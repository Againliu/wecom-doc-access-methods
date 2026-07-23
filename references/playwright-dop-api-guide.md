# 方案一(首选):Playwright + dop-api — 全量读取详细指南

> 本文件由 SKILL.md 拆分而来(2026-07-21)。

## 方案一（首选）：Playwright + dop-api（全量读取，生产验证）

### 原理

浏览器加载智能表格时，会调用内部 API `dop-api/get/sheet` 获取压缩的全量数据。用 Playwright + 已保存的 `storage_state` 拦截此响应或主动 fetch，解压解析，可拿到**全量结构化数据**。

### 前置条件

- Python 3 + Playwright (`pip install playwright && playwright install chromium`)
- 有效的 `storage_state` JSON 文件（通过扫码登录获取）

### 步骤 1：扫码登录获取 storage_state

详见 `scripts/wecom_login.py`。核心流程：

```python
from playwright.async_api import async_playwright

async def login():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=['--no-sandbox'])
        page = await browser.new_page(viewport={"width": 800, "height": 600})

        # 拦截二维码图片
        qr_captured = False
        async def capture_qr(response):
            nonlocal qr_captured
            if 'qrcode' in response.url.lower() and response.status == 200:
                ct = response.headers.get('content-type', '')
                if 'image' in ct and not qr_captured:
                    data = await response.body()
                    with open("/tmp/wecom_qr.png", "wb") as f:
                        f.write(data)
                    qr_captured = True
        page.on("response", capture_qr)

        await page.goto("https://doc.weixin.qq.com", wait_until="domcontentloaded", timeout=15000)

        # 等待 QR 出现（最多 20s）
        for _ in range(20):
            await asyncio.sleep(1)
            if qr_captured: break
        # → 将 /tmp/wecom_qr.png 展示给用户扫码

        # 等待扫码成功（最多 5 分钟）
        for _ in range(150):
            await asyncio.sleep(2)
            if "login" not in page.url.lower() and "scenario" not in page.url.lower():
                await asyncio.sleep(5)
                state = await page.context.storage_state()
                with open("wecom_state.json", "w") as f:
                    json.dump(state, f, ensure_ascii=False, indent=2)
                break

        await browser.close()
```

**⚠️ 扫码成功判断不能只看 URL（2026-07-23 修复）**：
旧代码只检查 `"login" not in page.url.lower()`，但企微跳转后的 URL 可能仍含 `login`/`scenario` 字样（中间跳转页），导致永远检测不到扫码成功 → 等到 timeout → **不保存 cookie**。
**修复**：双重判断——URL 变化 **或** cookie 里出现 `wedoc_sid`（登录成功的真正标志），任一满足即成功。`wecom_login.py` 已实现此逻辑。
**`--status-file` 参数**：后台跑 `wecom_login.py --status-file /tmp/login_status.json`，调用方轮询 JSON 文件即可自动检测扫码完成，不需要用户说"扫完了"。状态值：`qr_ready` → `waiting_scan` → `scanned` → `success`/`timeout`/`error`。

### 步骤 2：检查 cookie 有效性

```python
async def check_cookies(state_file):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=['--no-sandbox'])
        context = await browser.new_context(storage_state=state_file)
        page = await context.new_page()
        await page.goto("https://doc.weixin.qq.com/home/recent",
                        wait_until="domcontentloaded", timeout=15000)
        await asyncio.sleep(3)
        valid = "login" not in page.url.lower()
        await browser.close()
        return valid
```

**Cookie 有效期**：约 2 周。核心 cookie 是 `wedoc_sid` 和 `wedoc_ticket`。

### 主动提醒：cookie 到期前 4 天通知用户（2026-06-26 团队负责人要求，2026-07-15 提前到 4 天）

用户要求机器人在 cookie 过期前**主动提醒**扫码续期，而不是等过期了才发现。
2026-07-15 用户进一步要求："以后你过期前就提醒我，不要过期了再跟我说" — cookie 预警从 2 天提前到 4 天（7 天寿命过半即提醒）。

