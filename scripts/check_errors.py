#!/usr/bin/env python3
"""
Auto-Debug 错误检查脚本
用法：python check_errors.py <错误目录> <项目名称>
输出：JSON 格式的错误摘要，供 Hermes Agent 分析

特性：
- 无错误时 0 token 消耗（直接返回）
- 有错误时输出详细报告供 LLM 分析
- 支持多个项目的错误监控
"""

import os
import sys
import json
from datetime import datetime, timedelta
from pathlib import Path

def check_errors(error_dir: str, project_name: str) -> dict:
    """检查错误目录中的新错误"""
    
    error_path = Path(os.path.expanduser(error_dir))
    if not error_path.exists():
        return {
            "has_errors": False,
            "project": project_name,
            "message": f"错误目录不存在: {error_dir}"
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
    all_errors = []
    
    for error_file in recent_errors:
        if "data" in error_file:
            errors = error_file["data"].get("errors", [])
            total_errors += len(errors)
            for error in errors:
                error_type = error.get("type", "unknown")
                error_types[error_type] = error_types.get(error_type, 0) + 1
                all_errors.append(error)
    
    # 按时间排序，取最近的错误
    all_errors.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    
    return {
        "has_errors": True,
        "project": project_name,
        "total_errors": total_errors,
        "error_types": error_types,
        "recent_files": len(recent_errors),
        "errors": all_errors[:20],  # 最多输出20个
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
