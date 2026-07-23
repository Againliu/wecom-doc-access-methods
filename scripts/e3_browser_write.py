#!/usr/bin/env python3
"""e3_ 电子表格浏览器写入 — Mutation API 方案（2026-07-23 实测闭环）

通过企微 OT/Mutation 协同模型写入 e3_ 电子表格单元格。
完整流程：cookie 加载 → 打开页面 → monkey-patch 捕获 mutation → 修改属性 → applyMutation + await commitMutation → WS 同步 → 服务端持久化。

⚠️ 关键 Pitfall（详见 references/e3-browser-write-research.md）：
  1. mutation 的 cell 和 gridRangeData 是类实例（有 isInvalid/getAuthor 方法）。
     只能改标量属性（.value/.startRowIndex 等），**不能替换整个对象为 plain JSON**。
  2. commitMutation 返回 **Promise**（不是 generator），必须 await。
  3. 方向键定位可靠；坐标点击不稳定（canvas 渲染布局每次不同）。

用法：
  python3 e3_browser_write.py \\
    --user <wecom_userid> \\
    --url "https://doc.weixin.qq.com/sheet/e3_xxx" \\
    --row 10 --col 2 --value "测试写入"
"""
import argparse, asyncio, json, os, sys

COOKIE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "wecom_states")


async def write_e3_cell(user_id: str, doc_url: str, row: int, col: int, value: str,
                         cookie_file: str = None, verify_persistence: bool = True) -> dict:
    """Write a single cell to an e3_ spreadsheet via mutation API.

    Returns: {"success": bool, "readback": str, "persisted": str|None, "error": str|None}
    """
    from playwright.async_api import async_playwright

    if not cookie_file:
        cookie_file = os.path.join(COOKIE_DIR, f"{user_id}.json")
    if not os.path.exists(cookie_file):
        return {"success": False, "error": f"Cookie file not found: {cookie_file}"}

    with open(cookie_file) as f:
        state = json.load(f)
    pw_cookies = []
    for c in state.get("cookies", []):
        pc = {"name": c["name"], "value": c["value"], "domain": c["domain"], "path": c.get("path", "/")}
        if c.get("expires", -1) > 0:
            pc["expires"] = c["expires"]
        pw_cookies.append(pc)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
        )
        await context.add_cookies(pw_cookies)
        page = await context.new_page()

        # Navigate
        try:
            await page.goto(doc_url, wait_until="domcontentloaded", timeout=45000)
        except Exception as e:
            return {"success": False, "error": f"Navigation failed: {e}"}
        await page.wait_for_timeout(12000)  # Wait for SpreadsheetApp JS runtime

        # Focus canvas
        await page.mouse.click(400, 400)
        await page.wait_for_timeout(800)
        await page.keyboard.press("Escape")
        await page.wait_for_timeout(300)

        # Step 1: Install monkey-patch on commitMutation to capture a real mutation instance
        # (Mutation class is minified — can't `new` it directly. Must capture from keyboard edit.)
        await page.evaluate("""() => {
            const app = window.SpreadsheetApp;
            window.__m = null;
            window.__opts = null;
            const cs = app.commitService;
            const orig = cs.commitMutation.bind(cs);
            cs.commitMutation = function(e) {
                try {
                    const o = e?.options;
                    if (o?.mutations?.length > 0) {
                        window.__m = o.mutations[0];
                        window.__opts = {
                            requestType: o.requestType,
                            requestKey: o.requestKey,
                            sheetId: o.sheetId,
                            operateType: o.operateType
                        };
                    }
                } catch(err) {}
                return orig(e);
            };
            return true;
        }""")

        # Step 2: Seed keyboard edit to capture mutation (arrow keys for reliable positioning)
        for _ in range(5):
            await page.keyboard.press("ArrowDown")
            await page.wait_for_timeout(50)
        await page.keyboard.press("F2")
        await page.wait_for_timeout(400)
        await page.keyboard.type("__SEED__", delay=60)
        await page.keyboard.press("Enter")
        await page.wait_for_timeout(5000)

        has_mutation = await page.evaluate("""() => window.__m !== null""")
        if not has_mutation:
            # Retry with more arrow downs
            for _ in range(3):
                await page.keyboard.press("ArrowDown")
                await page.wait_for_timeout(50)
            await page.keyboard.press("F2")
            await page.wait_for_timeout(400)
            await page.keyboard.type("__SEED2__", delay=60)
            await page.keyboard.press("Enter")
            await page.wait_for_timeout(5000)
            has_mutation = await page.evaluate("""() => window.__m !== null""")

        if not has_mutation:
            await browser.close()
            return {"success": False, "error": "Failed to capture mutation instance via keyboard edit"}

        # Step 3: Write target cell via mutation API
        # ⚠️ KEY: only modify scalar props, DON'T replace cell/gridRangeData objects!
        result = await page.evaluate("""async (params) => {
            const app = window.SpreadsheetApp;
            const cs = app.commitService;
            const ma = app.mutationApi;
            const wb = app.workbook;
            const sheet = wb.worksheetManager.sheetList[0];
            const sheetId = sheet.cellDataGrid.usedRange.sheetId;
            const m = window.__m;
            const opts = window.__opts;
            const out = {};

            // Save original properties (will restore after write)
            const saved = {
                sr: m.gridRangeData.startRowIndex, er: m.gridRangeData.endRowIndex,
                sc: m.gridRangeData.startColIndex, ec: m.gridRangeData.endColIndex,
                val: m.cell.value, typ: m.cell.type
            };

            // Modify ONLY scalar properties (keep class instances intact!)
            m.gridRangeData.startRowIndex = params.row;
            m.gridRangeData.endRowIndex = params.row;
            m.gridRangeData.startColIndex = params.col;
            m.gridRangeData.endColIndex = params.col;
            m.cell.value = params.value;
            m.cell.type = 4;  // 4 = string

            // 1. Apply locally
            try {
                ma.applyMutation(wb, m);
                out.applyOk = true;
            } catch(e) {
                out.applyOk = false;
                out.applyErr = e.message;
            }

            // 2. Commit to server (⚠️ returns Promise, must await!)
            const commitArg = {
                options: {
                    requestType: opts.requestType || 5,
                    requestKey: Date.now(),
                    sheetId: sheetId,
                    operateType: opts.operateType ?? 0,
                    mutations: [m]
                }
            };
            try {
                const ret = cs.commitMutation(commitArg);
                if (ret && typeof ret.then === 'function') {
                    await ret;  // Promise — await it
                } else if (ret && typeof ret.next === 'function') {
                    let n, steps = 0;
                    while (!(n = ret.next()).done) {
                        steps++;
                        if (n.value && typeof n.value.then === 'function') await n.value;
                        if (steps > 50) break;
                    }
                }
                out.commitOk = true;
            } catch(e) {
                out.commitOk = false;
                out.commitErr = e.message;
            }

            // 3. Restore original properties (avoid side effects)
            m.gridRangeData.startRowIndex = saved.sr;
            m.gridRangeData.endRowIndex = saved.er;
            m.gridRangeData.startColIndex = saved.sc;
            m.gridRangeData.endColIndex = saved.ec;
            m.cell.value = saved.val;
            m.cell.type = saved.typ;

            // 4. Read back via getValue
            await new Promise(r => setTimeout(r, 3000));
            try {
                const cell = sheet.getCellDataAtPosition(params.row, params.col);
                out.readback = cell ? String(cell.getValue()) : null;
            } catch(e) {
                out.readback = "<err: " + e.message + ">";
            }

            return out;
        }""", {"row": row, "col": col, "value": value})

        # Step 4 (optional): Reload and verify persistence
        persisted = None
        if verify_persistence and result.get("commitOk"):
            try:
                await page.goto(doc_url, wait_until="domcontentloaded", timeout=45000)
            except Exception:
                pass
            await page.wait_for_timeout(12000)
            persisted = await page.evaluate("""(params) => {
                const wb = window.SpreadsheetApp?.workbook;
                if (!wb) return "<no workbook>";
                const sheet = wb.worksheetManager.sheetList[0];
                try {
                    const cell = sheet.getCellDataAtPosition(params.row, params.col);
                    return cell ? String(cell.getValue()) : null;
                } catch(e) { return "<err>"; }
            }""", {"row": row, "col": col})

        await browser.close()

        return {
            "success": result.get("applyOk") and result.get("commitOk"),
            "readback": result.get("readback"),
            "persisted": persisted,
            "applyError": result.get("applyErr"),
            "commitError": result.get("commitErr"),
        }


