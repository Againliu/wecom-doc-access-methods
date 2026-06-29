#!/usr/bin/env python3
"""CLI 入口 — 命令行接口"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path

from .constants import DEFAULT_STATE_DIR, LEGACY_SHARED_STATE, __version__
from .reader import WeComDocReader

def _legacy_main():
    """向后兼容：老版 CLI 接口（无用户隔离，共享状态文件）"""
    import argparse
    parser = argparse.ArgumentParser(
        description="企微文档读取工具（向后兼容模式）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("check", help="检查共享 cookies 是否有效")
    p_login = sub.add_parser("login", help="扫码登录")
    p_login.add_argument("--timeout", type=int, default=300)
    p_fetch = sub.add_parser("fetch", help="读取文档")
    p_fetch.add_argument("url")
    p_fsheet = sub.add_parser("fetch-sheet", help="读取智能表格")
    p_fsheet.add_argument("url")
    p_fsheet.add_argument("sheet_id", nargs="?", default=None)
    sub.add_parser("list", help="列出状态信息")

    args = parser.parse_args()

    if args.cmd == "check":
        if not os.path.exists(LEGACY_SHARED_STATE):
            print(json.dumps({"valid": False, "reason": "状态文件不存在"}, ensure_ascii=False))
            return
        with open(LEGACY_SHARED_STATE) as f:
            state = json.load(f)
        for c in state.get("cookies", []):
            if c["name"] == "wedoc_sid":
                exp = c.get("expires", 0)
                remaining = (exp - time.time()) / 86400
                print(json.dumps({
                    "valid": remaining > 0,
                    "remaining_days": round(remaining, 1),
                    "reason": "OK" if remaining > 0 else "已过期",
                    "ts": int(time.time()),
                }, ensure_ascii=False, indent=2))
                return
        print(json.dumps({"valid": False, "reason": "未找到 wedoc_sid cookie"}, ensure_ascii=False))

    elif args.cmd == "login":
        asyncio.run(_legacy_login(args.timeout))

    elif args.cmd in ("fetch", "fetch-sheet"):
        # 用共享状态文件通过 WeComDocReader 读取
        import shutil, tempfile
        tmp_dir = tempfile.mkdtemp(prefix="wecom_legacy_")
        try:
            shutil.copy2(LEGACY_SHARED_STATE, os.path.join(tmp_dir, "_shared.json"))
            reader = WeComDocReader(state_dir=tmp_dir)
            sheet_id = getattr(args, "sheet_id", None)
            r = asyncio.run(reader.read("_shared", args.url, sheet_id))
            print(json.dumps(r, ensure_ascii=False, indent=2))
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    elif args.cmd == "list":
        if os.path.exists(LEGACY_SHARED_STATE):
            mtime = os.path.getmtime(LEGACY_SHARED_STATE)
            age_hours = (time.time() - mtime) / 3600
            print(json.dumps({
                "state_file": LEGACY_SHARED_STATE,
                "last_modified": f"{age_hours:.1f}h ago",
            }, ensure_ascii=False, indent=2))
        else:
            print(json.dumps({"error": "状态文件不存在"}, ensure_ascii=False))

    else:
        parser.print_help()


async def _legacy_login(timeout=300):
    """老版扫码登录"""
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
        context = await browser.new_context(viewport={"width": 1280, "height": 800})
        page = await context.new_page()
        qr_saved = False
        async def capture_qr(response):
            nonlocal qr_saved
            if "login" in response.url and "qr" in response.url.lower() and not qr_saved:
                try:
                    body = await response.body()
                    path = "/tmp/wecom_qr_code.png"
                    with open(path, "wb") as f:
                        f.write(body)
                    print(f"二维码已保存: {path}")
                    qr_saved = True
                except:
                    pass
        page.on("response", capture_qr)
        await page.goto("https://doc.weixin.qq.com", wait_until="networkidle", timeout=60000)
        if not qr_saved:
            await page.screenshot(path="/tmp/wecom_qr_code.png")
            print("二维码已截图: /tmp/wecom_qr_code.png")
        print(f"等待扫码（最多 {timeout}s）...")
        deadline = time.time() + timeout
        while time.time() < deadline:
            if "doc.weixin.qq.com" in page.url and "login" not in page.url.lower():
                print("登录成功！")
                break
            await page.wait_for_timeout(2000)
        else:
            print("扫码超时")
            await browser.close()
            return
        os.makedirs(os.path.dirname(LEGACY_SHARED_STATE), exist_ok=True)
        state = await context.storage_state()
        with open(LEGACY_SHARED_STATE, "w") as f:
            json.dump(state, f)
        print(f"状态已保存: {LEGACY_SHARED_STATE}")
        await browser.close()


def main():
    # 向后兼容检测：老版命令（check/login/fetch/fetch-sheet/list）不带 --state-dir
    _legacy_cmds = {"check", "login", "fetch", "fetch-sheet", "list"}
    argv_cmds = [a for a in sys.argv[1:] if not a.startswith("-")]
    if argv_cmds and argv_cmds[0] in _legacy_cmds and "--state-dir" not in sys.argv:
        _legacy_main()
        return

    import argparse

    parser = argparse.ArgumentParser(
        description="企微文档浏览器读取（用户隔离版）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--state-dir",
        default=DEFAULT_STATE_DIR,
        help=f"storage_state 目录 (默认: {DEFAULT_STATE_DIR})",
    )
    sub = parser.add_subparsers(dest="cmd")

    p_login = sub.add_parser("login", help="扫码登录（生成二维码，用户扫码后保存 cookies）")
    p_login.add_argument("user_id", help="用户唯一标识")
    p_login.add_argument("--timeout", type=int, default=300, help="等待扫码超时（秒）")

    p_check = sub.add_parser("check", help="检查用户 cookies 是否有效")
    p_check.add_argument("user_id")

    p_read = sub.add_parser("read", help="读取文档（自动路由：s3_/e3_/m4_→专用方案，其他→DOM）")
    p_read.add_argument("user_id")
    p_read.add_argument("url", help="企微文档 URL")
    p_read.add_argument("--sheet", default=None, help="指定子表 ID（仅智能表格）")

    sub.add_parser("list-users", help="列出所有已登录用户")

    p_rm = sub.add_parser("remove-user", help="删除用户 cookies")
    p_rm.add_argument("user_id")

    args = parser.parse_args()
    reader = WeComDocReader(state_dir=args.state_dir)

    if args.cmd == "login":
        r = asyncio.run(reader.login(args.user_id, args.timeout))
    elif args.cmd == "check":
        r = asyncio.run(reader.check(args.user_id))
    elif args.cmd == "read":
        r = asyncio.run(reader.read(args.user_id, args.url, args.sheet))
    elif args.cmd == "list-users":
        r = reader.list_users()
    elif args.cmd == "remove-user":
        r = reader.remove_user(args.user_id)
    else:
        parser.print_help()
        return

    # 输出 JSON（如果文本太长，截断 text 字段只显示 preview）
    output = r.copy() if isinstance(r, dict) else r
    if isinstance(output, dict) and "text" in output:
        text = output["text"]
        if len(text) > 2000:
            output["text_preview"] = text[:2000]
            output["text_truncated"] = True
            del output["text"]
    print(json.dumps(output, ensure_ascii=False, indent=2))
