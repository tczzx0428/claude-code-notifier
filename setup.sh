#!/usr/bin/env bash
# ================================================================
# Claude Code Notifier — Setup & Install
# ================================================================
# One-command setup that:
#   1. Checks prerequisites (Python 3, osascript)
#   2. Guides you through Bark setup for iPhone / Apple Watch
#   3. Installs a LaunchAgent so the monitor starts on login
#   4. Starts the monitor immediately
# ================================================================

set -euo pipefail

PROJECT_DIR="$HOME/claude-code-notifier"
MONITOR_PY="$PROJECT_DIR/monitor.py"
PLIST_TMPL="$PROJECT_DIR/com.claudecode.notifier.plist"
PLIST_DST="$HOME/Library/LaunchAgents/com.claudecode.notifier.plist"
CONFIG_DIR="$HOME/.claude-code-notifier"
CONFIG_FILE="$CONFIG_DIR/config.json"

# ── Colours ───────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; NC='\033[0m'  # no colour

banner() {
    echo ""
    echo -e "${CYAN}╔══════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║    🤖  Claude Code Notifier — Setup          ║${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════════════╝${NC}"
    echo ""
}

success() { echo -e "  ${GREEN}✔${NC} $*"; }
warn()    { echo -e "  ${YELLOW}⚠${NC} $*"; }
fail()    { echo -e "  ${RED}✘${NC} $*"; }
info()    { echo -e "  ${CYAN}→${NC} $*"; }

# ── Step 0: pre-flight checks ────────────────────────────────
banner

info "Checking prerequisites…"

if ! command -v python3 &>/dev/null; then
    fail "python3 not found — please install Python 3 first."
    exit 1
fi
success "python3  $(python3 --version 2>&1)"

if ! command -v osascript &>/dev/null; then
    fail "osascript not available — this must run on macOS."
    exit 1
fi
success "osascript available"

# ── Step 1: config ───────────────────────────────────────────
echo ""
info "Setting up configuration…"
mkdir -p "$CONFIG_DIR"

# Initialise config if needed
if [ ! -f "$CONFIG_FILE" ]; then
    python3 "$MONITOR_PY" --init 2>/dev/null || true
    success "Default config written to $CONFIG_FILE"
else
    success "Config already exists at $CONFIG_FILE"
fi

# ── Step 2: Bark (iPhone / Apple Watch) ──────────────────────
echo ""
echo -e "${YELLOW}┌─────────────────────────────────────────────────┐${NC}"
echo -e "${YELLOW}│  📱  iPhone / Apple Watch 通知设置 (Bark)        │${NC}"
echo -e "${YELLOW}└─────────────────────────────────────────────────┘${NC}"
echo ""
echo "  Bark 是一款免费的 iOS 推送通知 App，"
echo "  它能把通知推送到你的 iPhone 和 Apple Watch 上。"
echo ""
echo "  设置步骤："
echo "    1. 在 iPhone 上从 App Store 安装 「Bark」"
echo "    2. 打开 Bark，复制显示的 Device Key / URL"
echo "    3. 把 Device Key 粘贴到下方"
echo ""
read -r -p "  Bark Device Key (留空跳过): " BARK_KEY

if [ -n "$BARK_KEY" ]; then
    # Update config.json with the key using python
    python3 -c "
import json
with open('$CONFIG_FILE') as f:
    cfg = json.load(f)
cfg['bark']['device_key'] = '$BARK_KEY'
cfg['bark']['enabled'] = True
with open('$CONFIG_FILE', 'w') as f:
    json.dump(cfg, f, indent=2)
print('Bark key saved.')
"
    success "Bark 已配置！通知将推送到你的 iPhone 和 Apple Watch。"

    # Test Bark notification
    echo ""
    read -r -p "  要发送一条测试通知到你的 iPhone/Watch 吗? (y/n) " TEST_BARK
    if [ "$TEST_BARK" = "y" ] || [ "$TEST_BARK" = "Y" ]; then
        info "正在发送测试通知…"
        python3 -c "
import json, urllib.request, urllib.parse
with open('$CONFIG_FILE') as f:
    cfg = json.load(f)
