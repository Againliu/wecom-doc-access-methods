#!/usr/bin/env python3
"""
wecom_doc_reader — 企微文档浏览器读取库（用户隔离版）

通过 Playwright 浏览器自动化读取企业微信文档（doc.weixin.qq.com）。
每个用户独立 storage_state，独立 cookies 管理。

支持的文档类型:
  ┌─────────────┬──────────┬───────────────────────────────┬──────────────────────────────────────────┐
  │ 类型        │ 前缀     │ 读取方式                       │ 说明                                     │
  ├─────────────┼──────────┼───────────────────────────────┼──────────────────────────────────────────┤
  │ 智能表格    │ s3_      │ dop-api 全量                  │ ✅ 结构化，支持字段映射                 │
  │ 微文档      │ w3_      │ opendoc API                   │ ✅ 完整正文（canvas 渲染，DOM 无效）    │
  │ 电子表格    │ e3_      │ JS Runtime 元数据 + 剪贴板 HTML │ ✅ 合并单元格保留（colspan/rowspan）     │
  │ 收集表      │ form     │ DOM 文本提取                  │ ✅ 表单内容                             │
  │ 幻灯片      │ slide    │ DOM 文本提取                  │ ✅ 幻灯片文本                           │
  │ 思维导图    │ m4_      │ dop-api/get/mind              │ ✅ JSON 节点树                          │
  │ 流程图      │ flowchart│ DOM 文本提取                  │ ✅ 节点文本                             │
  └─────────────┴──────────┴───────────────────────────────┴──────────────────────────────────────────┘

依赖:
  pip install playwright
  playwright install chromium

用法（CLI）:
  python3 -m wecom_doc_reader --state-dir ./states login <user_id>
  python3 -m wecom_doc_reader --state-dir ./states check <user_id>
  python3 -m wecom_doc_reader --state-dir ./states read <user_id> <url>
  python3 -m wecom_doc_reader --state-dir ./states list-users
  python3 -m wecom_doc_reader --state-dir ./states remove-user <user_id>

用法（Python API）:
  from wecom_doc_reader import WeComDocReader
  reader = WeComDocReader(state_dir="./states")
  result = await reader.login("user_123")
  result = await reader.read("user_123", "https://doc.weixin.qq.com/doc/w3_xxx?scode=xxx")
"""

from __future__ import annotations

from .constants import (
    __version__,
    DEFAULT_STATE_DIR,
    LEGACY_SHARED_STATE,
    _TZ_CN,
    _URL_PREFIX_TO_TYPE,
    _FIELD_TYPE_TEXT,
    _FIELD_TYPE_USER,
    _FIELD_TYPE_EDITOR,
    _FIELD_TYPE_CREATED_AT,
    _FIELD_TYPE_UPDATED_AT,
    _FIELD_TYPE_SELECT,
    _FIELD_TYPE_FORMULA,
    _DOM_SELECTORS,
    RETRY_MAX_ATTEMPTS,
    RETRY_BASE_DELAY,
    RETRY_SHEET_MAX,
    _NON_RETRYABLE_KEYWORDS,
)
from .utils import _auto_report
from .parsers import (
    parse_doc_url,
    _cell_value,
    _parse_column_defs,
    _block_fonts,
    _is_login_page,
)
from .reader import WeComDocReader
from .cli import main, _legacy_main, _legacy_login

__all__ = [
    "WeComDocReader",
    "parse_doc_url",
    "_parse_column_defs",
    "_cell_value",
    "_block_fonts",
    "_is_login_page",
    "_auto_report",
    "_FIELD_TYPE_TEXT",
    "_FIELD_TYPE_USER",
    "_FIELD_TYPE_EDITOR",
    "_FIELD_TYPE_CREATED_AT",
    "_FIELD_TYPE_UPDATED_AT",
    "_FIELD_TYPE_SELECT",
    "_FIELD_TYPE_FORMULA",
    "_DOM_SELECTORS",
    "RETRY_MAX_ATTEMPTS",
    "RETRY_BASE_DELAY",
    "RETRY_SHEET_MAX",
    "_NON_RETRYABLE_KEYWORDS",
    "DEFAULT_STATE_DIR",
    "LEGACY_SHARED_STATE",
    "_TZ_CN",
    "_URL_PREFIX_TO_TYPE",
    "__version__",
    "main",
    "_legacy_main",
    "_legacy_login",
]
