#!/usr/bin/env python3
"""
Claude Code Notifier — Permission Prompt Monitor
=================================================
Monitors Claude Code for permission prompts and sends notifications
to macOS, iPhone, and Apple Watch after a configurable delay.

Detection strategies (multi-layered):
  1. AppleScript — reads visible text from iTerm2 / Terminal.app
  2. Process  state — checks whether the claude process is blocked on stdin
  3. Heuristic   — process exists but near-zero CPU for N seconds

Notifications:
  • macOS Notification Center  (built-in, zero setup)
  • Bark push  → iPhone / Apple Watch  (free App Store app)

Author: Claude Code Notifier
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Optional

# ═══════════════════════════════════════════════════════════════
# Paths
# ═══════════════════════════════════════════════════════════════

# Auto-detect project directory (where this script lives)
PROJECT_DIR = Path(__file__).resolve().parent
CONFIG_FILE = PROJECT_DIR / "config.json"
LOG_FILE    = PROJECT_DIR / "monitor.log"
ICON_FILE   = PROJECT_DIR / "icon.jpg"

# ═══════════════════════════════════════════════════════════════
# Default configuration
# ═══════════════════════════════════════════════════════════════

DEFAULT_CONFIG: dict = {
    "bark": {
        "enabled": True,
        "server_url": "https://api.day.app",   # Bark public server
        "device_key": "",                       # Fill this after installing Bark
    },
    "macos_notification": {
        "enabled": True,
    },
    "check_interval": 2,           # seconds between checks
    "notification_delay": 10,      # seconds before first notification
    "repeat_interval": 60,         # seconds between repeat notifications
    "max_notifications": 10,       # stop after this many (prevents spam)
    "cooldown_seconds": 5,         # brief cooldown after prompt resolves
    "debug": False,
}

# ═══════════════════════════════════════════════════════════════
# Permission-prompt patterns  (matched case-insensitively)
# ═══════════════════════════════════════════════════════════════

# Urgent — yes/no confirmations  → 10 second delay
YESNO_PATTERNS: list[str] = [
    r"\[y/n\]",
    r"\(y/n\)",
    r"\[yes/no\]",
    r"\(yes/no\)",
    r"\[Y/n\]",
    r"\(Y/n\)",
    r"\[y/N\]",
    r"\(y/N\)",
    r"\[a/d\]",
    r"\(a/d\)",
    r"\[allow/deny\]",
    r"\(allow/deny\)",
    r"\b(yes/no/always)\b",
    r"Do you want to allow",
    r"Do you want to proceed",
]

# Less urgent — other prompts  → 30 second delay
OTHER_PATTERNS: list[str] = [
    r"permission required",
    r"\bAllow\b.*\?",
    r"\bProceed\b.*\?",
    r"\bContinue\b.*\?",
    r"Run\s+\S+\s*\?",
    r"Execute\s+\S+\s*\?",
    r"May I\s",
    r"Can I\s",
    r"Shall I\s",
]


# ═══════════════════════════════════════════════════════════════
# Logging
# ═══════════════════════════════════════════════════════════════

def _timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log(msg: str, *, debug: bool = False, force: bool = False) -> None:
    """Append a line to the log file (and stderr when debug=True)."""
    if not debug and not force:
        return
    line = f"[{_timestamp()}] {msg}"
    try:
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
    except OSError:
        pass
    if force:
        print(line, flush=True, file=sys.stderr)


# ═══════════════════════════════════════════════════════════════
# Configuration helpers
# ═══════════════════════════════════════════════════════════════

def load_config() -> dict:
    """Load config from disk; write defaults if the file doesn't exist."""
    PROJECT_DIR.mkdir(parents=True, exist_ok=True)
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE) as fh:
                saved = json.load(fh)
            # Merge so new keys in DEFAULT_CONFIG always appear
            merged = {**DEFAULT_CONFIG, **saved}
            # Deep-merge nested dicts
            for k, v in DEFAULT_CONFIG.items():
                if isinstance(v, dict) and isinstance(merged.get(k), dict):
                    merged[k] = {**v, **merged[k]}
            return merged
        except (json.JSONDecodeError, OSError):
            pass
    # Write defaults
    with open(CONFIG_FILE, "w") as fh:
        json.dump(DEFAULT_CONFIG, fh, indent=2)
    return dict(DEFAULT_CONFIG)


