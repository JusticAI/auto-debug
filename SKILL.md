---
name: auto-debug
description: 自动错误监控和修复系统 - 适用于任何 Chrome 扩展、Python 脚本、Node.js 服务
tags: [debugging, automation, error-monitoring, chrome-extension, self-healing]
triggers:
  - "自动debug"
  - "自动修复"
  - "错误监控"
  - "auto-debug"
  - "self-healing"
  - "无人值守"
---

# Auto-Debug: 自动错误监控和修复系统

## 概述

一套通用的自动错误监控和修复框架，实现无人值守的自动调试。

**核心优势：**
- 无错误时 **0 token 消耗**（纯脚本检查）
- 自动检测 → 自动上报 → 自动分析 → 自动修复
- 可应用于 Chrome 扩展、Python 脚本、Node.js 服务等

## 架构

```
┌─────────────┐    错误上报     ┌──────────────┐    有错误时    ┌─────────────┐
│  应用/扩展   │ ──────────────→ │  错误目录     │ ────────────→ │  LLM 分析   │
│  (运行中)    │                │  (本地文件)   │              │  自动修复    │
└─────────────┘                └──────────────┘              └─────────────┘
       ↑                                                           │
       │                    修复后的代码                            │
       └───────────────────────────────────────────────────────────┘
```

## 组件

### 1. 错误监控模块 (error-monitor.js)

适用于 Chrome 扩展，自动捕获所有错误。

**文件位置：** 项目目录下 `error-monitor.js`

```javascript
/**
 * 通用错误监控器 - Chrome 扩展版
 * 
 * 功能：
 * - 拦截 console.error
 * - 捕获未处理异常
 * - 捕获 Promise 拒绝
 * - 自动保存到 IndexedDB
 * - 生成错误报告
 */

class ErrorMonitor {
    constructor(options = {}) {
        this.errors = [];
        this.maxErrors = options.maxErrors || 100;
        this.ignorePatterns = options.ignorePatterns || [];
        this.projectName = options.projectName || 'unknown';
        this.saveCallback = options.saveCallback || null;
        this.setupInterceptors();
    }

    setupInterceptors() {
        // 拦截 console.error
        const originalError = console.error;
        console.error = (...args) => {
            this.captureError('console.error', args.join(' '));
            originalError.apply(console, args);
        };

        // 拦截未捕获的错误
        window.addEventListener('error', (event) => {
            this.captureError('uncaught', `${event.message} at ${event.filename}:${event.lineno}`);
        });

        // 拦截未处理的 Promise 错误
        window.addEventListener('unhandledrejection', (event) => {
            this.captureError('unhandledrejection', event.reason?.toString() || 'Unknown error');
        });
    }

    captureError(type, message) {
        if (this.shouldIgnore(message)) return;

        const error = {
            type,
            message: message.substring(0, 500),
            timestamp: new Date().toISOString(),
            url: window.location.href,
        };

        this.errors.push(error);

        if (this.errors.length > this.maxErrors) {
            this.errors = this.errors.slice(-this.maxErrors);
        }

        this.saveErrors();
    }

    shouldIgnore(message) {
        return this.ignorePatterns.some(pattern => message.includes(pattern));
    }

    async saveErrors() {
        if (this.saveCallback) {
            await this.saveCallback(this.errors);
        }
    }

    getErrorsSince(minutes = 30) {
        const cutoff = new Date(Date.now() - minutes * 60 * 1000);
        return this.errors.filter(e => new Date(e.timestamp) > cutoff);
    }

    getErrorSummary() {
        const recent = this.getErrorsSince(30);
        const byType = {};
        
        for (const error of recent) {
            const key = error.type;
            if (!byType[key]) byType[key] = [];
            byType[key].push(error);
        }

        return {
            total: this.errors.length,
            recent: recent.length,
            byType: Object.entries(byType).map(([type, errors]) => ({
                type,
                count: errors.length,
                lastError: errors[errors.length - 1]?.message,
            })),
        };
    }

    generateReport() {
        const summary = this.getErrorSummary();
        const recentErrors = this.getErrorsSince(60);

        let report = `# Bug Report - ${this.projectName}\n`;
        report += `Generated: ${new Date().toISOString()}\n`;
        report += `URL: ${window.location.href}\n\n`;

        report += `## Summary\n`;
        report += `- Total errors: ${summary.total}\n`;
        report += `- Recent (30min): ${summary.recent}\n\n`;

        if (summary.byType.length > 0) {
            report += `## Error Types\n`;
            for (const { type, count, lastError } of summary.byType) {
                report += `- **${type}**: ${count} occurrences\n`;
                report += `  Last: ${lastError}\n`;
            }
            report += `\n`;
        }

        if (recentErrors.length > 0) {
            report += `## Recent Errors (last 1 hour)\n`;
            for (const error of recentErrors.slice(-20)) {
                report += `- [${error.timestamp}] ${error.type}: ${error.message}\n`;
            }
        }

        return report;
    }

    clearErrors() {
        this.errors = [];
        this.saveErrors();
    }
}

