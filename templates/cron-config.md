# Auto-Debug 定时任务配置模板

## 基本配置

```python
# 每10分钟检查一次错误（无错误时 0 token）
cronjob(
    action="create",
    name="auto-debug-{project_name}",
    schedule="*/10 * * * *",
    script="~/.hermes/scripts/check_errors.py ~/.hermes/auto-debug/{project_name} {project_name}",
    prompt="""
检查 {{output}} 中的错误报告。

如果 has_errors 为 false，直接返回"无错误"。
如果 has_errors 为 true：
1. 分析错误原因
2. 定位问题代码
3. 生成修复补丁
4. 应用修复
5. 通知用户修复结果

项目路径：{project_path}
错误目录：~/.hermes/auto-debug/{project_name}/
""",
    enabled_toolsets=["file", "terminal", "patch"]
)
```

## 多项目配置

```python
# 项目1：Reddit 社区采集器
cronjob(
    action="create",
    name="auto-debug-reddit-collector",
    schedule="*/10 * * * *",
    script="~/.hermes/scripts/check_errors.py ~/.hermes/auto-debug/reddit-collector reddit-collector",
    prompt="...",
    enabled_toolsets=["file", "terminal", "patch"]
)

# 项目2：Chrome 翻译插件
cronjob(
    action="create",
    name="auto-debug-translator",
    schedule="*/15 * * * *",  # 每15分钟检查一次
    script="~/.hermes/scripts/check_errors.py ~/.hermes/auto-debug/translator translator",
    prompt="...",
    enabled_toolsets=["file", "terminal", "patch"]
)
```

## 自定义检查频率

```python
# 每5分钟检查（高频，适合关键任务）
schedule="*/5 * * * *"

# 每30分钟检查（低频，适合非关键任务）
schedule="*/30 * * * *"

# 每小时检查（最低频）
schedule="0 * * * *"

# 只在工作时间检查（9-18点）
schedule="*/10 9-18 * * *"
```

## 错误处理策略

### 策略1：自动修复（推荐）

```python
prompt="""
检查 {{output}} 中的错误报告。

如果 has_errors 为 false，直接返回"无错误"。
如果 has_errors 为 true：
1. 分析错误原因
2. 定位问题代码
3. 生成修复补丁
4. 自动应用修复
5. 验证修复成功
6. 通知用户修复结果
"""
```

### 策略2：通知用户确认

```python
prompt="""
检查 {{output}} 中的错误报告。

如果 has_errors 为 false，直接返回"无错误"。
如果 has_errors 为 true：
1. 分析错误原因
2. 生成修复方案
3. 通知用户，等待确认
4. 用户确认后应用修复
"""
```

### 策略3：仅报告

```python
prompt="""
检查 {{output}} 中的错误报告。

如果 has_errors 为 false，直接返回"无错误"。
如果 has_errors 为 true：
1. 汇总错误信息
2. 生成错误报告
3. 通知用户
"""
```

## 通知配置

### 飞书通知

```python
prompt="""
...
修复完成后，通过飞书通知用户：
- 修复了什么问题
- 修改了哪些文件
- 修复是否成功
"""
```

### 本地通知

```python
prompt="""
...
修复完成后，保存修复日志到：
~/.hermes/auto-debug/{project_name}/fix-log.txt
"""
```

## 监控脚本路径

```
~/.hermes/scripts/check_errors.py          # 主检查脚本
~/.hermes/auto-debug/{project_name}/       # 错误文件目录
~/.hermes/auto-debug/{project_name}/fix-log.txt  # 修复日志
```
