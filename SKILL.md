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
- 指纹去重：同一类错误只分析一次，避免重复浪费

## 架构

```
应用/扩展 (运行中)
  → 捕获错误 → 保存到 ~/Downloads/auto-debug-errors-{project}.json
                                    ↓
cron 每10分钟 → check_errors.py → 指纹去重 → 新错误才报告
                                    ↓
                            LLM 分析 → 自动修复
```

## 组件

### 1. 错误监控模块 (error-monitor.js)

适用于 Chrome 扩展，自动捕获所有错误。

**⚠️ Chrome MV3 关键限制（踩坑经验）：**
- `chrome.downloads` 在 content script **不可用**，必须通过 service worker
- `URL.createObjectURL` 在 service worker **不可用**（无 DOM），用 data URL
- `const` 声明不挂到 `window`，跨文件访问必须用 `window.xxx`
- `console.error` 拦截器不会捕获 `try/catch` 里用 `console.log` 记录的错误——必须显式调用 `captureError()`

**manifest.json 配置：**

```json
{
  "content_scripts": [{
    "matches": ["*://*.your-site.com/*"],
    "js": ["error-monitor.js", "content.js"],
    "run_at": "document_idle"
  }],
  "background": {
    "service_worker": "background.js"
  },
  "permissions": ["downloads"]
}
```

**error-monitor.js（content script）：**

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
        const orig = console.error;
        console.error = (...args) => {
            this.captureError('console.error', args.join(' '));
            orig.apply(console, args);
        };
        window.addEventListener('error', (e) => {
            this.captureError('uncaught', `${e.message} at ${e.filename}:${e.lineno}`);
        });
        window.addEventListener('unhandledrejection', (e) => {
            this.captureError('unhandledrejection', e.reason?.toString() || 'Unknown');
        });
    }

    captureError(type, message) {
        if (this.shouldIgnore(message)) return;
        const fp = this.getFingerprint(type, message);
        if (this.fixedErrors.has(fp)) return;
        this.errors.push({
            type, message: message.substring(0, 500),
            timestamp: new Date().toISOString(),
            url: window.location.href, fingerprint: fp
        });
        if (this.errors.length > this.maxErrors) this.errors = this.errors.slice(-this.maxErrors);
        this.saveErrors();
    }

    getFingerprint(type, message) {
        // 归一化：去掉变量部分（如名称、ID），只保留错误模式
        let s = message
            .replace(/:\d+:\d+/g, '')                          // 行列号
            .replace(/\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}/g, '') // 时间戳
            .replace(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/gi, '') // UUID
            // 去掉前缀名称（如 "CommunityName: about_error:" → "about_error:"）
            .replace(/^[^:]+:\s*(?=about_error|rules_error|HTTP \d)/, '')
            .substring(0, 200);
        let hash = 0;
        for (let i = 0; i < s.length; i++) hash = ((hash << 5) - hash) + s.charCodeAt(i);
        return `${type}_${(hash >>> 0).toString(36)}`;
    }

    shouldIgnore(msg) {
        return ['kQuotaBytes', 'Receiving end does not exist', 'message port closed']
            .some(p => msg.includes(p));
    }

    async saveErrors() {
        try {
            if (this.errors.length === 0) return;
            const seen = new Set();
            const unique = this.errors.filter(e => {
                const fp = e.fingerprint || this.getFingerprint(e.type, e.message);
                if (seen.has(fp) || this.fixedErrors.has(fp)) return false;
                seen.add(fp); return true;
            }).slice(-20);
            if (unique.length === 0) return;
            const report = {
                project: this.projectName, timestamp: new Date().toISOString(),
                errors: unique, summary: { total: this.errors.length, unique: unique.length }
            };
            // ✅ 通过 background.js 保存（content script 不能用 chrome.downloads）
            if (chrome?.runtime) {
                chrome.runtime.sendMessage({
                    type: 'SAVE_ERROR_REPORT', reportData: report, filename: this.downloadFilename
                }, () => { if (chrome.runtime.lastError) {} });
            }
        } catch (e) { /* 忽略 */ }
    }

    markAsFixed(fp) { this.fixedErrors.add(fp); }
}

