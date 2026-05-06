# Auto-Debug: 自动错误监控和修复系统
# Auto-Debug: Automated Error Monitoring and Self-Healing System

[English](#english) | [中文](#中文)

---

## English

### Overview

A universal automated error monitoring and self-healing framework for unattended debugging.

**Key Benefits:**
- **0 token consumption** when no errors (pure script checking)
- Auto-detect → Auto-report → Auto-analyze → Auto-fix
- Works with Chrome extensions, Python scripts, Node.js services, and more

### Architecture

```
┌─────────────┐    Error Report    ┌──────────────┐    When Errors    ┌─────────────┐
│  App/Extension│ ────────────────→ │  Error Directory│ ──────────────→ │  LLM Analysis│
│  (Running)    │                  │  (Local Files)  │                │  Auto-Fix    │
└─────────────┘                  └──────────────┘                └─────────────┘
       ↑                                                                │
       │                    Fixed Code                                  │
       └────────────────────────────────────────────────────────────────┘
```

### Components

#### 1. Error Monitor (error-monitor.js)

For Chrome extensions, automatically captures all errors.

**Features:**
- Intercepts `console.error`
- Catches uncaught exceptions
- Catches unhandled Promise rejections
- Auto-saves to IndexedDB
- Generates error reports
- **Error deduplication** with fingerprints
- **Auto-cleanup** after analysis

#### 2. Check Script (check_errors.py)

For scheduled error checking with 0 token consumption.

**Features:**
- Checks error directory for new files
- Skips already-analyzed errors
- Auto-cleans processed files
- Outputs JSON summary for LLM analysis

#### 3. Setup Script (setup_auto_debug.py)

Initialize auto-debug for any project.

### Quick Start

#### Step 1: Initialize Project

```bash
python scripts/setup_auto_debug.py <project-name> <project-path>
```

#### Step 2: Integrate Error Monitor

**Chrome Extension:**

```javascript
// Add to manifest.json
{
  "content_scripts": [{
    "js": ["error-monitor.js", "content.js"]
  }]
}

// Initialize in content.js
const errorMonitor = new ErrorMonitor({
    projectName: 'your-project',
    ignorePatterns: ['kQuotaBytes'],
    saveCallback: async (errors) => {
        // Save to your preferred location
    }
});
```

**Python:**

```python
from error_monitor import ErrorMonitor

monitor = ErrorMonitor("your-project")

try:
    risky_operation()
except Exception as e:
    monitor.capture_error("operation_failed", str(e))
```

**Node.js:**

```javascript
const ErrorMonitor = require('./error-monitor');

const monitor = new ErrorMonitor('your-project');

process.on('uncaughtException', (error) => {
    monitor.captureError('uncaught', error.message);
});
```

#### Step 3: Create Cron Job

```bash
hermes cronjob create \
    --name "auto-debug-<project>" \
    --schedule "*/10 * * * *" \
    --script "check_errors.py <error-dir> <project-name> --cleanup" \
    --prompt "Analyze and fix errors if found, otherwise return empty"
```

### Token Consumption

| Scenario | Consumption | Notes |
|----------|-------------|-------|
| No errors | **0 tokens** | Pure script check |
| With errors | 3000-5000 tokens | Analysis + fix |
| Same error repeated | **0 tokens** | Deduplication prevents re-analysis |

### Directory Structure

```
~/.hermes/auto-debug/<project>/
├── errors-*.json          # New errors (pending)
├── processed/             # Analyzed errors
│   └── errors-*.json
└── config.json
```

---

## 中文

### 概述

一套通用的自动错误监控和修复框架，实现无人值守的自动调试。

**核心优势：**
- 无错误时 **0 token 消耗**（纯脚本检查）
- 自动检测 → 自动上报 → 自动分析 → 自动修复
- 可应用于 Chrome 扩展、Python 脚本、Node.js 服务等

### 架构

```
┌─────────────┐    错误上报     ┌──────────────┐    有错误时    ┌─────────────┐
│  应用/扩展   │ ──────────────→ │  错误目录     │ ────────────→ │  LLM 分析   │
│  (运行中)    │                │  (本地文件)   │              │  自动修复    │
└─────────────┘                └──────────────┘              └─────────────┘
       ↑                                                           │
       │                    修复后的代码                            │
       └───────────────────────────────────────────────────────────┘
```

### 组件

#### 1. 错误监控模块 (error-monitor.js)

适用于 Chrome 扩展，自动捕获所有错误。

**功能：**
- 拦截 `console.error`
- 捕获未处理异常
- 捕获 Promise 拒绝
- 自动保存到 IndexedDB
- 生成错误报告
- **错误去重**（指纹机制）
- **自动清理**（分析后移动到 processed 目录）

#### 2. 检查脚本 (check_errors.py)

用于定时检查错误，0 token 消耗。

**功能：**
- 检查错误目录中的新文件
- 跳过已分析的错误
- 自动清理已处理的文件
- 输出 JSON 格式的摘要供 LLM 分析

#### 3. 初始化脚本 (setup_auto_debug.py)

为任何项目初始化自动调试系统。

### 快速开始

#### 步骤 1：初始化项目

```bash
python scripts/setup_auto_debug.py <项目名称> <项目路径>
```

#### 步骤 2：集成错误监控

**Chrome 扩展：**

```javascript
// 在 manifest.json 中添加
{
  "content_scripts": [{
    "js": ["error-monitor.js", "content.js"]
  }]
}

// 在 content.js 中初始化
const errorMonitor = new ErrorMonitor({
    projectName: 'your-project',
    ignorePatterns: ['kQuotaBytes'],
    saveCallback: async (errors) => {
        // 保存到你选择的位置
    }
});
```

**Python：**

```python
from error_monitor import ErrorMonitor

monitor = ErrorMonitor("your-project")

try:
    risky_operation()
except Exception as e:
    monitor.capture_error("operation_failed", str(e))
```

**Node.js：**

```javascript
const ErrorMonitor = require('./error-monitor');

const monitor = new ErrorMonitor('your-project');

process.on('uncaughtException', (error) => {
    monitor.captureError('uncaught', error.message);
});
```

#### 步骤 3：创建定时任务

```bash
hermes cronjob create \
    --name "auto-debug-<项目名>" \
    --schedule "*/10 * * * *" \
    --script "check_errors.py <错误目录> <项目名> --cleanup" \
    --prompt "如果有错误则分析修复，否则返回空"
```

### Token 消耗

| 场景 | 消耗 | 说明 |
|------|------|------|
| 无错误 | **0 tokens** | 纯脚本检查 |
| 有错误 | 3000-5000 tokens | 分析 + 修复 |
| 同一错误重复出现 | **0 tokens** | 去重机制避免重复分析 |

### 目录结构

```
~/.hermes/auto-debug/<项目名>/
├── errors-*.json          # 新错误（待处理）
├── processed/             # 已分析的错误
│   └── errors-*.json
└── config.json
```

---

## Changelog

### v1.1.0 (2026-05-06)

**Chrome MV3 Architecture Fix:**
- `chrome.downloads` is NOT available in content scripts — must use service worker
- `URL.createObjectURL` is NOT available in service workers — use data URL
- `const` declarations don't expose to `window` — use `window.xxx` for cross-file access
- New architecture: content script → `chrome.runtime.sendMessage` → background.js → `chrome.downloads`

**Fingerprint Deduplication:**
- Same error type (same fingerprint) only reported once
- Saves analyzed fingerprints in `analyzed_fingerprints.json`
- Max 500 fingerprints retained, old ones auto-evicted

**Downloads Auto-Cleanup:**
- Error files in `~/Downloads/` deleted after analysis
- File only exists between error occurrence and next cron check (~10 min max)

**Multi-Source Error Checking:**
- `check_errors.py` checks both `~/.hermes/auto-debug/{project}/` and `~/Downloads/`
- Background.js errors merged into content script error reports

### v1.0.0 (2026-05-05)

Initial release.

---

## License

MIT

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Support

If you have any questions or issues, please open an issue on GitHub.