**生产环境 storage_state 路径**（本机实际使用，三个文件必须保持同步）：
- `~/.config/wecom-doc/states/_shared.json` — 主力（`wecom_login.py` 扫码脚本写入此文件，所有检查脚本优先读此文件）
- `~/.config/wecom-doc/workspace/wecom_browser_state.json` — 备用（同步脚本读此文件）
- `~/.config/wecom-doc/workspace/wecom_cookies.json` — `wecom_auto_renew.py` 的 COOKIE_FILE（cron 续期检查用）
- ⚠️ 三个文件必须同步更新！2026-06-27 踩坑：扫码续期后只更新前两个、漏了第三个 → cron 读旧文件发误告警

**检查方法**：读 storage_state JSON → 遍历 cookies → 找 `wedoc_sid` 的 `expires` 字段（Unix 时间戳）→ 距过期 < 2 天则提醒用户。

**续期命令**：
```bash
cd ./scripts
python3 wecom_login.py --state ~/.config/wecom-doc/states/_shared.json --qr /tmp/wecom_qr.png --timeout 300
```
QR 生成后通过企微发给用户扫码，扫完自动保存新 storage_state。

**⚠️ 发送 QR 图片必读（2026-06-14 + 2026-07-08 两次踩坑）**：
- `MEDIA:/tmp/wecom_qr.png` 会被 gateway 的 `media_delivery_allow_dirs` 白名单**静默拦截**（`/tmp/` 不在白名单），用户看不到图片且无报错
- **必须先复制到白名单目录**再发：`cp /tmp/wecom_qr_rgb.png ~/.config/wecom-doc/workspace/wecom_qr_send.png` 然后 `MEDIA:~/.config/wecom-doc/workspace/wecom_qr_send.png`
- QR 还需转 RGB（1-bit grayscale PNG 企微客户端无法渲染）：`Image.open(qr).convert('RGB').resize((800,800), Image.NEAREST).save(qr_rgb)`
- 如果企微发图仍失败，双保险发飞书：`send_message(target=feishu, message="MEDIA:~/.config/wecom-doc/workspace/wecom_qr_send.png")`
- 详见 `references/wecom-messaging.md` 踩坑1

同时复制到**所有三个**路径（缺一不可，否则 cron 监控读旧文件会误告警）：
```bash
cp ~/.config/wecom-doc/states/_shared.json ~/.config/wecom-doc/workspace/wecom_browser_state.json
cp ~/.config/wecom-doc/states/_shared.json ~/.config/wecom-doc/workspace/wecom_cookies.json
```

可用 `scripts/check_cookie_expiry.py` 自动检查过期状态。

### 步骤 3：获取全量数据（两种方式）

#### 方式 A：拦截页面自动加载的响应

```python
import base64, zlib

async def fetch_via_intercept(state_file, doc_url):
    """拦截 dop-api/get/sheet 响应，base64+zlib 解压"""
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
                try: sheet_data = await response.json()
                except: pass
        page.on('response', on_response)

        await page.goto(doc_url, wait_until='networkidle', timeout=60000)
        await asyncio.sleep(5)
        await browser.close()

    if not sheet_data:
        raise Exception("未捕获 dop-api 响应（cookie 可能已过期）")

    # ⚠️ 必须 urlsafe_b64decode + 默认 zlib（不传 wbits）
    text_data = sheet_data['data']['initialAttributedText']['text'][0]['smartsheet']
    decoded = base64.urlsafe_b64decode(text_data)
    decompressed = zlib.decompress(decoded)
    return json.loads(decompressed.decode('utf-8'))
```

#### 方式 B：主动 fetch（推荐，需拦截 xsrf + 完整参数 + base64+zlib 解码）

