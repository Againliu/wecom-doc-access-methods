#!/usr/bin/env python3
"""解析工具 — URL 解析、单元格值提取、列定义解析等"""

from __future__ import annotations

import re
import json
from datetime import datetime
from urllib.parse import urlparse, parse_qs

from .constants import (
    _TZ_CN,
    _URL_PREFIX_TO_TYPE,
    _FIELD_TYPE_TEXT,
    _FIELD_TYPE_USER,
    _FIELD_TYPE_EDITOR,
    _FIELD_TYPE_CREATED_AT,
    _FIELD_TYPE_UPDATED_AT,
    _FIELD_TYPE_SELECT,
    _FIELD_TYPE_FORMULA,
)

def parse_doc_url(url: str) -> dict:
    """
    解析企微文档 URL。

    返回:
        {
            "doc_type": "s3" | "w3" | "e3" | "m4" | "unknown",
            "doc_id": "s3_xxx",
            "path_type": "smartsheet" | "doc" | "sheet" | "form" | ...,
            "scode": str | None,
            "tab": str | None,
        }
    """
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    parts = [p for p in parsed.path.strip("/").split("/") if p]
    path_type = parts[0] if parts else ""
    doc_id = parts[1] if len(parts) > 1 else None
    doc_type = "unknown"
    if doc_id:
        prefix = doc_id[:2]
        if prefix in _URL_PREFIX_TO_TYPE:
            doc_type = prefix
    return {
        "doc_type": doc_type,
        "doc_id": doc_id,
        "path_type": path_type,
        "scode": query.get("scode", [None])[0],
        "tab": query.get("tab", [None])[0],
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# dop-api 数据解析（s3_ 智能表格专用）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _cell_value(cell: dict, select_opts=None, user_map=None) -> str:
    """根据字段类型提取单元格文本值。兼容 k前缀键和数字键。"""
    k30 = cell.get("k30") or cell.get("30")

    if k30 == _FIELD_TYPE_TEXT:
        k1 = cell.get("k1") or cell.get("1") or []
        if k1 and isinstance(k1[0], dict):
            return k1[0].get("k2") or k1[0].get("2") or ""
        return ""

    if k30 == _FIELD_TYPE_SELECT:
        k17 = cell.get("k17") or cell.get("17") or []
        if not k17:
            return ""
        oid = k17[0]
        return select_opts.get(oid, oid) if select_opts else oid

    if k30 in (_FIELD_TYPE_USER, _FIELD_TYPE_EDITOR):
        k17 = cell.get("k17") or cell.get("17") or []
        if not k17:
            return ""
        uid = k17[0]
        return user_map.get(uid, uid) if user_map else uid

    if k30 in (_FIELD_TYPE_CREATED_AT, _FIELD_TYPE_UPDATED_AT):
        k32 = cell.get("k32") or cell.get("32")
        if k32 and isinstance(k32, (int, float)):
            ts = k32 / 1000 if k32 > 1e12 else k32
            return datetime.fromtimestamp(ts, tz=_TZ_CN).strftime("%Y-%m-%d %H:%M:%S")
        return str(k32) if k32 else ""

    if k30 == _FIELD_TYPE_FORMULA:
        k36 = cell.get("k36") or cell.get("36") or {}
        k1 = k36.get("k1") or k36.get("1") or ""
        try:
            data = json.loads(k1).get("data", [])
            return data[0].get("text", "") if data else ""
        except (json.JSONDecodeError, TypeError, IndexError):
            return ""

    return ""


def _parse_column_defs(items: list) -> tuple:
    """
    从 dop-api parsed items 提取列定义、选项映射、用户映射。

    返回: (field_defs, select_options, user_map)
        field_defs:     {fid: {"name": str, "type": int}}
        select_options: {fid: {option_id: option_text}}
        user_map:       {user_id: name}
    """
    field_defs, select_options, user_map = {}, {}, {}

    for item in items:
        t, c = item.get("t"), item.get("c", {})

        # 列定义 (t=3005)
        if t == 3005:
            col = c.get("3") or c.get("k3") or {}
            inner = col.get("3") or col.get("k3") or {}
            for fid, meta in inner.items():
                name = meta.get("30") or meta.get("k30") or ""
                ftype = meta.get("31") or meta.get("k31") or 0
                field_defs[fid] = {"name": name, "type": ftype}

                # select 选项
                if ftype == _FIELD_TYPE_SELECT:
                    k17 = meta.get("17") or meta.get("k17") or {}
                    k3 = k17.get("3") or k17.get("k3") or []
                    if k3:
                        select_options[fid] = {
                            (o.get("1") or o.get("k1")): (o.get("2") or o.get("k2"))
                            for o in k3 if (o.get("1") or o.get("k1"))
                        }

        # 用户映射
        k3 = c.get("k3") or c.get("3") or {}
        k5 = k3.get("k5") or k3.get("5") or {}
        if isinstance(k5, dict):
            for uid, info in k5.items():
                name = info.get("k2") or info.get("2") or ""
                if name:
                    user_map[uid] = name

    return field_defs, select_options, user_map


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Playwright 通用工具
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def _block_fonts(page):
    """阻止字体加载以加速页面加载"""
    await page.route("**/*.woff*", lambda r: r.abort())
    await page.route("**/*.ttf", lambda r: r.abort())


def _is_login_page(url: str) -> bool:
    """检测是否跳转到了登录页（cookies 过期）"""
    low = url.lower()
    return "login" in low or "scenario/login" in low