// 导出
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ErrorMonitor;
}
```

### 2. Python 监控脚本 (check_errors.py)

用于定时检查错误文件，0 token 消耗。

**文件位置：** `~/.hermes/scripts/check_errors.py`

```python
#!/usr/bin/env python3
"""
Auto-Debug 错误检查脚本
用法：python check_errors.py <错误目录> <项目名称>
输出：JSON 格式的错误摘要，供 Hermes Agent 分析
"""

import os
import sys
import json
from datetime import datetime, timedelta
from pathlib import Path

def check_errors(error_dir: str, project_name: str) -> dict:
    """检查错误目录中的新错误"""
    
    error_path = Path(error_dir)
    if not error_path.exists():
        return {
            "has_errors": False,
            "project": project_name,
            "message": "错误目录不存在"
        }
    
    # 查找最近1小时的错误文件
    cutoff = datetime.now() - timedelta(hours=1)
    recent_errors = []
    
    for error_file in error_path.glob("*.json"):
        try:
            mtime = datetime.fromtimestamp(error_file.stat().st_mtime)
            if mtime > cutoff:
                with open(error_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    recent_errors.append({
                        "file": error_file.name,
                        "modified": mtime.isoformat(),
                        "data": data
                    })
        except Exception as e:
            recent_errors.append({
                "file": error_file.name,
                "error": str(e)
            })
    
    if not recent_errors:
        return {
            "has_errors": False,
            "project": project_name,
            "message": "最近1小时无错误"
        }
    
    # 汇总错误
    total_errors = 0
    error_types = {}
    
    for error_file in recent_errors:
        if "data" in error_file:
            errors = error_file["data"].get("errors", [])
            total_errors += len(errors)
            for error in errors:
                error_type = error.get("type", "unknown")
                error_types[error_type] = error_types.get(error_type, 0) + 1
    
    return {
        "has_errors": True,
        "project": project_name,
        "total_errors": total_errors,
        "error_types": error_types,
        "recent_files": len(recent_errors),
        "errors": recent_errors,
        "timestamp": datetime.now().isoformat()
    }

def main():
    if len(sys.argv) < 3:
        print(json.dumps({
            "has_errors": False,
            "error": "用法: check_errors.py <错误目录> <项目名称>"
        }))
        sys.exit(1)
    
    error_dir = sys.argv[1]
    project_name = sys.argv[2]
    
    result = check_errors(error_dir, project_name)
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
```

### 3. Hermes 定时任务配置

**Cron Job 设置：**

```python
# 每10分钟检查一次错误（无错误时 0 token）
cronjob(
    action="create",
    name="auto-debug-monitor",
    schedule="*/10 * * * *",
    script="check_errors.py",
    prompt="""
检查 {{output}} 中的错误报告。

如果 has_errors 为 false，直接返回"无错误"。
如果 has_errors 为 true：
1. 分析错误原因
2. 定位问题代码
3. 生成修复补丁
4. 应用修复
5. 通过飞书通知用户修复结果

错误目录：~/.hermes/auto-debug/{project_name}/
""",
    enabled_toolsets=["file", "terminal", "patch"]
)
```

## 集成指南

### Chrome 扩展集成（Manifest V3）

**⚠️ 关键限制（MV3）：**
- `chrome.downloads` 在 content script **不可用**，必须通过 service worker
- `URL.createObjectURL` 在 service worker **不可用**（无 DOM），用 data URL
- `const` 声明不挂到 `window`，跨文件访问用 `window.xxx`

**架构：**
```
content.js (错误捕获)
  → window.errorMonitor.captureError()
  → saveErrors()
  → chrome.runtime.sendMessage({ type: 'SAVE_ERROR_REPORT', reportData, filename })
  ↓
background.js (service worker)
  → chrome.downloads.download({ url: dataUrl, filename })
  ↓
~/Downloads/auto-debug-errors-{project}.json
  ↓
cron (check_errors.py) → 指纹去重 → 新错误才报告
```

**步骤 1：添加错误监控**

在 `manifest.json` 中添加 `error-monitor.js`：

```json
{
  "content_scripts": [
    {
      "matches": ["*://*.your-site.com/*"],
      "js": ["error-monitor.js", "content.js"],
      "run_at": "document_idle"
    }
  ],
  "background": {
    "service_worker": "background.js"
  },
  "permissions": ["downloads"]
}
```

**步骤 2：error-monitor.js（content script 中使用）**

```javascript
class ErrorMonitor {
    constructor() {
        this.errors = [];
        this.fixedErrors = new Set();
        this.maxErrors = 100;
        this.projectName = 'your-project-name';
        this.downloadFilename = `auto-debug-errors-${this.projectName}.json`;
        this.setupInterceptors();
    }

    setupInterceptors() {
        const originalError = console.error;
        console.error = (...args) => {
            this.captureError('console.error', args.join(' '));
            originalError.apply(console, args);
        };
        window.addEventListener('error', (event) => {
            this.captureError('uncaught', `${event.message} at ${event.filename}:${event.lineno}`);
        });
        window.addEventListener('unhandledrejection', (event) => {
            this.captureError('unhandledrejection', event.reason?.toString() || 'Unknown');
        });
    }

    captureError(type, message) {
        if (this.shouldIgnore(message)) return;
        const fingerprint = this.getFingerprint(type, message);
        if (this.fixedErrors.has(fingerprint)) return;
        this.errors.push({
            type, message: message.substring(0, 500),
            timestamp: new Date().toISOString(),
            url: window.location.href, fingerprint
        });
        if (this.errors.length > this.maxErrors) this.errors = this.errors.slice(-this.maxErrors);
        this.saveErrors();
    }

    getFingerprint(type, message) {
        const simplified = message
            .replace(/:\d+:\d+/g, '')
            .replace(/\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}/g, '')
            .substring(0, 200);
        let hash = 0;
        for (let i = 0; i < simplified.length; i++) {
            hash = ((hash << 5) - hash) + simplified.charCodeAt(i);
            hash = hash & hash;
        }
        return `${type}_${Math.abs(hash).toString(36)}`;
    }

    shouldIgnore(message) {
        return ['kQuotaBytes', 'Receiving end does not exist', 'message port closed']
            .some(p => message.includes(p));
    }

    async saveErrors() {
        try {
            // 保存到 IndexedDB（如果可用）
            if (typeof yourDB !== 'undefined' && yourDB.db) {
                const state = await yourDB.loadState();
                state.errorLog = this.errors;
                await yourDB.saveState(state);
            }

            if (this.errors.length === 0) return;
            const uniqueErrors = [];
            const seen = new Set();
            for (const error of this.errors) {
                const fp = error.fingerprint || this.getFingerprint(error.type, error.message);
                if (!seen.has(fp) && !this.fixedErrors.has(fp)) {
                    seen.add(fp);
                    uniqueErrors.push(error);
                }
            }
            if (uniqueErrors.length === 0) return;

            const report = {
                project: this.projectName,
                timestamp: new Date().toISOString(),
                errors: uniqueErrors.slice(-20),
                summary: { total: this.errors.length, unique: uniqueErrors.length }
            };

            // ✅ 通过 background.js 保存（content script 不能直接用 chrome.downloads）
            if (typeof chrome !== 'undefined' && chrome.runtime) {
                chrome.runtime.sendMessage({
                    type: 'SAVE_ERROR_REPORT',
                    reportData: report,
                    filename: this.downloadFilename
                }, (response) => {
                    if (chrome.runtime.lastError) {
                        console.error(`[AutoDebug] 保存失败: ${chrome.runtime.lastError.message}`);
                    }
                });
            }
        } catch (e) { /* 忽略保存错误 */ }
    }

    markAsFixed(fingerprint) {
        this.fixedErrors.add(fingerprint);
    }
}