# ═══════════════════════════════════════════════════════════════
# AppleScript helpers  —  read visible terminal text
# ═══════════════════════════════════════════════════════════════

def _run_applescript(source: str, timeout: int = 4) -> str | None:
    """Run an AppleScript snippet; return its stdout or None on failure."""
    try:
        proc = subprocess.run(
            ["osascript", "-e", source],
            capture_output=True, text=True, timeout=timeout,
        )
        out = proc.stdout.strip()
        if not out or out in ("NO_ITERM", "NO_TERMINAL", "ERROR", "N/A"):
            return None
        return out
    except Exception:
        return None


def get_frontmost_app_name() -> str | None:
    """Return the localized name of the frontmost application."""
    src = '''
    tell application "System Events"
        set frontApp to name of first application process whose frontmost is true
        return frontApp
    end tell
    '''
    return _run_applescript(src, timeout=2)


def get_iterm2_text() -> str | None:
    """Return the visible text of iTerm2's current session, or None."""
    src = '''
    tell application "System Events"
        if not (exists process "iTerm2") then return "NO_ITERM"
    end tell
    tell application "iTerm2"
        try
            return text of current session of current window
        on error
            return "ERROR"
        end try
    end tell
    '''
    return _run_applescript(src)


def get_terminal_app_text() -> str | None:
    """Return the visible text of Terminal.app's front window, or None."""
    src = '''
    tell application "System Events"
        if not (exists process "Terminal") then return "NO_TERMINAL"
        try
            tell process "Terminal"
                set frontWin to front window
                -- macOS Sequoia / Sonoma:  splitter group → scroll area → text area
                try
                    return value of text area 1 of scroll area 1 of UI element 1 of frontWin
                on error
                    -- older macOS fallback
                    try
                        return value of text area 1 of scroll area 1 of group 1 of frontWin
                    on error
                        try
                            return value of text area 1 of scroll area 1 of frontWin
                        on error
                            return "ERROR"
                        end try
                    end try
                end try
            end tell
        on error
            return "ERROR"
        end try
    end tell
    '''
    return _run_applescript(src)


def get_terminal_text() -> str | None:
    """
    Best-effort read of the frontmost terminal's visible text.
    Supports iTerm2 and Terminal.app.  Returns None when nothing is available.
    """
    frontmost = get_frontmost_app_name() or ""
    if "iTerm" in frontmost:
        return get_iterm2_text()
    if "Terminal" in frontmost:
        return get_terminal_app_text()
    # … Warp / VS Code terminal / etc. — not supported via AppleScript
    return None


# ═══════════════════════════════════════════════════════════════
# Process-state helpers
# ═══════════════════════════════════════════════════════════════

def find_claude_pids() -> list[int]:
    """Return PIDs for every process whose command line contains 'claude'."""
    try:
        proc = subprocess.run(
            ["pgrep", "-f", "claude"],
            capture_output=True, text=True, timeout=3,
        )
        return [int(p) for p in proc.stdout.strip().split("\n") if p]
    except Exception:
        return []


def _ps_state(pid: int) -> tuple[str, str]:
    """Return (state, wchan) for *pid*, e.g. ('S+', 'ttread')."""
    try:
        proc = subprocess.run(
            ["ps", "-p", str(pid), "-o", "state=,wchan="],
            capture_output=True, text=True, timeout=3,
        )
        parts = proc.stdout.strip().split()
        s = parts[0] if len(parts) > 0 else ""
        w = parts[1] if len(parts) > 1 else ""
        return s, w
    except Exception:
        return "", ""


