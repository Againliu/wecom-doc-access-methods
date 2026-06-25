#!/usr/bin/env python3
"""
企微文档通用读取工具 — MCP 优先 + 浏览器兜底。

用法:
  python3 wecom_reader.py check --state FILE           # 检查 cookie 有效性
  python3 wecom_reader.py fetch <url> --state FILE      # 读取文档内容（MCP优先→浏览器兜底）
  python3 wecom_reader.py fetch-sheet <url> --state FILE --mcp-url URL  # 读取智能表格

依赖: playwright, requests (可选，用于 MCP)
"""

import asyncio, json, os, sys, time, argparse
from playwright.async_api import async_playwright


async def check_cookies(state_file):
    """检查 cookies 是否仍有效"""
    if not os.path.exists(state_file):
        return {"valid": False, "reason": f"文件不存在: {state_file}"}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=['--no-sandbox'])
        context = await browser.new_context(
            storage_state=state_file,
            viewport={"width": 800, "height": 600}
        )
        page = await context.new_page()
        await page.route("**/*.woff*", lambda r: r.abort())
        await page.route("**/*.ttf", lambda r: r.abort())

        try:
            await page.goto("https://doc.weixin.qq.com/home/recent",
                            wait_until="domcontentloaded", timeout=15000)
            await asyncio.sleep(3)

            url = page.url
            body = await page.evaluate("() => document.body?.innerText?.substring(0, 200) || ''")

            is_login = "login" in url.lower() or "scenario/login" in url
            has_content = "我的文档" in body or "首页" in body or "最近查看" in body
            valid = not is_login and has_content
            reason = "OK" if valid else f"URL={url}, body={body[:50]}"
        except Exception as e:
            valid = False
            reason = str(e)[:200]

        await browser.close()
        return {"valid": valid, "reason": reason, "ts": time.time()}


async def fetch_doc_browser(state_file, url):
    """用浏览器读取文档内容"""
    if not os.path.exists(state_file):
        return {"error": f"无登录状态文件: {state_file}"}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=['--no-sandbox'])
        context = await browser.new_context(
            storage_state=state_file,
            viewport={"width": 1280, "height": 800}
        )
        page = await context.new_page()
        await page.route("**/*.woff*", lambda r: r.abort())
        await page.route("**/*.ttf", lambda r: r.abort())

        try:
            await page.goto(url, wait_until="networkidle", timeout=30000)
        except:
            pass
        await asyncio.sleep(5)

        # 检查 cookie 过期
        if "login" in page.url.lower():
            await browser.close()
            return {"error": "cookie 已过期，需重新扫码"}

        # 提取文档内容
        content = await page.evaluate("""() => {
            const selectors = [
                '.ne-doc-content', '.ne-viewer-body', '.ne-editor',
                '.doc-content', '.lake-engine', '.ql-editor'
            ];
            for (const sel of selectors) {
                const el = document.querySelector(sel);
                if (el && el.innerText?.length > 10) {
                    return { selector: sel, text: el.innerText };
                }
            }
            return {
                selector: 'body',
                text: document.body?.innerText?.substring(0, 100000) || ''
            };
        }""")

        result = {
            "source": "browser",
            "title": await page.title(),
            "url": page.url,
            "selector": content.get("selector"),
            "text_length": len(content.get("text", "")),
            "text": content.get("text", "")
        }
        await browser.close()
        return result


def mcp_call(mcp_url, tool_name, arguments):
    """调 MCP JSON-RPC"""
    import requests
    payload = {
        "jsonrpc": "2.0", "method": "tools/call",
        "params": {"name": tool_name, "arguments": arguments}, "id": 1
    }
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    resp = requests.post(mcp_url, json=payload, headers=headers, timeout=60)
    data = resp.json()
    if "error" in data:
        return {"error": f"MCP error: {data['error']}"}
    inner = json.loads(data["result"]["content"][0]["text"])
    return inner


def fetch_doc(url, state_file, mcp_url=None):
    """读文档：MCP 优先，浏览器兜底"""
    is_smartsheet = '/smartsheet/' in url
    is_doc = '/doc/' in url

    # 尝试 MCP
    if mcp_url:
        if is_smartsheet:
            result = mcp_call(mcp_url, "smartsheet_get_sheet", {"url": url})
            if result.get("errcode") == 0:
                print(json.dumps({"source": "mcp", "sheets": result.get("sheet_list", [])}, ensure_ascii=False, indent=2))
                return result
        elif is_doc:
            result = mcp_call(mcp_url, "get_doc_content", {"url": url, "type": 2})
            if result.get("errcode") == 0:
                print(json.dumps({"source": "mcp", "content": result.get("content", "")}, ensure_ascii=False, indent=2))
                return result
            elif result.get("task_id"):
                for _ in range(10):
                    time.sleep(2)
                    result = mcp_call(mcp_url, "get_doc_content", {"task_id": result["task_id"], "type": 2})
                    if result.get("task_done"):
                        print(json.dumps({"source": "mcp", "content": result.get("content", "")}, ensure_ascii=False, indent=2))
                        return result
        print("MCP 不可用，切换浏览器...", file=sys.stderr)

    # 浏览器兜底
    result = asyncio.run(fetch_doc_browser(state_file, url))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="企微文档通用读取")
    parser.add_argument("command", choices=["check", "fetch", "fetch-sheet"])
    parser.add_argument("url", nargs="?", default="")
    parser.add_argument("--state", default="./wecom_state.json", help="storage_state 路径")
    parser.add_argument("--mcp-url", default=None, help="MCP Server URL（可选）")
    args = parser.parse_args()

    if args.command == "check":
        result = asyncio.run(check_cookies(args.state))
        print(json.dumps(result, ensure_ascii=False))

    elif args.command == "fetch":
        if not args.url:
            print("用法: python3 wecom_reader.py fetch <url> --state FILE", file=sys.stderr)
            sys.exit(1)
        fetch_doc(args.url, args.state, args.mcp_url)

    elif args.command == "fetch-sheet":
        if not args.url:
            print("用法: python3 wecom_reader.py fetch-sheet <url> --state FILE --mcp-url URL", file=sys.stderr)
            sys.exit(1)
        if not args.mcp_url:
            print("fetch-sheet 需要 --mcp-url 参数", file=sys.stderr)
            sys.exit(1)
        result = mcp_call(args.mcp_url, "smartsheet_get_sheet", {"url": args.url})
        if result.get("errcode") != 0:
            print(json.dumps(result, ensure_ascii=False, indent=2))
            sys.exit(1)
        sheets = result.get("sheet_list", [])
        for s in sheets:
            print(f"\n=== {s['title']} ({s['sheet_id']}) ===")
            records = mcp_call(args.mcp_url, "smartsheet_get_records", {"url": args.url, "sheet_id": s['sheet_id']})
            if records.get("errcode") == 0:
                print(f"总记录: {records.get('total', 0)}, 已获取: {len(records.get('records', []))}")
                out = f"/tmp/wecom_sheet_{s['sheet_id']}.json"
                with open(out, "w") as f:
                    json.dump(records, f, ensure_ascii=False, indent=2)
                print(f"已保存到 {out}")
            else:
                print(f"获取失败: {json.dumps(records, ensure_ascii=False)[:200]}")
