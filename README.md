# 🤖 Claude 哨兵 — Claude Code 权限确认提醒器

> 不再因为离开座位而让 Claude Code 白白等你十几分钟。

<p align="center">
  <img src="https://img.shields.io/badge/platform-macOS%2014%2B-lightgrey">
  <img src="https://img.shields.io/badge/notify-Mac%20%7C%20iPhone%20%7C%20Watch-blue">
  <img src="https://img.shields.io/badge/license-MIT-green">
  <img src="https://img.shields.io/badge/python-3.8%2B-yellow">
</p>

---

## 这是什么？

**Claude 哨兵** 是一个轻量级的 macOS 后台监控工具。它实时监测 Claude Code 终端窗口，一旦检测到 `[y/n]` 权限确认弹窗，就会**自动推送通知**到你的 Mac、iPhone 和 Apple Watch。

你再也不用每隔几分钟就切回终端看一眼了——哨兵会替你盯着。

---

## 为什么要用？

### 你很可能遇到过这个场景：

> 你让 Claude Code 帮你重构一个模块，它干着干着弹出一个 `[y/n]` 确认——「是否允许执行这个命令？」而此时你刚好起身去接水、去洗手间、或者切到浏览器查资料。Claude Code 就在那里默默等着你，5 分钟、10 分钟、20 分钟……等你回来的时候，发现自己白白浪费了大量时间。

Claude Code 的权限确认机制是必要的安全设计，但它有一个前提假设：**你始终盯着屏幕**。然而现实中你不可能永远守在终端前面。

### Claude 哨兵解决的就是这个时间黑洞：

| 没有哨兵 | 有哨兵 |
|----------|--------|
| ❌ 离开座位 → Claude 卡住不知道 | ✅ 离开座位 → 10 秒后手机震动提醒 |
| ❌ 切到其他桌面 → 错过确认窗口 | ✅ Mac 横幅通知弹出来告诉你 |
| ❌ 在会议室 → 回来发现等了 20 分钟 | ✅ Apple Watch 手腕震动，立刻回去处理 |
| ❌ 不断切回终端检查 → 分心、低效 | ✅ 放心做别的事，有通知再回来 |

---

## 如何工作？

### 双重检测策略，确保不漏报

```
Claude Code 终端弹出 [y/n] 确认
        │
        ▼
┌─────────────────────────────────────────┐
│  策略一：AppleScript 读取终端文字         │
│  • 支持 iTerm2 / Terminal.app           │
│  • 正则匹配 [y/n]、(yes/no) 等模式       │
│  • 每 2 秒扫描一次                      │
├─────────────────────────────────────────┤
│  策略二：进程状态检测（后备方案）          │
│  • 检测 claude 进程是否阻塞在 stdin 读取  │
│  • 不依赖终端 UI，即使窗口最小化也能工作   │
│  • 作为策略一的补充，提高检测覆盖率        │
└─────────────────────────────────────────┘
        │
        ▼
  ┌─ [y/n] 类确认 ──── 10 秒延迟 ──── 🔔
  │
  └─ 其他提示 ──────── 30 秒延迟 ──── 🔔
        │
        ▼
┌──────────────────────────────────────────┐
│  💻  macOS 原生通知（横幅 + 通知中心）       │
│  📱  iPhone 推送（通过免费 Bark App）       │
│  ⌚  Apple Watch 同步推送（自动，无需配置）   │
└──────────────────────────────────────────┘
```

### 通知分级设计

| 类型 | 延迟 | 场景举例 |
|------|------|----------|
| 🚨 `[y/n]` 确认 | **10 秒** | 权限确认、工具调用审批、文件写入确认 |
| 📢 其他提示 | **30 秒** | "May I proceed?"、"Shall I continue?" 等 |

这样设计的原因是：`[y/n]` 确认是阻塞性的，Claude Code 完全停在那里等你，所以要在 10 秒内尽快通知。而其他提示可能只是询问式的问题，给 30 秒的缓冲，避免过度打扰。

### 防骚扰机制

哨兵不会反复轰炸你的手机：

- **首次通知后不再重复**：检测到确认弹窗 → 发一次通知 → 安静等待你回来
- **确认消失后进入冷却期**：你处理完确认后，哨兵进入 5 秒冷却，避免误报
- **不依赖轮询轰炸**：每 2 秒扫描一次终端文字，CPU 占用极低

---

## 安装与使用

### 前置条件

