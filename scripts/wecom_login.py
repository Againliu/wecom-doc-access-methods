#!/usr/bin/env python3
"""
企微文档扫码登录 — 生成二维码，等待用户扫码，保存 Playwright storage_state。

用法:
  python3 wecom_login.py [--state FILE] [--qr FILE] [--timeout SECONDS]

参数:
  --state FILE   storage_state 输出路径 (默认: ./wecom_state.json)
  --qr FILE      二维码图片输出路径 (默认: /tmp/wecom_qr.png)
  --timeout SEC  等待扫码超时秒数 (默认: 300)

输出:
  1. 二维码图片保存到 --qr 路径（展示给用户扫码）
  2. 扫码成功后 storage_state 保存到 --state 路径
  3. stdout 输出 JSON 状态更新
"""

import asyncio, json, os, sys, time, argparse, tempfile
from pathlib import Path
from playwright.async_api import async_playwright


def write_status(status, msg=""):
    data = {"status": status, "msg": msg, "ts": time.time()}
    print(json.dumps(data, ensure_ascii=False), flush=True)


def write_private_state(state_file, state):
    """Atomically replace a credential state file with owner-only mode."""
    path = Path(state_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp"
    )
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(state, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        os.chmod(path, 0o600)
    except BaseException:
        try:
            os.close(descriptor)
        except OSError:
            pass
        temporary.unlink(missing_ok=True)
        raise


async def main(state_file, qr_file, timeout_sec):
    write_status("starting", "启动 Playwright")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=['--no-sandbox'])

        qr_captured = False

        async def capture_qr(response):
            nonlocal qr_captured
            url = response.url
            if 'qrcode' in url.lower() and response.status == 200:
                ct = response.headers.get('content-type', '')
                if 'image' in ct and not qr_captured:
                    try:
                        data = await response.body()
                        with open(qr_file, "wb") as f:
                            f.write(data)
                        qr_captured = True
                        write_status("qr_ready", f"QR码已保存({len(data)}bytes)到 {qr_file}，请扫码")
                    except Exception as e:
                        write_status("error", f"QR捕获失败: {e}")

        page = await browser.new_page(viewport={"width": 800, "height": 600}, bypass_csp=True)
        page.on("response", capture_qr)

        # 阻止字体加载（加速）
        await page.route("**/*.woff*", lambda route: route.abort())
        await page.route("**/*.ttf", lambda route: route.abort())

        write_status("navigating", "打开登录页")
        try:
            await page.goto("https://doc.weixin.qq.com", wait_until="domcontentloaded", timeout=15000)
        except Exception as e:
            write_status("navigating", f"页面加载中: {e}")

        # 等待 QR 加载（最多 20s）
        for _ in range(20):
            await asyncio.sleep(1)
            if qr_captured:
                break

        if not qr_captured:
            write_status("error", "QR码未能加载")
            await browser.close()
            return 2

        # 等待扫码
        write_status("waiting_scan", "等待扫码中...")
        scanned = False
        max_waits = timeout_sec // 2
        for i in range(max_waits):
            await asyncio.sleep(2)
            current_url = page.url

            if "login" not in current_url.lower() and "scenario" not in current_url.lower():
                write_status("scanned", f"扫码成功! 跳转到: {current_url}")
                scanned = True
                break

            if i % 15 == 14:
                write_status("waiting_scan", f"仍在等待扫码({(i+1)*2}s)...")

        if scanned:
            await asyncio.sleep(5)
            # 抓登录用户信息（2026-09-02：userName 一直在 basicClientVars 里，此前没取）
            user_info = {}
            try:
                raw = await page.evaluate("JSON.stringify(window.basicClientVars||{})")
                user_info = (json.loads(raw) or {}).get("userInfo", {}) if raw else {}
            except Exception:
                pass
            context = page.context
            state = await context.storage_state()
            # 附加用户信息，登录态落盘时一并保存（仅元数据，不含敏感凭证）
            if user_info:
                state["login_user"] = {
                    "name": str(user_info.get("userName", ""))[:64],
                    "user_id": str(user_info.get("userId", ""))[:64],
                    "user_type": str(user_info.get("userType", ""))[:16],
                    "captured_at": int(time.time()),
                }
            write_private_state(state_file, state)

            cookies = state.get("cookies", [])
            user_name = state.get("login_user", {}).get("name", "")
            write_status(
                "success",
                f"登录成功! 保存了{len(cookies)}条cookies到 {state_file}"
                + (f"；登录用户: {user_name}" if user_name else "；未捕获到用户名"),
            )
            rc = 0
        else:
            write_status("timeout", "等待超时，QR码可能已过期")
            rc = 1

        await browser.close()
        return rc


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="企微文档扫码登录")
    parser.add_argument("--state", default="./wecom_state.json", help="storage_state 输出路径")
    parser.add_argument("--qr", default="/tmp/wecom_qr.png", help="二维码图片输出路径")
    parser.add_argument("--timeout", type=int, default=300, help="等待扫码超时秒数")
    args = parser.parse_args()

    sys.exit(asyncio.run(main(args.state, args.qr, args.timeout)))
