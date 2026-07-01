#!/usr/bin/env python3
"""常量定义 — 企微文档字段类型、URL 映射、DOM 选择器等"""

from __future__ import annotations

import os
from pathlib import Path
from datetime import timezone, timedelta

__version__ = "4.5.0"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 常量
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

DEFAULT_STATE_DIR = os.environ.get("WECOM_STATE_DIR", "./wecom_states")
# 向后兼容：老版共享状态文件路径（无用户隔离）
LEGACY_SHARED_STATE = "/root/.hermes/workspace/wecom_browser_state.json"
_TZ_CN = timezone(timedelta(hours=8))

# URL 前缀 → 文档类型
_URL_PREFIX_TO_TYPE = {
    "s3": "smartsheet",   # 智能表格
    "w3": "doc",          # 微文档
    "e3": "sheet",        # 旧格式电子表格
    "m4": "mind",         # 思维导图
}

# dop-api 字段类型 ID
_FIELD_TYPE_TEXT = 1
_FIELD_TYPE_USER = 10        # 创建人
_FIELD_TYPE_EDITOR = 11      # 最后编辑人
_FIELD_TYPE_CREATED_AT = 12  # 创建时间
_FIELD_TYPE_UPDATED_AT = 13  # 最后编辑时间
_FIELD_TYPE_SELECT = 17      # 单选
_FIELD_TYPE_FORMULA = 19     # 公式/引用

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 自动重试配置（环境变量可覆盖）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RETRY_MAX_ATTEMPTS = int(os.environ.get("WECOM_RETRY_MAX", "3"))   # 总尝试次数（含首次）
RETRY_BASE_DELAY = float(os.environ.get("WECOM_RETRY_DELAY", "2"))  # 基础延迟秒数，指数退避（2s, 4s, 6s...）
RETRY_SHEET_MAX = int(os.environ.get("WECOM_RETRY_SHEET_MAX", "2"))  # 单子表重试次数（不含首次）

# 不可重试的错误关键词（认证/权限类，重试也没用）
_NON_RETRYABLE_KEYWORDS = (
    "cookies 已过期", "访问权限", "未登录", "无法解析 URL",
    "无法解析 doc_id", "无法解析", "需重新登录",
)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# URL 解析
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


# DOM 选择器列表 — 覆盖所有文档类型
_DOM_SELECTORS = """() => {
    const selectors = [
        '.ne-doc-content', '.ne-viewer-body', '.ne-editor',
        '.doc-content', '.lake-engine', '.ql-editor',
        '.article-content', '.editor-content',
        '[class*="sheet-cell"]', '[class*="grid-container"]',
        '[class*="mind-node"]', '[class*="flowchart"]',
        '[class*="slide-content"]', '[class*="form-content"]',
        '.smartsheet-container', '.sheet-container'
    ];
    for (const sel of selectors) {
        const el = document.querySelector(sel);
        if (el && el.innerText.length > 10) {
            return { selector: sel, text: el.innerText, success: true };
        }
    }
    return {
        selector: 'body',
        text: document.body?.innerText?.substring(0, 100000) || '',
        success: document.body?.innerText?.length > 50
    };
}"""