// ✅ 用 window 暴露（const 不行）
try { window.errorMonitor = new ErrorMonitor(); } catch (e) { window.errorMonitor = null; }
```

**background.js（service worker）：**

```javascript
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.type === 'SAVE_ERROR_REPORT') {
        const { reportData, filename } = message;
        // ✅ service worker 用 data URL（URL.createObjectURL 不可用）
        const jsonStr = JSON.stringify(reportData, null, 2);
        const dataUrl = 'data:application/json;base64,' + btoa(unescape(encodeURIComponent(jsonStr)));
        chrome.downloads.download({
            url: dataUrl, filename, saveAs: false, conflictAction: 'overwrite'
        }, (downloadId) => {
            sendResponse({ success: !chrome.runtime.lastError, error: chrome.runtime.lastError?.message });
        });
        return true; // 保持 sendResponse 通道开放
    }
});
```

**在采集代码中显式通知 errorMonitor：**

```javascript
// errorMonitor 的 console.error 拦截器不会捕获 try/catch 里的错误！
// 必须显式调用：
try {
    const result = await fetchJSON(url);
} catch (e) {
    state.errors.push({ name, error: e.message });
    if (window.errorMonitor) {
        window.errorMonitor.captureError('collector_error', `${name}: ${e.message}`);
    }
}
```

### 2. Python 监控脚本 (check_errors.py)

**位置：** `~/.hermes/scripts/check_errors.py`

**功能：**
- 检查 `~/.hermes/auto-debug/{project}/` 和 `~/Downloads/` 两个位置
- 指纹去重：同一类错误只报告一次
- 分析后自动删除 Downloads 文件

```python
#!/usr/bin/env python3
"""
Auto-Debug 错误检查脚本（带指纹去重）
用法：python check_errors.py <错误目录> <项目名称>
"""

import os, sys, json
from datetime import datetime, timedelta
from pathlib import Path

DOWNLOADS_DIR = Path.home() / "Downloads"

def load_analyzed_fingerprints(project_name):
    fp_file = Path(os.path.expanduser(f"~/.hermes/auto-debug/{project_name}")) / "analyzed_fingerprints.json"
    if fp_file.exists():
        try: return set(json.loads(fp_file.read_text()).get("fingerprints", []))
        except: pass
    return set()

def save_analyzed_fingerprints(project_name, fingerprints):
    fp_dir = Path(os.path.expanduser(f"~/.hermes/auto-debug/{project_name}"))
    fp_dir.mkdir(parents=True, exist_ok=True)
    (fp_dir / "analyzed_fingerprints.json").write_text(json.dumps({
        "fingerprints": sorted(fingerprints)[-500:],
        "updated": datetime.now().isoformat()
    }, indent=2))

def check_errors(error_dir, project_name):
    error_path = Path(os.path.expanduser(error_dir))
    downloads_file = DOWNLOADS_DIR / f"auto-debug-errors-{project_name}.json"
    all_errors = []

    # 收集错误（从两个来源）
    for src in ([error_path] if error_path.exists() else []):
        for f in src.glob("*.json"):
            if f.name == "analyzed_fingerprints.json": continue
            try:
                if datetime.fromtimestamp(f.stat().st_mtime) > datetime.now() - timedelta(hours=1):
                    all_errors.extend(json.loads(f.read_text()).get("errors", []))
            except: pass
    if downloads_file.exists():
        try:
            if datetime.fromtimestamp(downloads_file.stat().st_mtime) > datetime.now() - timedelta(hours=24):
                all_errors.extend(json.loads(downloads_file.read_text()).get("errors", []))
        except: pass

    if not all_errors:
        return {"has_errors": False, "project": project_name, "message": "最近无错误"}

    # 指纹去重
    analyzed = load_analyzed_fingerprints(project_name)
    new_errors = [e for e in all_errors if e.get("fingerprint", "") not in analyzed]

    if not new_errors:
        if downloads_file.exists(): downloads_file.unlink()  # 清理
        return {"has_errors": False, "project": project_name, "message": f"全部 {len(all_errors)} 个错误已分析过"}

    # 保存指纹 + 清理 Downloads
    save_analyzed_fingerprints(project_name, analyzed | {e["fingerprint"] for e in new_errors if e.get("fingerprint")})
    if downloads_file.exists(): downloads_file.unlink()

    types = {}
    for e in new_errors: types[e.get("type", "unknown")] = types.get(e.get("type", "unknown"), 0) + 1
    new_errors.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    return {"has_errors": True, "project": project_name, "total_errors": len(new_errors),
            "skipped_duplicates": len(all_errors) - len(new_errors), "error_types": types,
            "errors": new_errors[:20], "timestamp": datetime.now().isoformat()}

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(json.dumps({"has_errors": False, "error": "用法: check_errors.py <错误目录> <项目名称>"}))
        sys.exit(1)
    print(json.dumps(check_errors(sys.argv[1], sys.argv[2]), ensure_ascii=False, indent=2))