```python
async def fetch_via_active_fetch(state_file, doc_url, doc_id, sheet_id=None):
    """主动 fetch dop-api startrow=0，smartsheet 字段是 base64+zlib 压缩格式。
    必须先拦截页面首次 get/sheet 请求获取 xsrf 等动态参数。"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=['--no-sandbox'])
        context = await browser.new_context(storage_state=state_file)
        page = await context.new_page()
        await page.route("**/*.woff*", lambda r: r.abort())
        await page.route("**/*.ttf", lambda r: r.abort())

        # ⚠️ 关键1：拦截页面首次 get/sheet 请求获取 xsrf 等动态参数
        captured_params = None
        def _on_req(req):
            nonlocal captured_params
            if 'dop-api/get/sheet' in req.url and not captured_params:
                qs = parse_qs(urlparse(req.url).query)
                captured_params = {k: v[0] for k, v in qs.items()}
        page.on("request", _on_req)

        await page.goto(doc_url, wait_until='networkidle', timeout=60000)
        await asyncio.sleep(5)
        if not captured_params:
            return {"error": "未拦截到 get/sheet 请求，无法获取 xsrf"}

        xsrf = captured_params.get("xsrf", "")
        rev = captured_params.get("rev", "")

        # 从 collab_client_vars 获取 workbook（子表列表）
        workbook = await page.evaluate("""() => {
            const ccv = window.clientVars?.collab_client_vars;
            if (!ccv) return null;
            const iat = ccv.initialAttributedText;
            if (!iat || !iat.text || !iat.text[0]) return null;
            return iat.text[0].workbook ? JSON.parse(iat.text[0].workbook) : null;
        }""")

        # 确定子表列表
        all_sheets = [s for s in (workbook or []) if s.get("type") == "smartsheet"]
        target_sheets = [s for s in all_sheets if s["id"] == sheet_id] if sheet_id else all_sheets

        results = []
        for sh in target_sheets:
            # ⚠️ 关键2：必须用完整参数集，不能只用最简参数
            api_url = (
                f"https://doc.weixin.qq.com/dop-api/get/sheet"
                f"?padId={doc_id}&subId={sh['id']}"
                f"&startrow=0&endrow=99999&xsrf={xsrf}"
                f"&outformat=1&normal=1&nowb=1&needSheetState=2"
                f"&rev={rev}&optimizedVer=2"
                f"&chunkCellSize=15000&enableChunkRank=1&enablePermOpt=0"
            )
            # JS 端返回原始 smartsheet 字符串（base64+zlib），不在此解析
            result = await page.evaluate("""async (url) => {
                const r = await fetch(url, {credentials: 'include'});
                const j = await r.json();
                const item = j?.data?.initialAttributedText?.text?.[0];
                if (!item) return { error: j.errmsg || 'no text item' };
                return {
                    ok: true,
                    total_record_count: item.total_record_count,
                    smartsheet: item.smartsheet,  // base64+zlib 原始字符串
                };
            }""", api_url)
            if result.get("ok"):
                # ⚠️ 关键3：Python 端解码 base64+zlib
                ss_raw = result["smartsheet"]
                padding = 4 - len(ss_raw) % 4
                if padding != 4: ss_raw += "=" * padding
                decoded = base64.urlsafe_b64decode(ss_raw)
                decompressed = zlib.decompress(decoded)
                parsed = json.loads(decompressed.decode("utf-8"))
                # parsed 可能双层嵌套 [[items...]]，取第一层
                if parsed and isinstance(parsed[0], list): parsed = parsed[0]
                results.append({"sheet": sh["name"], "parsed": parsed})
        await browser.close()
        return results
```

