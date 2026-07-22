#!/usr/bin/env python3
"""
企微智能表格 dop-api 全量数据抓取。

两种模式：
  intercept  — 拦截页面自动加载的 dop-api 响应（base64+zlib 解压）
  fetch      — 主动 fetch dop-api（纯 JSON，推荐）

用法:
  python3 wecom_fetch.py <doc_url> --state FILE [--mode intercept|fetch] [--sheet-id ID]

输出: JSON 到 stdout，包含全量结构化数据。

依赖: playwright
"""

import asyncio, json, sys, os, time, base64, zlib, argparse, re
from playwright.async_api import async_playwright


def extract_doc_and_sheet_ids(url):
    """从 URL 提取 padId 和 sheet_id"""
    # padId: s3_xxx 部分
    m = re.search(r'/(smartsheet/)?(s3_\w+)', url)
    pad_id = m.group(2) if m else None

    # sheet_id: 可能在 URL path 或 query 中
    sheet_id = None
    m2 = re.search(r'/smartsheet/[^/]+/([^?]+)', url)
    if m2:
        sheet_id = m2.group(1)

    return pad_id, sheet_id


async def fetch_via_intercept(state_file, doc_url):
    """拦截 dop-api/get/sheet 响应"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=['--no-sandbox'])
        context = await browser.new_context(storage_state=state_file)
        page = await context.new_page()
        await page.route("**/*.woff*", lambda r: r.abort())
        await page.route("**/*.ttf", lambda r: r.abort())

        sheet_data = None
        async def on_response(response):
            nonlocal sheet_data
            if 'dop-api/get/sheet' in response.url and response.status == 200:
                try:
                    sheet_data = await response.json()
                except:
                    pass
        page.on('response', on_response)

        print(f"[fetch] 打开文档: {doc_url}", file=sys.stderr)
        try:
            await page.goto(doc_url, wait_until='networkidle', timeout=60000)
        except Exception as e:
            print(f"[fetch] 导航警告: {e}", file=sys.stderr)
        await page.wait_for_timeout(5000)

        # 检查 cookie
        if "login" in page.url.lower():
            await browser.close()
            return {"error": "cookie 已过期"}

        await browser.close()

    if not sheet_data:
        return {"error": "未捕获 dop-api 响应"}

    # 解码: urlsafe_b64decode + zlib
    try:
        text_data = sheet_data['data']['initialAttributedText']['text'][0]['smartsheet']
        decoded = base64.urlsafe_b64decode(text_data)
        decompressed = zlib.decompress(decoded)
        data = json.loads(decompressed.decode('utf-8'))
    except Exception as e:
        return {"error": f"解码失败: {e}", "hint": "确认用 urlsafe_b64decode + zlib.decompress 默认参数"}

    return {"source": "intercept", "format": "base64+zlib", "data": data}


async def fetch_via_active(state_file, doc_url, pad_id=None, sheet_id=None):
    """主动 fetch dop-api，返回纯 JSON"""
    if not pad_id:
        pad_id, sid = extract_doc_and_sheet_ids(doc_url)
        if not sheet_id:
            sheet_id = sid

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=['--no-sandbox'])
        context = await browser.new_context(storage_state=state_file)
        page = await context.new_page()
        await page.route("**/*.woff*", lambda r: r.abort())
        await page.route("**/*.ttf", lambda r: r.abort())

        print(f"[fetch] 打开文档: {doc_url}", file=sys.stderr)
        try:
            await page.goto(doc_url, wait_until='networkidle', timeout=60000)
        except Exception as e:
            print(f"[fetch] 导航警告: {e}", file=sys.stderr)
        await page.wait_for_timeout(3000)

        # 检查 cookie
        if "login" in page.url.lower():
            await browser.close()
            return {"error": "cookie 已过期"}

        # 如果没拿到 sheet_id，先拦截一次获取
        if not sheet_id:
            captured_sid = None
            async def capture_sid(response):
                nonlocal captured_sid
                if 'dop-api/get/sheet' in response.url and 'subId=' in response.url:
                    m = re.search(r'subId=(\w+)', response.url)
                    if m:
                        captured_sid = m.group(1)
            page.on('response', capture_sid)
            await page.reload(wait_until='networkidle', timeout=60000)
            await page.wait_for_timeout(3000)
            sheet_id = captured_sid
            page.remove_listener('response', capture_sid)

        if not pad_id or not sheet_id:
            await browser.close()
            return {"error": f"无法提取 padId={pad_id} 或 sheetId={sheet_id}"}

        api_url = (
            f"https://doc.weixin.qq.com/dop-api/get/sheet"
            f"?padId={pad_id}&subId={sheet_id}"
            f"&startrow=0&endrow=99999&outformat=1&normal=1"
        )
        print(f"[fetch] 主动 fetch: {api_url}", file=sys.stderr)

        result = await page.evaluate("""async (url) => {
            const r = await fetch(url, {credentials: 'include'});
            return await r.json();
        }""", api_url)

        await browser.close()
        return {
            "source": "active_fetch",
            "format": "json",
            "pad_id": pad_id,
            "sheet_id": sheet_id,
            "data": result
        }


def extract_select_options(data):
    """从 t=3005 列定义提取 select 选项映射"""
    select_options = {}

    items = data if isinstance(data, list) else []
    if isinstance(data, dict) and '0' in data:
        items = data['0'] if isinstance(data['0'], list) else []

    for item in items:
        if isinstance(item, dict) and item.get('t') == 3005:
            c = item.get('c', {})
            field_defs = c.get('3', {}).get('3', {})
            for fid, fmeta in field_defs.items():
                k17 = fmeta.get('17')
                if k17 and isinstance(k17, dict):
                    k3 = k17.get('3')
                    if k3 and isinstance(k3, list):
                        select_options[fid] = {
                            opt.get('1', ''): opt.get('2', '')
                            for opt in k3
                        }
            break

    return select_options


def extract_records(data, select_options=None):
    """提取行数据为扁平字典列表"""
    records = []

    # 尝试两种路径
    rows = None
    if isinstance(data, list) and len(data) > 0:
        first = data[0]
        if isinstance(first, list) and len(first) > 1:
            # base64+zlib 格式: data[0][0].c.k2.k1
            try:
                rows = first[0].get('c', {}).get('k2', {}).get('k1', {})
            except:
                pass
            # 纯 JSON 格式: data[0][1].c.2.1
            if not rows:
                try:
                    rows = first[1].get('c', {}).get('2', {}).get('1', {})
                except:
                    pass

    if not rows:
        return records

    for rid, rdata in rows.items():
        cells = rdata.get('k1', rdata.get('1', {}))
        record = {'record_id': rid}

        for fid, cell in cells.items():
            k30 = cell.get('k30', cell.get('30'))
            if k30 == 1:  # 文本
                k1 = cell.get('k1', cell.get('1', []))
                val = ''
                if k1 and isinstance(k1[0], dict):
                    val = k1[0].get('k2', k1[0].get('2', ''))
                record[fid] = val
            elif k30 == 17:  # 单选
                k17 = cell.get('k17', cell.get('17', []))
                opt_id = k17[0] if k17 else ''
                if select_options and fid in select_options:
                    record[fid] = select_options[fid].get(opt_id, opt_id)
                else:
                    record[fid] = opt_id
            else:
                record[fid] = ''

        records.append(record)

    return records


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="企微智能表格 dop-api 全量抓取")
    parser.add_argument("url", help="智能表格 URL")
    parser.add_argument("--state", default="./wecom_state.json", help="storage_state 路径")
    parser.add_argument("--mode", choices=["intercept", "fetch"], default="fetch",
                        help="抓取模式: fetch=主动fetch纯JSON(默认), intercept=拦截base64+zlib")
    parser.add_argument("--sheet-id", default=None, help="子表 ID（可选，自动检测）")
    parser.add_argument("--extract", action="store_true", help="提取为扁平记录列表")
    args = parser.parse_args()

    if not os.path.exists(args.state):
        print(json.dumps({"error": f"无登录状态文件: {args.state}，请先运行 wecom_login.py"}))
        sys.exit(1)

    if args.mode == "intercept":
        result = asyncio.run(fetch_via_intercept(args.state, args.url))
    else:
        pad_id, auto_sid = extract_doc_and_sheet_ids(args.url)
        result = asyncio.run(fetch_via_active(args.state, args.url, pad_id, args.sheet_id or auto_sid))

    if "error" in result:
        print(json.dumps(result, ensure_ascii=False))
        sys.exit(1)

    if args.extract and "data" in result:
        data = result["data"]
        # 对于 active fetch 格式，data 可能直接就是解析后的 JSON
        if isinstance(data, dict) and 'data' in data:
            data = data['data']

        select_opts = extract_select_options(data if isinstance(data, list) else [])
        records = extract_records(data if isinstance(data, list) else [], select_opts)
        result["records"] = records
        result["record_count"] = len(records)
        result["select_options"] = select_opts

    print(json.dumps(result, ensure_ascii=False, indent=2))
