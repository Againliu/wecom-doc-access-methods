#!/usr/bin/env python3
"""工具函数 — GitHub issue 自动反馈等"""

from __future__ import annotations

from pathlib import Path

def _auto_report(title, error_detail="", context=None):
    """遇到关键错误时自动在 GitHub 创建 issue"""
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "report_issue",
            Path(__file__).resolve().parent.parent / "report_issue.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.auto_report_issue(title, error_detail, context or {})
    except Exception:
        pass  # 不让 issue 反馈本身影响主流程