**⚠️ 关键纠正（2026-06-29 实测，推翻 2026-06-13 的错误结论）**：
- `startrow=0` 主动 fetch 返回的 `smartsheet` 字段是 **base64+zlib 压缩格式**（以 `eJ` 开头），**不是** JSON 字符串
- 之前认为 "startrow=0 返回 JSON 字符串、startrow=61+ 返回 base64+zlib" 是**错误的**，两种方式返回的都是 base64+zlib
- 解码方式：`base64.urlsafe_b64decode` + `zlib.decompress` + `json.loads`（与拦截方式完全一致）
- **必须传完整参数集**：`xsrf`, `needSheetState=2`, `rev`, `optimizedVer=2`, `chunkCellSize=15000`, `enableChunkRank=1`, `enablePermOpt=0`。只传 `padId+subId+startrow+endrow+outformat+normal` 会返回 `retcode 538002: "Get content error"`
- `xsrf` 和 `rev` 是动态参数，必须从页面首次 `get/sheet` 请求中拦截获取，不能硬编码
- 多子表：不需要切换 tab，用同一套参数+不同 `subId` 即可 fetch 所有子表
- 从 `collab_client_vars.initialAttributedText.text[0].workbook` 获取子表列表（JSON 字符串需 `JSON.parse`）
- `endrow=99999` 不影响性能，API 自动返回实际全量
- `text[0]` 是包装对象 `{smartsheet: "base64+zlib...", workbook: "JSON字符串", total_record_count: N, max_row: N}`

### 微文档 w3_ 读取（opendoc API）

**关键发现（2026-06-14）**：w3_ 微文档使用 **canvas 渲染**，DOM 提取只能拿到工具栏文字。必须用 `dop-api/opendoc` API 获取完整正文。

详见 `references/w3-opendoc-extraction.md`。

### 思维导图 m4_ 读取（dop-api/get/mind）

**关键发现（2026-06-14）**：m4_ 思维导图 DOM 只能拿到工具栏。数据在 `dop-api/get/mind` 返回的 `item[0].content` JSON 节点树中。URL 前缀 `m4_` → `mind`。

详见 `references/m4-mind-extraction.md`。

### 步骤 4：解析数据

详见 `references/dop-api-data-structure.md`。核心要点：

**两种格式的行数据位置**：

| 来源 | 格式 | 行数据路径 | 是否需要解压 |
|------|------|-----------|-------------|
| 页面自动加载 | base64+zlib（k前缀键） | `parsed[0][0].c.k2.k1` | ✅ urlsafe_b64decode + zlib |
| 主动 fetch | base64+zlib（k前缀键） | 解码后找 t=3028 → `.c.k2.k1` | ✅ urlsafe_b64decode + zlib |

**⚠️ 两种来源返回格式一致**：都是 base64+zlib 压缩，解码后都是 k 前缀键结构。不要假设主动 fetch 返回"纯 JSON"（2026-06-29 实测推翻此错误结论）。

**字段值提取**：

```python
def extract_cell_value(cell):
    """根据 k30（字段类型）提取单元格值"""
    k30 = cell.get('k30') or cell.get('30')
    if k30 == 1:  # 文本
        k1 = cell.get('k1') or cell.get('1', [])
        return k1[0].get('k2', k1[0].get('2', '')) if k1 and isinstance(k1[0], dict) else ''
    elif k30 == 17:  # 单选 → 返回 option_id，需要映射
        k17 = cell.get('k17') or cell.get('17', [])
        return k17[0] if k17 else ''
    elif k30 in (10, 11):  # 创建人/编辑人 → 返回 user_id
        k17 = cell.get('k17') or cell.get('17', [])
        return k17[0] if k17 else ''
    elif k30 in (12, 13):  # 创建时间/编辑时间 → 毫秒时间戳
        k32 = cell.get('k32') or cell.get('32', 0)
        return k32  # 转 datetime: datetime.fromtimestamp(k32/1000)
    elif k30 == 19:  # 公式/引用
        k36 = cell.get('k36') or cell.get('36', {})
        k1 = k36.get('k1', k36.get('1', ''))
        try:
            parsed = json.loads(k1)
            return parsed.get('data', [{}])[0].get('text', '')
        except: return ''
    return ''
```