def is_waiting_on_stdin(pid: int) -> bool:
    """
    Heuristic: the process is sleeping in the foreground (state S+)
    AND its kernel wait-channel suggests it's blocked on terminal read.
    """
    state, wchan = _ps_state(pid)
    if "+" not in state:               # not a foreground process
        return False
    # Common macOS wchan values for a process blocked on stdin / tty read
    stdin_wchan = {"ttread", "read", "poll", "select", "tty", "piperd", "nread"}
    return any(kw in wchan.lower() for kw in stdin_wchan)


def is_any_claude_waiting() -> bool:
    """True when at least one claude process appears to be waiting for input."""
    for pid in find_claude_pids():
        if is_waiting_on_stdin(pid):
            return True
    return False


# ═══════════════════════════════════════════════════════════════
# Prompt detection
# ═══════════════════════════════════════════════════════════════

def _match_patterns(text: str, patterns: list[str]) -> bool:
    """Check whether *text* matches any pattern in *patterns*."""
    lines = text.split("\n")
    recent = "\n".join(lines[-60:])
    for pat in patterns:
        if re.search(pat, recent, re.IGNORECASE):
            return True
    return False


def detect_prompt() -> str | None:
    """
    Multi-strategy prompt detection.
    Returns 'yesno' for urgent y/n confirmations,
            'other' for less urgent prompts,
            None    when no prompt is detected.
    """
    text = get_terminal_text()
    if text:
        # Check yes/no first (more specific)
        if _match_patterns(text, YESNO_PATTERNS):
            return "yesno"
        if _match_patterns(text, OTHER_PATTERNS):
            return "other"

    # Strategy 2 — process state (fallback)
    if is_any_claude_waiting():
        return "yesno"  # treat process-blocked as urgent

    return None


# ═══════════════════════════════════════════════════════════════
# Notifications
# ═══════════════════════════════════════════════════════════════

def notify_macos(title: str, body: str) -> bool:
    """Post a macOS Notification Center notification.
    Tries terminal-notifier first, falls back to osascript.
    """
    tn_paths = [
        "/opt/homebrew/bin/terminal-notifier",
        "/usr/local/bin/terminal-notifier",
    ]
    args = ["-title", title, "-message", body,
            "-sound", "default", "-timeout", "15"]
    # Right-side content image (your photo)
    if ICON_FILE.exists():
        args += ["-contentImage", str(ICON_FILE)]

    for tn in tn_paths:
        if os.path.exists(tn):
            try:
                subprocess.run([tn] + args, capture_output=True, timeout=5)
                return True
            except Exception:
                continue

    # Fallback — osascript
    safe_title = title.replace('"', '\\"')
    safe_body  = body.replace('"', '\\"')
    src = f'display notification "{safe_body}" with title "{safe_title}" sound name "default"'
    try:
        subprocess.run(["osascript", "-e", src], capture_output=True, timeout=5)
        return True
    except Exception:
        return False


def notify_bark(cfg: dict, title: str, body: str) -> bool:
    """Push a notification via Bark to iPhone / Apple Watch."""
    device_key = cfg.get("device_key", "").strip()
    if not device_key:
        return False
    server = cfg.get("server_url", "https://api.day.app").rstrip("/")

    # Build URL with extra params
    params = {
        "level": "active",       # time-sensitive delivery (iOS 15+)
        "isArchive": "1",        # save to Bark history
        "group": "claude-code",  # group notifications together
    }
    qs = urllib.parse.urlencode(params)
    url = f"{server}/{device_key}/{urllib.parse.quote(title)}/{urllib.parse.quote(body)}?{qs}"

    try:
        req = urllib.request.Request(url, method="GET")
        urllib.request.urlopen(req, timeout=10)
        return True
    except Exception:
        return False


