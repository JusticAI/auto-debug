#!/usr/bin/env python3
"""
Auto-Debug 错误检查脚本（带指纹去重）
用法：python check_errors.py <错误目录> <项目名称>
输出：JSON 格式的错误摘要，供 Hermes Agent 分析

特性：
- 无错误时 0 token 消耗（直接返回）
- 有错误时输出详细报告供 LLM 分析
- 指纹去重：同一类错误只报告一次，避免重复分析浪费 token
- 同时检查 Downloads 目录（Chrome 扩展的固定文件名输出）
"""

import os
import sys
import json
from datetime import datetime, timedelta
from pathlib import Path

DOWNLOADS_DIR = Path.home() / "Downloads"

def load_analyzed_fingerprints(project_name: str) -> set:
    """加载已分析的错误指纹"""
    fp_file = Path(os.path.expanduser(f"~/.hermes/auto-debug/{project_name}"))
    fp_file = fp_file / "analyzed_fingerprints.json"
    if fp_file.exists():
        try:
            data = json.loads(fp_file.read_text())
            return set(data.get("fingerprints", []))
        except:
            pass
    return set()

def save_analyzed_fingerprints(project_name: str, fingerprints: set):
    """保存已分析的错误指纹"""
    fp_dir = Path(os.path.expanduser(f"~/.hermes/auto-debug/{project_name}"))
    fp_dir.mkdir(parents=True, exist_ok=True)
    fp_file = fp_dir / "analyzed_fingerprints.json"
    # 只保留最近 500 个指纹，防止文件无限增长
    fp_list = sorted(fingerprints)[-500:]
    fp_file.write_text(json.dumps({
        "fingerprints": fp_list,
        "updated": datetime.now().isoformat()
    }, indent=2))

def check_errors(error_dir: str, project_name: str) -> dict:
    """检查错误目录中的新错误（带指纹去重）"""
    
    error_path = Path(os.path.expanduser(error_dir))
    all_recent_errors = []
    
    # 来源1: 原始错误目录
    if error_path.exists():
        cutoff = datetime.now() - timedelta(hours=1)
        for error_file in error_path.glob("*.json"):
            if error_file.name == "analyzed_fingerprints.json":
                continue
            try:
                mtime = datetime.fromtimestamp(error_file.stat().st_mtime)
                if mtime > cutoff:
                    with open(error_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        all_recent_errors.append({
                            "source": str(error_path),
                            "file": error_file.name,
                            "modified": mtime.isoformat(),
                            "data": data
                        })
            except Exception as e:
                all_recent_errors.append({
                    "source": str(error_path),
                    "file": error_file.name,
                    "error": str(e)
                })
    
    # 来源2: Downloads 目录
    downloads_file = DOWNLOADS_DIR / f"auto-debug-errors-{project_name}.json"
    if downloads_file.exists():
        try:
            mtime = datetime.fromtimestamp(downloads_file.stat().st_mtime)
            cutoff_dl = datetime.now() - timedelta(hours=24)
            if mtime > cutoff_dl:
                with open(downloads_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    all_recent_errors.append({
                        "source": str(DOWNLOADS_DIR),
                        "file": downloads_file.name,
                        "modified": mtime.isoformat(),
                        "data": data
                    })
        except Exception as e:
            all_recent_errors.append({
                "source": str(DOWNLOADS_DIR),
                "file": downloads_file.name,
                "error": str(e)
            })
    
    if not all_recent_errors:
        return {
            "has_errors": False,
            "project": project_name,
            "message": "最近无错误"
        }
    
    # 收集所有错误和指纹
    all_errors = []
    for error_file in all_recent_errors:
        if "data" in error_file:
            for error in error_file["data"].get("errors", []):
                all_errors.append(error)
    
    if not all_errors:
        return {
            "has_errors": False,
            "project": project_name,
            "message": "无错误详情"
        }
    
    # 指纹去重：过滤掉已分析的错误
    analyzed_fps = load_analyzed_fingerprints(project_name)
    new_errors = []
    new_fps = set()
    
    for error in all_errors:
        fp = error.get("fingerprint", "")
        if fp and fp in analyzed_fps:
            continue  # 跳过已分析
        new_errors.append(error)
        if fp:
            new_fps.add(fp)
    
    if not new_errors:
        # 全部已分析，删除 Downloads 文件
        if downloads_file.exists():
            try:
                downloads_file.unlink()
            except:
                pass
        return {
            "has_errors": False,
            "project": project_name,
            "message": f"所有 {len(all_errors)} 个错误均已分析过（去重）"
        }
    
    # 有新错误：保存指纹，输出报告
    all_fps = analyzed_fps | new_fps
    save_analyzed_fingerprints(project_name, all_fps)
    
    # 删除 Downloads 中的错误文件（已分析完毕）
    if downloads_file.exists():
        try:
            downloads_file.unlink()
        except:
            pass
    
    # 汇总
    error_types = {}
    for error in new_errors:
        error_type = error.get("type", "unknown")
        error_types[error_type] = error_types.get(error_type, 0) + 1
    
    new_errors.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    
    return {
        "has_errors": True,
        "project": project_name,
        "total_errors": len(new_errors),
        "skipped_duplicates": len(all_errors) - len(new_errors),
        "error_types": error_types,
        "errors": new_errors[:20],
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