### 步骤 5：select 选项映射（从 sheet 数据列定义提取）

**⚠️ 这是 2026-05-28 最终方案：不需要 opendoc，直接从 sheet 数据的列定义提取。**

```python
def extract_select_options(parsed_data):
    """从 t=3005 列定义项提取所有 select 选项映射"""
    select_options = {}  # {field_id: {option_id: option_text}}

    # 找到 t=3005 的列定义项
    col_meta = None
    for item in parsed_data[0] if isinstance(parsed_data, list) else parsed_data.get('0', []):
        if isinstance(item, dict) and item.get('t') == 3005:
            col_meta = item
            break

    if not col_meta:
        return select_options

    # 列定义路径：c.3.3 (数字键) 或 c.k3.k3 (k前缀)
    c = col_meta.get('c', {})
    field_defs = c.get('3', c.get('k3', {})).get('3', c.get('3', c.get('k3', {})))

    for fid, fmeta in field_defs.items():
        k17 = fmeta.get('17', fmeta.get('k17'))
        if k17 and isinstance(k17, dict):
            k3 = k17.get('3', k17.get('k3'))
            if k3 and isinstance(k3, list):
                select_options[fid] = {
                    opt.get('1', opt.get('k1', '')): opt.get('2', opt.get('k2', ''))
                    for opt in k3
                }

    return select_options
```

### 多子表处理（v2.1 默认读取所有子表）

dop-api 默认只返回当前激活的子表。`wecom_doc_reader.py` v2.1 实现了**自动遍历所有子表（包括隐藏的）**：

```python
# 从初始响应中提取 workbook
workbook_json = text_arr[0].get('workbook', '[]')
workbook = json.loads(workbook_json)
# [{"id": "q979lj", "name": "表1", "hidden": false}, ...]

# v2.1 逻辑（v2.0 只读非隐藏，v2.1 改为全部读取）：
# 1. 如果用户指定了 sheet_id，只读该子表
# 2. 否则自动遍历所有子表（包括 hidden=true 的）
# 3. 每个子表单独 fetch（subId 参数）
# 4. 每条记录带 _sheet_id 标识来源
```

**关键点**：
- 每个子表的 field_id 不同，需分别提取字段定义（`_parse_column_defs`）
- 使用 `current_tab` 区分"页面默认 tab"和"用户指定 tab"
- 避免在 `async with` 外访问 `page`（browser 已关闭）

**⚠️ 两个关键 Pitfall（2026-06-15 踩坑）**：

1. **`async with` 作用域 bug**：多子表遍历循环必须在 `async with async_playwright()` 块**内部**。如果把 `await browser.close()` 放在第一次 fetch 后、循环放在 `async with` 外面，会报 `TargetClosedError: Page.evaluate: Target page, context or browser has been closed`。修复：把整个多子表逻辑（解析 workbook → 遍历 sheets → 逐表 fetch → 关闭 browser）都放在 `async with` 内部。

2. **`current_tab` vs `sheet_id` 混淆**：页面加载后 URL 会自动追加 `&tab=q979lj`（默认激活的子表）。如果把这个自动追加的 tab 当作 `sheet_id` 使用，会导致"用户没指定 tab → 但代码认为用户指定了 → 只读一个子表"。**正确做法**：
   - `current_tab`：从页面 URL 提取，仅用于第一次 fetch（获取 workbook 列表）
   - `sheet_id`：仅来自用户输入（URL 参数或函数参数），用于判断"用户是否指定了特定子表"
   - 如果 `sheet_id` 为空 → 读取所有非隐藏子表；如果非空 → 只读指定子表

**e3_ 电子表格多子表**：
- 自动遍历底部 `.tab-bar-item-title` 元素获取所有子表名称
- 逐个点击 tab → 隐藏遮罩 → Ctrl+A/C → 剪贴板提取
- 结果带 `sheets`（子表名称列表）和 `sheet_count` 字段

---