// ✅ 用 window 确保跨文件可访问（const 不行）
try { window.errorMonitor = new ErrorMonitor(); }
catch (e) { window.errorMonitor = null; }
```

**步骤 3：background.js（service worker 中添加下载处理）**

```javascript
// 监听 content script 的错误报告保存请求
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.type === 'SAVE_ERROR_REPORT') {
        const { reportData, filename } = message;
        // ✅ service worker 用 data URL（不能用 URL.createObjectURL）
        const jsonStr = JSON.stringify(reportData, null, 2);
        const dataUrl = 'data:application/json;base64,' + btoa(unescape(encodeURIComponent(jsonStr)));
        chrome.downloads.download({
            url: dataUrl,
            filename: filename,
            saveAs: false,
            conflictAction: 'overwrite'
        }, (downloadId) => {
            if (chrome.runtime.lastError) {
                sendResponse({ success: false, error: chrome.runtime.lastError.message });
            } else {
                sendResponse({ success: true, downloadId });
            }
        });
        return true; // 保持 sendResponse 通道开放
    }
    return false;
});
```

**步骤 4：在采集代码中调用 errorMonitor**

```javascript
// 当捕获到错误时，显式通知 errorMonitor
try {
    const result = await doSomething();
} catch (e) {
    // 你的错误处理逻辑
    state.errors.push({ name, error: e.message });
    // ✅ 通知 errorMonitor 触发文件保存
    if (window.errorMonitor) {
        window.errorMonitor.captureError('my_error', `${name}: ${e.message}`);
    }
}
```

```javascript
// 连续错误检测
let consecutiveErrors = 0;
const MAX_CONSECUTIVE_ERRORS = 10;

