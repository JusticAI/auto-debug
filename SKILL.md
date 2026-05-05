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

### Chrome 扩展集成

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
  ]
}
```

**步骤 2：配置保存回调**

在 `content.js` 中配置错误保存：

```javascript
// 初始化错误监控器
const errorMonitor = new ErrorMonitor({
    projectName: 'your-extension-name',
    maxErrors: 100,
    ignorePatterns: [
        'kQuotaBytes',           // Chrome 存储限制
        'Receiving end does not exist',  // 消息通道
    ],
    saveCallback: async (errors) => {
        // 保存到 IndexedDB
        if (typeof collectorDB !== 'undefined') {
            const state = await collectorDB.loadState();
            state.errorLog = errors;
            await collectorDB.saveState(state);
        }
        
        // 同时保存到文件（通过 downloads API）
        const report = {
            timestamp: new Date().toISOString(),
            errors: errors.slice(-50),  // 最近50个
            summary: errorMonitor.getErrorSummary()
        };
        
        const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        
        // 触发下载（保存到指定目录）
        chrome.downloads.download({
            url: url,
            filename: `~/.hermes/auto-debug/your-project/errors-${Date.now()}.json`,
            saveAs: false
        });
    }
});
```

**步骤 3：添加自动恢复逻辑**

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

```python
ANALYZED_FILE = "analyzed_errors.json"

def load_analyzed_errors(error_dir):
    """加载已分析的指纹"""
    path = Path(error_dir) / ANALYZED_FILE
    if path.exists():
        return set(json.loads(path.read_text()).get("fingerprints", []))
    return set()

def check_errors(error_dir, project_name):
    analyzed = load_analyzed_errors(error_dir)
    new_errors = []
    
    for error in all_errors:
        fp = error.get("fingerprint", "")
        if fp and fp in analyzed:
            continue  # 跳过已分析
        new_errors.append(error)
    
    # 保存新分析的指纹
    for error in new_errors:
        analyzed.add(error.get("fingerprint", ""))
    save_analyzed_errors(error_dir, analyzed)
    
    return {"has_errors": bool(new_errors), "errors": new_errors}
```

### 修复后标记

LLM 修复 bug 后，通过 message handler 标记为已修复：
```javascript
chrome.tabs.sendMessage(tab.id, {
    type: 'MARK_ERROR_FIXED',
    fingerprint: error.fingerprint
});
```

**Token 节省：** 同一错误 × 100 次 = 3,000 tokens（而非 300,000）

## 故障排除

**问题：错误文件没有生成**
- 检查目录权限
- 确认 saveCallback 正确配置
- 检查浏览器控制台是否有报错

**问题：Python 脚本找不到错误文件**
- 确认错误目录路径正确
- 检查文件扩展名是否为 `.json`
- 确认文件修改时间在检查范围内

**问题：自动修复失败**
- 检查文件权限
- 确认补丁格式正确
- 查看 Hermes 日志获取详细错误

## 相关技能

- `systematic-debugging` - 系统性调试方法
- `test-driven-development` - 测试驱动开发
- `requesting-code-review` - 代码审查流程

---

**最后更新：** 2026-05-05
**版本：** 1.0.0
**作者：** Hermes Agent
