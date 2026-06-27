# 🤖 Claude 哨兵

> 不再错过 Claude Code 的每一次权限确认

Claude Code 弹出 `[y/n]` 时你刚好去接水了。它在等你，你浑然不知。

**Claude 哨兵** 在后台盯着终端，一旦检测到确认提示，10~30 秒后推送到你的所有设备。

<p align="center">
  <img src="https://img.shields.io/badge/platform-macOS%2014%2B-lightgrey">
  <img src="https://img.shields.io/badge/notify-Mac%20%7C%20iPhone%20%7C%20Watch-blue">
  <img src="https://img.shields.io/badge/license-MIT-green">
</p>

---

## 工作原理

```
Claude Code 弹出 [y/n] 确认
        │
        ▼
  哨兵检测到提示 (每 2 秒扫描)
        │
        ├── [y/n] 类 → 10 秒 → 🔔
        │
        └── 其他提示 → 30 秒 → 🔔
        │
        ▼
  ┌──────────────────────────┐
  │  💻 macOS 原生横幅        │
  │  📱 iPhone (Bark 推送)    │
  │  ⌚ Apple Watch (自动同步) │
  └──────────────────────────┘
```

## 快速开始

```bash
# 安装 terminal-notifier
brew install terminal-notifier

# 克隆项目
git clone https://github.com/tczzx0428/-Claude-.git
cd -Claude-

# 运行安装
chmod +x setup.sh && ./setup.sh
```

## 配置 iPhone / Apple Watch

1. iPhone App Store 安装 [Bark](https://apps.apple.com/app/bark/id1403753865)
2. 打开 Bark，复制 **Device Key**
3. 运行 `./setup.sh` → 粘贴 Key
4. ⌚ 自动同步，无需额外配置

## 检测策略

| 策略 | 方式 | 说明 |
|------|------|------|
| 终端文字 | AppleScript 读取 Terminal / iTerm2 | 匹配 `[y/n]` 等确认模式 |
| 进程状态 | 检测 claude 是否阻塞在 stdin | 后备方案 |

## 通知分级

| 类型 | 延迟 | 场景 |
|------|------|------|
| `[y/n]` 确认 | **10 秒** | 权限确认、工具调用确认 |
| 其他提示 | **30 秒** | 一般性提问 |

## 项目结构

```
Claude-哨兵/
├── monitor.py              ← 核心监控守护进程
├── setup.sh                ← 交互式安装脚本
├── config.example.json     ← 配置模板
└── README.md
```

## 管理命令

```bash
# 查看运行状态
launchctl list | grep claudecode

# 停止
launchctl bootout gui/$(id -u)/com.claudecode.notifier

# 启动
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.claudecode.notifier.plist

# 查看实时日志
tail -f monitor.log
```