- macOS 14 Sonoma 或更高版本
- Python 3.8+
- Claude Code 运行在 **iTerm2** 或 **Terminal.app** 中
- （可选）iPhone / Apple Watch + [Bark App](https://apps.apple.com/app/bark/id1403753865) 用于跨设备推送

### 一分钟安装

```bash
# 1. 安装 terminal-notifier（macOS 通知增强工具）
brew install terminal-notifier

# 2. 克隆项目
git clone https://github.com/tczzx0428/-Claude-.git
cd -Claude-

# 3. 运行安装脚本
chmod +x setup.sh && ./setup.sh
```

安装脚本会引导你完成：

1. ✅ 检查 Python 3 和 macOS 环境
2. 📱 配置 iPhone / Apple Watch 推送（可选）
3. 💻 发送测试通知确认通道正常
4. 🔄 安装 LaunchAgent，设置为开机自启
5. ⚠️ 提醒授予辅助功能权限

### 配置 iPhone / Apple Watch 推送

> 如果你只在 Mac 上工作、不需要手机推送，可以跳过此步骤。

1. 在 iPhone 上从 App Store 安装 **Bark**（免费，无广告）
2. 打开 Bark，复制显示的 **Device Key**（一串随机字符）
3. 运行 `./setup.sh`，粘贴 Device Key
4. Apple Watch 会自动同步，**无需额外配置**

Bark 使用的是 Apple 推送通知服务 (APNs)，推送速度快、不耗电、完全免费。

### 授权辅助功能权限

为了通过 AppleScript 读取终端文字，需要授予辅助功能权限：

> **系统设置 → 隐私与安全性 → 辅助功能**
> 找到 **Terminal** 或 **iTerm2**，确保开关已开启。

如果不授权此权限，哨兵会自动退回到**进程状态检测**模式——准确度稍低但不会完全失效。

---

## 日常管理

```bash
# 查看服务运行状态
launchctl list | grep claudecode

# 停止服务
launchctl bootout gui/$(id -u)/com.claudecode.notifier

# 启动服务
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.claudecode.notifier.plist

# 重启服务
launchctl bootout gui/$(id -u)/com.claudecode.notifier
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.claudecode.notifier.plist

# 查看实时日志
tail -f monitor.log

# 重新运行配置向导
./setup.sh
```

---

## 配置说明

编辑 `config.json` 可以自定义行为：

```json
{
  "bark": {
    "enabled": true,
    "server_url": "https://api.day.app",
    "device_key": "你的Bark设备密钥"
  },
  "macos_notification": {
    "enabled": true
  },
  "check_interval": 2,
  "notification_delay": 10,
  "repeat_interval": 60,
  "max_notifications": 10,
  "cooldown_seconds": 5,
  "debug": false
}
```

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `bark.enabled` | 是否启用 iPhone/Apple Watch 推送 | `true` |
| `bark.server_url` | Bark 服务器地址（自建服务可修改） | `https://api.day.app` |
| `macos_notification.enabled` | 是否启用 Mac 本地通知 | `true` |
| `check_interval` | 终端扫描间隔（秒） | `2` |
| `notification_delay` | 检测到确认后延迟多久通知（秒） | `10` |
| `cooldown_seconds` | 确认消失后冷却时间（秒） | `5` |
| `debug` | 开启调试日志 | `false` |

---

## 项目结构

```
- Claude-
├── monitor.py                  ← 核心监控守护进程
├── setup.sh                    ← 交互式安装配置脚本
├── com.claudecode.notifier.plist ← LaunchAgent 配置（开机自启）
├── config.example.json         ← 配置文件模板
├── config.json                 ← 你的配置文件（不提交到 Git）
├── icon.jpg                    ← 通知头像
├── README.md                   ← 本文件
└── .gitignore
```

---

## 常见问题

### Q: 为什么检测不到我的终端？
A: 哨兵目前支持 **iTerm2** 和 **Terminal.app**。如果你使用 Warp、VS Code 内置终端、Hyper 等，文字检测策略不生效，但进程状态检测仍然可以工作。推荐使用 iTerm2 以获得最佳体验。

### Q: Bark 推送安全吗？
A: Bark 是开源项目（[GitHub](https://github.com/finb/bark)）。你的 Device Key 是唯一标识符，推送内容经过 Apple APNs 加密传输。如果你对隐私要求极高，可以自己部署 Bark Server。

### Q: 会不会影响 Claude Code 的正常运行？
A: 完全不会。哨兵是只读的——它只是通过 AppleScript 读取终端文字、通过 `ps` 查看进程状态，不会向终端写入任何内容，也不会拦截或修改 Claude Code 的输入输出。

### Q: 耗电吗？
A: 几乎不耗电。哨兵每 2 秒做一次轻量检测（AppleScript + ps），CPU 占用通常在 0.1% 以下，内存占用不到 30MB。

### Q: 可以同时监控多个 Claude Code 窗口吗？
A: 可以。进程检测会扫描所有 claude 相关进程，只要有一个在等待输入，就会触发通知。

---

## License

MIT © 2025