async function collectWithRetry(name, stage, state) {
    try {
        const result = await collectCommunity(name, stage, state);
        consecutiveErrors = 0;
        return result;
    } catch (e) {
        consecutiveErrors++;
        
        if (consecutiveErrors >= MAX_CONSECUTIVE_ERRORS) {
            console.log(`[Collector] ⚠️ 连续 ${consecutiveErrors} 个错误，自动暂停`);
            state.isRunning = false;
            await saveState(state);
            throw new Error('连续错误过多，已暂停');
        }
        
        throw e;
    }
}
```

### Python 脚本集成

**步骤 1：添加错误上报**

```python
import json
import os
from datetime import datetime
from pathlib import Path

class ErrorMonitor:
    def __init__(self, project_name: str, error_dir: str = None):
        self.project_name = project_name
        self.error_dir = error_dir or f"~/.hermes/auto-debug/{project_name}"
        self.errors = []
        os.makedirs(os.path.expanduser(self.error_dir), exist_ok=True)
    
    def capture_error(self, error_type: str, message: str, details: dict = None):
        error = {
            "type": error_type,
            "message": str(message)[:500],
            "timestamp": datetime.now().isoformat(),
            "details": details
        }
        self.errors.append(error)
        self.save_errors()
    
    def save_errors(self):
        if not self.errors:
            return
        
        report = {
            "project": self.project_name,
            "timestamp": datetime.now().isoformat(),
            "errors": self.errors[-50:],  # 最近50个
            "summary": self.get_summary()
        }
        
        filepath = os.path.expanduser(f"{self.error_dir}/errors-{int(datetime.now().timestamp())}.json")
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
    
    def get_summary(self):
        from collections import Counter
        error_types = Counter(e["type"] for e in self.errors)
        return {
            "total": len(self.errors),
            "by_type": dict(error_types)
        }

# 使用示例
monitor = ErrorMonitor("my-scraper")

try:
    # 你的代码
    result = some_risky_operation()
except Exception as e:
    monitor.capture_error("operation_failed", str(e), {"context": "some context"})
```

### Node.js 服务集成

```javascript
const fs = require('fs');
const path = require('path');

class ErrorMonitor {
    constructor(projectName, errorDir = null) {
        this.projectName = projectName;
        this.errorDir = errorDir || path.join(process.env.HOME, '.hermes/auto-debug', projectName);
        this.errors = [];
        
        // 确保目录存在
        fs.mkdirSync(this.errorDir, { recursive: true });
        
        // 全局错误捕获
        process.on('uncaughtException', (error) => {
            this.captureError('uncaughtException', error.message, { stack: error.stack });
        });
        
        process.on('unhandledRejection', (reason) => {
            this.captureError('unhandledRejection', reason?.toString() || 'Unknown');
        });
    }
    