def send_notifications(cfg: dict, prompt_type: str) -> dict[str, bool]:
    """Fire all enabled notification channels.  Returns per-channel results."""
    if prompt_type == "yesno":
        title = "🤖 Claude Code 等你确认 [y/n]"
        body  = "有个 yes/no 权限确认已等待 10 秒，请尽快处理！"
    else:
        title = "🤖 Claude Code 提醒"
        body  = "有个提示已等待 30 秒，记得回来看看。"

    results: dict[str, bool] = {}

    if cfg.get("macos_notification", {}).get("enabled", True):
        results["macos"] = notify_macos(title, body)

    if cfg.get("bark", {}).get("enabled", True):
        results["bark"] = notify_bark(cfg["bark"], title, body)

    return results


# ═══════════════════════════════════════════════════════════════
# Main monitor loop  (finite state machine)
# ═══════════════════════════════════════════════════════════════

class State:
    IDLE            = "idle"
    PROMPT_DETECTED = "prompt_detected"   # timer running, not yet notified
    NOTIFIED        = "notified"          # first alert sent, waiting / repeating
    COOLDOWN        = "cooldown"          # prompt resolved, brief pause


def main() -> None:
    cfg = load_config()

    interval          = max(1, cfg["check_interval"])
    delay_yesno       = 10   # urgent  y/n confirmations
    delay_other       = 30   # regular  other prompts
    cooldown_secs     = max(1, cfg["cooldown_seconds"])
    debug             = cfg.get("debug", False)

    # --- welcome ---
    log("Claude Code Notifier started.", force=True)
    log(f"  check_interval      = {interval}s", force=True)
    log(f"  yes/no delay        = {delay_yesno}s", force=True)
    log(f"  other delay         = {delay_other}s", force=True)
    log(f"  bark enabled        = {cfg['bark']['enabled'] and bool(cfg['bark'].get('device_key', '').strip())}", force=True)
    log(f"  macos notifications = {cfg['macos_notification']['enabled']}", force=True)

    # --- state ---
    state: str = State.IDLE
    prompt_type: str = ""              # 'yesno' or 'other'
    prompt_start: float = 0.0
    cooldown_until: float = 0.0

    while True:
        try:
            now = time.monotonic()

            # -- cooldown guard -------------------------------------------------
            if state == State.COOLDOWN and now < cooldown_until:
                time.sleep(interval)
                continue
            if state == State.COOLDOWN and now >= cooldown_until:
                state = State.IDLE

            # -- detection ------------------------------------------------------
            detected = detect_prompt()

            # -- state transitions ----------------------------------------------
            if state == State.IDLE and detected:
                state = State.PROMPT_DETECTED
                prompt_type = detected
                prompt_start = now
                log(f"Prompt detected ({detected}) — timer started.", debug=debug)

            elif state == State.PROMPT_DETECTED:
                if not detected:
                    log(f"Prompt resolved before notification ({now - prompt_start:.0f}s).", debug=debug)
                    state = State.COOLDOWN
                    cooldown_until = now + cooldown_secs
                    continue

                threshold = delay_yesno if prompt_type == "yesno" else delay_other
                elapsed = now - prompt_start
                if elapsed >= threshold:
                    tag = "y/n" if prompt_type == "yesno" else "other"
                    log(f"Threshold reached [{tag}] ({elapsed:.0f}s), sending notification…", force=True)
                    results = send_notifications(cfg, prompt_type)
                    log(f"  → {results}", debug=debug)
                    state = State.NOTIFIED

            elif state == State.NOTIFIED:
                if not detected:
                    log(f"Prompt resolved (was active {now - prompt_start:.0f}s).", force=True)
                    state = State.COOLDOWN
                    cooldown_until = now + cooldown_secs
                    continue
                # No repeat — stay in NOTIFIED until prompt resolves

        except Exception as exc:
            log(f"Loop error: {exc}", force=True)

        time.sleep(interval)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--init":
        # Only write config, don't start monitoring
        load_config()
        print(f"Config written to {CONFIG_FILE}")
    else:
        main()
