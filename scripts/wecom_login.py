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

import asyncio, json, os, sys, time, argparse
from playwright.async_api import async_playwright


def write_status(status, msg="", status_file=None):
    data = {"status": status, "msg": msg, "ts": time.time()}
    line = json.dumps(data, ensure_ascii=False)
    print(line, flush=True)
    if status_file:
        try:
            with open(status_file, "w") as f:
                json.dump(data, f, ensure_ascii=False)
        except Exception:
            pass


async def main(state_file, qr_file, timeout_sec, status_file=None):
    def ws(status, msg=""):
        write_status(status, msg, status_file)

    ws("starting", "启动 Playwright")

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
                        ws("qr_ready", f"QR码已保存({len(data)}bytes)到 {qr_file}，请扫码")
                    except Exception as e:
                        ws("error", f"QR捕获失败: {e}")

        page = await browser.new_page(viewport={"width": 800, "height": 600}, bypass_csp=True)
        page.on("response", capture_qr)

        # 阻止字体加载（加速）
        await page.route("**/*.woff*", lambda route: route.abort())
        await page.route("**/*.ttf", lambda route: route.abort())

        ws("navigating", "打开登录页")
        try:
            await page.goto("https://doc.weixin.qq.com", wait_until="domcontentloaded", timeout=15000)
        except Exception as e:
            ws("navigating", f"页面加载中: {e}")

        # 等待 QR 加载（最多 20s）
        for _ in range(20):
            await asyncio.sleep(1)
            if qr_captured:
                break

        if not qr_captured:
            ws("error", "QR码未能加载")
            await browser.close()
            return

        # 等待扫码 — 双重判断：URL 变化 + wedoc_sid cookie 出现
        ws("waiting_scan", "等待扫码中...")
        scanned = False
        max_waits = timeout_sec // 2
        for i in range(max_waits):
            await asyncio.sleep(2)
            current_url = page.url

            # 方式1：URL 不再含 login/scenario
            url_changed = "login" not in current_url.lower() and "scenario" not in current_url.lower()

            # 方式2：cookie 里出现了 wedoc_sid（登录成功的真正标志）
            has_sid = False
            try:
                cookies = await page.context.cookies("https://doc.weixin.qq.com")
                has_sid = any(c.get("name") == "wedoc_sid" for c in cookies)
            except Exception:
                pass

            if url_changed or has_sid:
                ws("scanned", f"扫码成功! URL: {current_url}, wedoc_sid: {has_sid}")
                scanned = True
                break

            if i % 15 == 14:
                ws("waiting_scan", f"仍在等待扫码({(i+1)*2}s)...")

        if scanned:
            # 等 wedoc_sid 真正写入（最多再等 15s），而不是固定 sleep 5s
            for _ in range(8):
                await asyncio.sleep(2)
                try:
                    cookies = await page.context.cookies("https://doc.weixin.qq.com")
                    if any(c.get("name") == "wedoc_sid" for c in cookies):
                        break
                except Exception:
                    pass

            context = page.context
            state = await context.storage_state()
            with open(state_file, "w") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)

            cookies = state.get("cookies", [])
            sid_found = any(c.get("name") == "wedoc_sid" for c in cookies)
            if sid_found:
                ws("success", f"登录成功! 保存了{len(cookies)}条cookies到 {state_file}")
            else:
                ws("warning", f"已保存{len(cookies)}条cookies到 {state_file}，但缺少 wedoc_sid，可能登录不完整")
        else:
            ws("timeout", "等待超时，QR码可能已过期")

        await browser.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="企微文档扫码登录")
    parser.add_argument("--state", default="./wecom_state.json", help="storage_state 输出路径")
    parser.add_argument("--qr", default="/tmp/wecom_qr.png", help="二维码图片输出路径")
    parser.add_argument("--timeout", type=int, default=300, help="等待扫码超时秒数")
    parser.add_argument("--status-file", default=None, help="状态文件输出路径（JSON，轮询此文件即可自动检测扫码结果）")
    args = parser.parse_args()

    asyncio.run(main(args.state, args.qr, args.timeout, args.status_file))