def main():
    parser = argparse.ArgumentParser(description="Write a cell to an e3_ WeCom spreadsheet via mutation API")
    parser.add_argument("--user", required=True, help="WeCom user ID (for cookie file)")
    parser.add_argument("--url", required=True, help="e3_ spreadsheet URL")
    parser.add_argument("--row", type=int, required=True, help="Target row (0-indexed)")
    parser.add_argument("--col", type=int, required=True, help="Target column (0-indexed)")
    parser.add_argument("--value", required=True, help="Value to write (string)")
    parser.add_argument("--cookie-file", default=None, help="Override cookie file path")
    parser.add_argument("--no-verify", action="store_true", help="Skip reload persistence check")
    args = parser.parse_args()

    result = asyncio.run(write_e3_cell(
        user_id=args.user,
        doc_url=args.url,
        row=args.row,
        col=args.col,
        value=args.value,
        cookie_file=args.cookie_file,
        verify_persistence=not args.no_verify,
    ))

    if result["success"]:
        print(f"✅ Write successful")
        print(f"  Readback: {result.get('readback')}")
        if result.get("persisted") is not None:
            match = "✅" if result["persisted"] == args.value else "❌"
            print(f"  Reload persistence: {match} {result['persisted']}")
    else:
        print(f"❌ Write failed")
        if result.get("applyError"):
            print(f"  applyMutation error: {result['applyError']}")
        if result.get("commitError"):
            print(f"  commitMutation error: {result['commitError']}")
        print(f"  Other error: {result.get('error', '')}")
        sys.exit(1)


if __name__ == "__main__":
    main()