    captureError(type, message, details = null) {
        const error = {
            type,
            message: message.substring(0, 500),
            timestamp: new Date().toISOString(),
            details
        };
        
        this.errors.push(error);
        this.saveErrors();
    }
    
    saveErrors() {
        if (this.errors.length === 0) return;
        
        const report = {
            project: this.projectName,
            timestamp: new Date().toISOString(),
            errors: this.errors.slice(-50),
            summary: this.getSummary()
        };
        
        const filepath = path.join(this.errorDir, `errors-${Date.now()}.json`);
        fs.writeFileSync(filepath, JSON.stringify(report, null, 2));
    }
    
    getSummary() {
        const byType = {};
        for (const error of this.errors) {
            byType[error.type] = (byType[error.type] || 0) + 1;
        }
        return { total: this.errors.length, byType };
    }
}

module.exports = ErrorMonitor;
```

## 错误目录结构

```
~/.hermes/auto-debug/
├── {project-name-1}/
│   ├── errors-1714843200.json
│   ├── errors-1714843800.json
│   └── ...
├── {project-name-2}/
│   ├── errors-1714843200.json
│   └── ...
└── check_errors.py  (监控脚本)
```

## 错误报告格式

```json
{
  "project": "reddit-community-collector",
  "timestamp": "2026-05-05T18:30:00.000Z",
  "errors": [
    {
      "type": "console.error",
      "message": "HTTP 429: Too Many Requests",
      "timestamp": "2026-05-05T18:29:45.000Z",
      "url": "https://www.reddit.com/r/programming"
    }
  ],
  "summary": {
    "total": 15,
    "by_type": {
      "console.error": 10,
      "uncaught": 5
    }
  }
}
```

## 自动修复流程

```
1. Python 脚本检测到新错误文件
2. 输出 JSON 格式的错误摘要
3. Hermes Agent 分析错误模式
4. 定位问题代码（读取相关文件）
5. 生成修复补丁
6. 应用补丁（使用 patch 工具）
7. 验证修复（语法检查）
8. 通知用户修复结果
```

## Token 消耗分析

| 场景 | 消耗 | 说明 |
|------|------|------|
| 无错误 | **0 tokens** | Python 脚本直接返回 |
| 有错误 | 3000-5000 tokens | 分析 + 修复 |
| 复杂错误 | 5000-10000 tokens | 需要读取多个文件 |

**24小时无错误：** 0 tokens（纯脚本检查）
**24小时有10个错误：** ~50,000 tokens

## 最佳实践

1. **合理设置忽略规则**
   - 忽略已知的无害错误（如 Chrome 存储限制）
   - 避免误报干扰

2. **限制错误数量**
   - 保留最近 50-100 个错误
   - 避免错误文件过大

3. **分类处理**
   - 不同错误类型不同处理策略
   - 连续错误自动暂停

4. **定期清理**
   - 清理超过 7 天的错误文件
   - 保持错误目录整洁

5. **错误去重（重要！）**
   - 同一错误重复出现会导致重复分析，浪费 token
   - 使用错误指纹（fingerprint）去重
   - 修复后标记指纹为"已修复"，不再分析

## 错误去重（Fingerprinting）

**问题：** 同一错误出现 100 次 → 100 × 3000 tokens = 300,000 tokens 浪费

**解决方案：** 错误指纹 + 分析记录

### JavaScript 端（error-monitor.js）

```javascript
class ErrorMonitor {
    constructor() {
        this.errors = [];
        this.fixedErrors = new Set(); // 已修复的指纹
    }