bk = cfg['bark']
key = bk['device_key']
server = bk.get('server_url', 'https://api.day.app').rstrip('/')
title = urllib.parse.quote('✅ 测试通知')
body  = urllib.parse.quote('Claude Code Notifier 已就绪！当你离开 Mac 时也能收到权限确认提醒。')
url  = f'{server}/{key}/{title}/{body}?level=active&isArchive=1&group=claude-code'
urllib.request.urlopen(urllib.request.Request(url), timeout=10)
print('Test notification sent! Check your iPhone / Apple Watch.')
"
        success "测试通知已发送，请检查你的手机和手表。"
    fi
else
    info "已跳过 Bark 设置（仅使用 macOS 本地通知）。"
fi

# ── Step 3: macOS notification test ──────────────────────────
echo ""
echo -e "${YELLOW}┌─────────────────────────────────────────────────┐${NC}"
echo -e "${YELLOW}│  💻  macOS 本地通知测试                          │${NC}"
echo -e "${YELLOW}└─────────────────────────────────────────────────┘${NC}"
echo ""
read -r -p "  要发送一条 macOS 测试通知吗? (y/n) " TEST_MAC
if [ "$TEST_MAC" = "y" ] || [ "$TEST_MAC" = "Y" ]; then
    osascript -e 'display notification "如果你看到这条通知，说明 macOS 通知通道正常！" with title "✅ Claude Code Notifier 测试" sound name "default"'
    success "macOS 通知已发送（检查屏幕右上角）。"
fi

# ── Step 4: LaunchAgent ──────────────────────────────────────
echo ""
echo -e "${YELLOW}┌─────────────────────────────────────────────────┐${NC}"
echo -e "${YELLOW}│  🔄 安装后台服务 (LaunchAgent)                    │${NC}"
echo -e "${YELLOW}└─────────────────────────────────────────────────┘${NC}"
echo ""
info "安装 LaunchAgent → $PLIST_DST"

mkdir -p "$HOME/Library/LaunchAgents"

# Fill template
sed \
    -e "s|{{MONITOR_PATH}}|$MONITOR_PY|g" \
    -e "s|{{LOG_DIR}}|$CONFIG_DIR|g" \
    "$PLIST_TMPL" > "$PLIST_DST"

success "LaunchAgent plist 已写入。"

# Unload old instance if present, then load
launchctl bootout "gui/$(id -u)/com.claudecode.notifier" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST_DST" 2>/dev/null || \
    launchctl load "$PLIST_DST"

success "后台服务已启动。"

# ── Step 5: Accessibility permission ─────────────────────────
echo ""
echo -e "${YELLOW}┌─────────────────────────────────────────────────┐${NC}"
echo -e "${YELLOW}│  ⚠️  重要：辅助功能权限                            │${NC}"
echo -e "${YELLOW}└─────────────────────────────────────────────────┘${NC}"
echo ""
echo "  为了读取终端中的权限确认文字，需要授予「辅助功能」权限："
echo ""
echo "  系统设置 → 隐私与安全性 → 辅助功能"
echo "  确保  Terminal / iTerm2 已在列表中并已开启。"
echo ""
echo "  如果跳过此步骤，监控器仍可通过进程状态检测来工作，"
echo "  但准确度会降低。"
echo ""

# ── Done ─────────────────────────────────────────────────────
echo -e "${GREEN}╔══════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  ✅  安装完成！                               ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════╝${NC}"
echo ""
echo "  监控器已在后台运行。每次开机时会自动启动。"
echo ""
echo "  管理命令："
echo "    查看日志:  tail -f $CONFIG_DIR/monitor.log"
echo "    停止服务:  launchctl bootout gui/\$(id -u)/com.claudecode.notifier"
echo "    启动服务:  launchctl bootstrap gui/\$(id -u) $PLIST_DST"
echo "    重新配置:  $PROJECT_DIR/setup.sh"
echo "    查看状态:  cat $CONFIG_FILE"
echo ""
echo "  📱 Bark App 下载: https://apps.apple.com/app/bark/id1403753865"
echo ""