```

### 3. Hermes 定时任务配置

```python
cronjob(
    action="create",
    name="auto-debug-monitor",
    schedule="*/10 * * * *",
    script="check_errors.py",
    prompt="""
检查 {{output}} 中的错误报告。
如果 has_errors 为 false，直接返回"无错误"。
如果 has_errors 为 true：分析错误原因，定位问题代码，生成修复补丁，应用修复，通知用户。
""",
    enabled_toolsets=["file", "terminal", "patch"]
)
```

## 指纹去重详解

**问题：** 同类错误（如多个社区返回 404）因消息内容不同而生成不同指纹，导致重复分析浪费 token。

**解决方案：** 归一化消息后再哈希。

```javascript
// 归一化前：每个社区名产生不同指纹
"AskWhateverYaWant: about_error: HTTP 404"  → fingerprint_abc
"GlobalLawyersHub: about_error: HTTP 404"    → fingerprint_xyz

// 归一化后：去掉社区名，共享同一指纹
"about_error: HTTP 404"  → fingerprint_123 (全部相同)
```

归一化规则（`getFingerprint` 中）：
- 去掉行列号、时间戳、UUID
- 去掉前缀名称：`^[^:]+:\s*(?=about_error|rules_error|HTTP \d)`
- 限制长度 200 字符

## Token 消耗分析

| 场景 | 消耗 | 说明 |
|------|------|------|
| 无错误 | **0 tokens** | Python 脚本直接返回 |
| 新错误类型 | 3000-5000 tokens | 分析 + 修复 |
| 重复错误 | **0 tokens** | 指纹去重跳过 |

## Chrome MV3 错误监控踩坑记录

以下是实际调试中发现的问题，按出现顺序排列：

### 问题1：chrome.downloads 在 content script 不可用
**症状**：`chrome` 对象存在，`chrome.downloads` 是 `undefined`
**原因**：Manifest V3 中 `chrome.downloads` 只在 service worker（background.js）可用
**解决**：content script 通过 `chrome.runtime.sendMessage` 发给 background.js 执行下载

### 问题2：URL.createObjectURL 在 service worker 不可用
**症状**：`Uncaught TypeError: URL.createObjectURL is not a function`
**原因**：Service worker 没有 DOM，Blob URL API 不可用
**解决**：用 data URL 替代：`'data:application/json;base64,' + btoa(unescape(encodeURIComponent(jsonStr)))`

### 问题3：const 不挂到 window
**症状**：`typeof errorMonitor` 返回 `undefined`（在其他文件或 console 中）
**原因**：`const` 声明的变量在 content script 的作用域中，不暴露到 `window` 对象
**解决**：用 `window.errorMonitor = new ErrorMonitor()` 替代 `const errorMonitor = ...`

### 问题4：errorMonitor 和采集器错误处理脱节
**症状**：采集器捕获了错误但 errorMonitor 没有记录，Downloads 文件不生成
**原因**：采集器用 `console.log` 记录错误，而 errorMonitor 只拦截 `console.error`
**解决**：在采集器的 catch 块中显式调用 `window.errorMonitor.captureError(type, message)`

### 问题5：指纹过于细粒度导致重复分析
**症状**：100 个不同社区的 404 被当成 100 个"新错误"
**原因**：指纹哈希包含了社区名（`"CommunityA: HTTP 404"` ≠ `"CommunityB: HTTP 404"`）
**解决**：在 `getFingerprint` 中归一化消息，去掉变量部分：
```javascript
.replace(/^[^:]+:\s*(?=about_error|rules_error|HTTP \d{3})/, '')
```
这样所有 `"XXX: about_error: HTTP 404"` 都归一化为 `"about_error: HTTP 404"`，共享同一指纹。

### 正确的 MV3 架构
```
content.js:
  window.errorMonitor.captureError(type, message)
  → saveErrors()
  → chrome.runtime.sendMessage({ type: 'SAVE_ERROR_REPORT', reportData, filename })

background.js:
  chrome.runtime.onMessage → chrome.downloads.download({ url: dataUrl, filename })

check_errors.py:
  检查 ~/Downloads/ → 指纹去重 → 新错误才报告 → 删除文件
```

## 故障排除

**错误文件没有生成：**
1. `error-monitor.js` 是否用 `window.errorMonitor`（不是 `const`）
2. 是否通过 `chrome.runtime.sendMessage` 发给 background.js
3. catch 块里是否显式调用 `window.errorMonitor.captureError()`
4. 检查浏览器下载栏是否有被拦截的下载

**同一错误被重复分析：**
- 确认 `getFingerprint()` 包含消息归一化逻辑
- 检查 `analyzed_fingerprints.json` 是否存在
- 归一化正则是否匹配你的错误消息格式

**errorMonitor 报 undefined：**
- DevTools Console 上下文需切换到 extension（不是 "top"）
- `error-monitor.js` 必须在 manifest 中排在 `content.js` 之前
- 异步初始化必须包在 `try/catch` 里

---

**最后更新：** 2026-05-06
**版本：** 1.1.0
