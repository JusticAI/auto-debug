/**
 * 通用错误监控器 - Chrome 扩展版
 * 
 * 功能：
 * - 拦截 console.error
 * - 捕获未处理异常
 * - 捕获 Promise 拒绝
 * - 自动保存到 IndexedDB
 * - 生成错误报告
 * 
 * 使用方法：
 * 1. 在 manifest.json 中添加此文件
 * 2. 在 content.js 中初始化：const monitor = new ErrorMonitor({...})
 * 3. 配置 saveCallback 保存错误到指定位置
 */

class ErrorMonitor {
    /**
     * @param {Object} options
     * @param {string} options.projectName - 项目名称
     * @param {number} options.maxErrors - 最大错误数量（默认100）
     * @param {string[]} options.ignorePatterns - 忽略的错误模式
     * @param {Function} options.saveCallback - 保存回调函数
     */
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
        // 过滤无用的错误
        if (this.shouldIgnore(message)) return;

        const error = {
            type,
            message: message.substring(0, 500), // 限制长度
            timestamp: new Date().toISOString(),
            url: window.location.href,
        };

        this.errors.push(error);

        // 限制错误数量
        if (this.errors.length > this.maxErrors) {
            this.errors = this.errors.slice(-this.maxErrors);
        }

        // 保存错误
        this.saveErrors();
    }

    shouldIgnore(message) {
        return this.ignorePatterns.some(pattern => message.includes(pattern));
    }

    async saveErrors() {
        if (this.saveCallback) {
            try {
                await this.saveCallback(this.errors);
            } catch (e) {
                // 忽略保存错误，避免无限循环
            }
        }
    }

    getErrors() {
        return this.errors;
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
        const recentErrors = this.getErrorsSince(60); // 最近1小时

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

// 导出（支持 CommonJS 和 ES Module）
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ErrorMonitor;
}