    // 生成错误指纹
    getFingerprint(type, message) {
        const simplified = message
            .replace(/:\d+:\d+/g, '')           // 行列号
            .replace(/\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}/g, '') // 时间戳
            .replace(/[0-9a-f-]{36}/gi, '')     // UUID
            .substring(0, 200);
        let hash = 0;
        for (let i = 0; i < simplified.length; i++) {
            hash = ((hash << 5) - hash) + simplified.charCodeAt(i);
            hash = hash & hash;
        }
        return `${type}_${Math.abs(hash).toString(36)}`;
    }

    captureError(type, message) {
        const fingerprint = this.getFingerprint(type, message);
        if (this.fixedErrors.has(fingerprint)) return; // 跳过已修复
        // ... 保存错误（含 fingerprint）
    }

    markAsFixed(fingerprint) {
        this.fixedErrors.add(fingerprint);
        this.saveFixedErrors(); // 持久化到 IndexedDB
    }
}
```

### Python 端（check_errors.py）

`check_errors.py` 支持：
- 检查 `~/.hermes/auto-debug/{project}/` 目录
- 检查 `~/Downloads/auto-debug-errors-{project}.json`（Chrome 扩展输出）
- 指纹去重：同一类错误只报告一次
- 分析后自动删除 Downloads 文件

```python
ANALYZED_FILE = "analyzed_fingerprints.json"
DOWNLOADS_DIR = Path.home() / "Downloads"

def load_analyzed_fingerprints(project_name):
    """加载已分析的指纹"""
    path = Path(f"~/.hermes/auto-debug/{project_name}") / ANALYZED_FILE
    if path.exists():
        return set(json.loads(path.read_text()).get("fingerprints", []))
    return set()

def save_analyzed_fingerprints(project_name, fingerprints):
    """保存已分析的指纹（最多500个）"""
    path = Path(f"~/.hermes/auto-debug/{project_name}") / ANALYZED_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"fingerprints": sorted(fingerprints)[-500:]}, indent=2))

def check_errors(error_dir, project_name):
    analyzed = load_analyzed_fingerprints(project_name)
    downloads_file = DOWNLOADS_DIR / f"auto-debug-errors-{project_name}.json"

    # 收集所有错误（从 error_dir 和 Downloads）
    all_errors = collect_from_dir(error_dir) + collect_from_file(downloads_file)

    # 指纹去重
    new_errors = [e for e in all_errors if e.get("fingerprint", "") not in analyzed]
    if not new_errors:
        if downloads_file.exists(): downloads_file.unlink()  # 清理
        return {"has_errors": False, "message": "全部已分析"}

    # 保存指纹 + 删除 Downloads 文件
    new_fps = {e["fingerprint"] for e in new_errors if e.get("fingerprint")}
    save_analyzed_fingerprints(project_name, analyzed | new_fps)
    if downloads_file.exists(): downloads_file.unlink()

    return {"has_errors": True, "errors": new_errors[:20]}
```

**Token 节省：** 同一错误 × 100 次 = 3,000 tokens（而非 300,000）

## Downloads 文件自动清理

cron 脚本分析完错误后自动删除 `~/Downloads/auto-debug-errors-*.json`：
- 有新错误 → 报告 + 保存指纹 + 删除文件
- 全部已分析 → `has_errors: false` + 删除文件
- 文件只在错误发生到下次 cron 检查之间存在（最多 10 分钟）

## 故障排除

**问题：错误文件没有生成**
- 确认 `error-monitor.js` 中使用 `window.errorMonitor`（不是 `const`）
- 确认通过 `chrome.runtime.sendMessage` 发送给 `background.js`（content script 不能直接用 `chrome.downloads`）
- 确认 `background.js` 使用 data URL（service worker 不能用 `URL.createObjectURL`）
- 检查浏览器控制台是否有报错

**问题：Python 脚本找不到错误文件**
- 确认错误目录路径正确
- 同时检查 `~/Downloads/auto-debug-errors-{project}.json`
- 检查文件扩展名是否为 `.json`
- 确认文件修改时间在检查范围内

**问题：同一错误被重复分析**
- 确认 `check_errors.py` 使用指纹去重（`analyzed_fingerprints.json`）
- 检查错误的 `fingerprint` 字段是否存在
- 指纹文件最多保留 500 个，旧的自动淘汰

**问题：自动修复失败**
- 检查文件权限
- 确认补丁格式正确
- 查看 Hermes 日志获取详细错误

## 相关技能

- `systematic-debugging` - 系统性调试方法
- `test-driven-development` - 测试驱动开发
- `requesting-code-review` - 代码审查流程

---

**最后更新：** 2026-05-06
**版本：** 1.1.0
**作者：** Hermes Agent
