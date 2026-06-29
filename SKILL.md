---
name: wecom-doc-access-methods
version: 4.1.5
description: >
  企微文档读取 Skill。以下 4 种文档类型已通过完整实测验证：
  ① s3_ 智能表格 — dop-api 全量结构化读取，多子表自动遍历，select 选项映射，用户字段解析，2000 条以上全量获取；
  ② e3_ 电子表格 — 原生 JS API (getCellDataAtPosition) 直读内存，合并单元格精确范围填充（含 mergeList 行号偏移处理），图片原始 URL，日期自动转换，多子表切换读取；
  ③ w3_ 微文档 — opendoc API 完整正文提取（canvas 渲染适配），HYPERLINK 标记清理；
  ④ m4_ 思维导图 — dop-api/get/mind 完整 JSON 节点树递归提取（适配 children.attached 结构）。
  表单(form)、幻灯片(slide)、流程图(flowchart)等类型仅走 DOM 兜底，未做专项验证。
---
---

# 企微文档稳定读取 — 通用 Skill

## 适用场景

- 需要读取企微智能表格（`s3_`）或微文档（`w3_`）的数据
- **优先使用浏览器 dop-api 方案**（结构化 JSON，无列错位，全量数据）— 2026-06-29 建哥要求
- MCP `get_doc_content` 仅用于快速浏览/简单场景（返回 Markdown，多子表时有 `|` 列错位风险）
- MCP 授权过期（errcode 851014 / 2200063）时浏览器方案是唯一可用路径
- 需要突破 MCP 2000 条硬限制获取全量数据
- 需要给其他 Agent 系统集成企微文档读取能力

## 企微文档完整类型列表

| 类型 | API doc_type | URL 前缀 | MCP 支持 | 浏览器读取方式 | 数据质量 |
|------|-------------|---------|---------|-------------|---------|
| 微文档 | DOC (3) | `w3_` → `/doc/w3_xxx` | ✅ | **opendoc API**（canvas 渲染，DOM 无效） | ✅ 完整正文 |
| 电子表格 | SHEET (4) | `e3_` → `/sheet/e3_xxx` | ❌ | **SpreadsheetApp 原生 JS API**（v3.1 实测）。`getCellDataAtPosition` 直接读值+合并范围+图片URL | ✅ 内存直读，合并精确，图片原始URL |
| 智能表格 | SMARTSHEET (10) | `s3_` → `/smartsheet/s3_xxx` | ✅(2000条限制) | dop-api 全量结构化 | ✅ 完整字段+选项 |
| 思维导图 | MIND | `m4_` → `/mind/m4_xxx` | ❌ | **dop-api/get/mind**（JSON 节点树） | ✅ 完整节点 |
| 收集表 | FORM | `/form/...` | ❌ | DOM 文本提取 | ✅ |
| 幻灯片 | SLIDE | `/slide/...` | ❌ | DOM 文本提取 | ✅ |
| 流程图 | FLOWCHART | `/flowchart/...` | ❌ | DOM 文本提取 | ✅ |
| 汇报 | REPORT | `/report/...` | ❌ | DOM 文本提取 | ⏸️ 待测试 |
| 智能文档 | SMARTDOC | `/smartdoc/...` | ❌ | DOM 文本提取 | ⏸️ 待测试 |

**⚠️ API 创建限制**：官方 API（`create_doc`）仅支持创建 3 种类型：`doc_type=3`（微文档）、`4`（电子表格）、`10`（智能表格）。其他类型（幻灯片、汇报、智能文档等）只能通过企微 UI 创建。

**⚠️ 完整性验证 Pitfall（2026-06-15 踩坑）**：
- 不要凭记忆列出文档类型清单 → 必须交叉验证：① 查官方 API 文档的 doc_type 参数 ② 实际打开企微 UI 创建菜单截图对比
- 2026-06-15 只列了 7 种类型，用户指出还有"汇报"和"智能文档"未覆盖

**说明**: e3_ 电子表格 v3.1.0 实测重构（2026-06-15）：
1. **SpreadsheetApp 原生 JS API**（主力，最稳定）：`sheet.getCellDataAtPosition(row, col)` 直接读单元格值、合并范围、图片原始 URL。**800 cells < 1ms**
2. **剪贴板 HTML**（降级）：当原生 API 不可用时，Ctrl+A/C → clipboard.read() → 解析 colspan/rowspan
3. **xlsx 导出**（降级）：需编辑权限
4. **剪贴板 TSV / DOM**（最终兜底）

**🚨 实测关键发现（2026-06-15 v3.1）**：
- **`getCellDataAtPosition(row, col)`** 是企微表格引擎的原生 JS API，直接读取内存中的 cell 数据
- `cell.getValue()` 返回值（字符串/数字），`cell.getMergeReference()` 返回精确合并范围
- `cell.getExtendedValue()` 返回图片原始 URL（如 `https://wdcdn.qpic.cn/...?w=4096&h=2304`）
- **非活跃 tab 数据懒加载**：必须先点击 tab + 等待 5 秒数据加载后才能读取
- dop-api 对 e3_ 返回 protobuf 二进制（非 JSON），v2.x 的 JSON.parse 代码从未真正跑通过
- 详见 `references/e3-native-js-api.md`

**⚠️ 历史教训（v2.x → v3.1 的演进）**：
- v2.x：假设 dop-api 返回 JSON → 代码从未跑通（protobuf 格式）
- v3.0：用剪贴板 HTML → 14/15 成功但图片列丢失、合并边界不精确
- v3.1：发现原生 JS API → 直接读内存，最稳定最完整

**⚠️ 合并单元格处理（2026-06-15 v2.7.0 关键改进）**：
- 灌溉日志、日历、分组表头等大量使用合并单元格的子表，用纯文本 TSV 提取后列名丢失、数据错位
- 策略2（HTML）通过解析 `<td colspan="N" rowspan="M">` 还原合并结构
- 策略3（xlsx）通过 openpyxl 的 `merged_cells.ranges` 精确获取合并范围
- 两者都将合并区域内的所有单元格填充为左上角的值

## 用户隔离架构（多用户 Agent 系统必做）

当 skill 被集成到多人使用的 Agent 系统时，**必须按 user_id 隔离 cookies**：

```
wecom_states/
├── user_alice.json     # Alice 的 storage_state
├── user_alice.lock     # 并发锁（fcntl.flock）
├── user_bob.json       # Bob 的 storage_state
└── user_bob.lock
```

设计要点：
- 每个 user_id 独立扫码、独立 cookies、独立过期检测
- 用 `fcntl.flock()` 文件锁防止同一用户并发登录导致 cookies 互相覆盖
- `user_id` 需做安全字符过滤（`re.sub(r'[^\w\-.]', '_', user_id)`）
- 权限检测：打开文档后检查 body 是否含"暂无权限"/"申请权限"

## 方案速查

| 方案 | 推荐度 | 数据完整性 | 稳定性 | 写能力 | 维护成本 |
|------|--------|-----------|--------|--------|----------|
| **Playwright + dop-api** | **✅ 首选** | ✅ 全量 | ⚠️ 中（cookie ~2周） | ❌ | 中（定期扫码续期） |
| **MCP API** | ⚠️ fallback | ⚠️ 前2000条 | ✅ 高 | ✅ | 低（授权过期重分享） |

**推荐策略**：**优先用浏览器 dop-api 方案**（结构化 JSON，无列错位风险，全量数据）。MCP `get_doc_content` 返回 Markdown 纯文本，多子表拼接时单元格内 `|` 字符导致列错位（2026-06-29 实测 24 子表技术工单表，31-39 列旧格式子表大量错位），仅作为快速浏览/简单场景的 fallback。需要写操作时用 MCP（浏览器方案只读）。

---

## 方案二（fallback）：MCP API

> ⚠️ 仅用于快速浏览/简单场景。返回 Markdown 纯文本，多子表时有 `|` 列错位风险（详见 Pitfalls）。需要写操作时也可用 MCP（浏览器方案只读）。

```yaml
mcp_servers:
  企业微信文档:
    url: "https://qyapi.weixin.qq.com/mcp/robot-doc?apikey=YOUR_KEY"
```

### 能力范围

- ✅ `s3_` 智能表格：可读写
- ✅ `w3_` 微文档：可读（异步轮询）
- ❌ `e3_` 旧格式：不支持（errcode 851000）
- ❌ `w3_` blankpage：不支持（errcode 851003）

### 调用方式

```python
import requests, json

def mcp_call(mcp_url, tool_name, arguments):
    """直接调 MCP Server JSON-RPC"""
    payload = {
        "jsonrpc": "2.0", "method": "tools/call",
        "params": {"name": tool_name, "arguments": arguments}, "id": 1
    }
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    resp = requests.post(mcp_url, json=payload, headers=headers, timeout=60)
    data = resp.json()
    if "error" in data:
        raise Exception(f"MCP error: {data['error']}")
    inner = json.loads(data["result"]["content"][0]["text"])
    if inner.get("errcode", 0) != 0:
        raise Exception(f"API error: {inner.get('errmsg')} (errcode={inner.get('errcode')})")
    return inner

# 读智能表格
sheets = mcp_call(URL, "smartsheet_get_sheet", {"url": doc_url})
records = mcp_call(URL, "smartsheet_get_records", {"url": doc_url, "sheet_id": sheet_id})

# 读微文档（异步轮询）
result = mcp_call(URL, "get_doc_content", {"url": doc_url, "type": 2})
if result.get("task_id") and not result.get("task_done"):
    import time; time.sleep(2)
    result = mcp_call(URL, "get_doc_content", {"task_id": result["task_id"], "type": 2})
```

### 已知限制

1. **2000 条硬限制**：`smartsheet_get_records` 最多返回 2000 条，`has_more: true` 但分页参数（offset/cursor/start）**全部无效**
2. **授权过期**：errcode 851014 / 2200063，需文档所有者重新分享给机器人
3. **应用隔离**：只能读写应用自己创建的文档，或成员主动分享的文档

### 授权流程

文档所有者在企微打开文档 → 右上角「分享」→ 搜索并添加机器人应用 → 给阅读权限

### Pitfalls

- ❌ 不要尝试分页，始终返回前 2000 条
- ❌ 授权不是永久的，会过期
- ✅ 增量同步不受 2000 条限制（新增/修改都能拿到）
- ✅ 写操作（upsert/delete）没有数量限制

---

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

### 主动提醒：cookie 到期前 2 天通知用户（2026-06-26 建哥要求）

用户要求机器人在 cookie 过期前**主动提醒**扫码续期，而不是等过期了才发现。

**生产环境 storage_state 路径**（本机实际使用，三个文件必须保持同步）：
- `/root/.hermes/scripts/wecom_states/_shared.json` — 主力（`wecom_login.py` 扫码脚本写入此文件，所有检查脚本优先读此文件）
- `/root/.hermes/workspace/wecom_browser_state.json` — 备用（同步脚本读此文件）
- `/root/.hermes/workspace/wecom_cookies.json` — `wecom_auto_renew.py` 的 COOKIE_FILE（cron 续期检查用）
- ⚠️ 三个文件必须同步更新！2026-06-27 踩坑：扫码续期后只更新前两个、漏了第三个 → cron 读旧文件发误告警

**检查方法**：读 storage_state JSON → 遍历 cookies → 找 `wedoc_sid` 的 `expires` 字段（Unix 时间戳）→ 距过期 < 2 天则提醒用户。

**续期命令**：
```bash
cd /root/.hermes/skills/devops/wecom-doc-access-methods/scripts
python3 wecom_login.py --state /root/.hermes/scripts/wecom_states/_shared.json --qr /tmp/wecom_qr.png --timeout 300
```
QR 生成后通过企微发给用户扫码，扫完自动保存新 storage_state。同时复制到**所有三个**路径（缺一不可，否则 cron 监控读旧文件会误告警）：
```bash
cp /root/.hermes/scripts/wecom_states/_shared.json /root/.hermes/workspace/wecom_browser_state.json
cp /root/.hermes/scripts/wecom_states/_shared.json /root/.hermes/workspace/wecom_cookies.json
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
| 主动 fetch | 纯 JSON（数字键） | `parsed[0][1].c.2.1` 或直接 `.c.2.1` | ❌ |

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

## Pitfalls（血泪教训汇总）

### 解码相关
- ⚠️ **必须** `base64.urlsafe_b64decode`，不是 `b64decode`（企微用 URL-safe base64）
- ⚠️ **必须** `zlib.decompress(decoded)` 默认参数，不要传 `-zlib.MAX_WBITS`
- ⚠️ 如果 base64 报错 "invalid characters"，试加 padding：`raw + '=' * (4 - len(raw) % 4)`

### opendoc 陷阱
- ❌ **不要依赖 opendoc 拿 select 选项映射**。主动 fetch opendoc 返回自定义文本格式（非 JSON），且 `initialAttributedText.text` 经常为空字符串
- ✅ select 选项从 `get/sheet` 的 t=3005 列定义项直接提取
- ⚠️ opendoc 主动 fetch 返回格式：头部 `text\ntext\n84835\n` + URL 编码 JSON，需 `urllib.parse.unquote` + `json.JSONDecoder().raw_decode`

### startrow 陷阱
- ⚠️ 页面默认加载的 `get/sheet` 只含 startrow=61+ 的部分
- ✅ 主动 fetch 时必须传 `startrow=0` 才能拿全量
- ✅ endrow 设多大（99999）都不影响性能
- ⚠️ **startrow=0 返回的 smartsheet 字段是 base64+zlib 压缩格式**（2026-06-29 实测推翻之前错误结论），不是 JSON 字符串，需 `urlsafe_b64decode + zlib.decompress + json.loads`
- ⚠️ **主动 fetch 必须传完整参数集**：`xsrf`, `needSheetState=2`, `rev`, `optimizedVer=2`, `chunkCellSize=15000`, `enableChunkRank=1`, `enablePermOpt=0`。只传最简参数（padId+subId+startrow+endrow+outformat+normal）返回 `retcode 538002: "Get content error"`
- ⚠️ **xsrf 和 rev 是动态参数**，必须拦截页面首次 `get/sheet` 请求获取，不能硬编码
- ✅ **多子表不需要切换 tab**：从 `collab_client_vars.initialAttributedText.text[0].workbook` 获取子表列表后，用同一套参数+不同 `subId` 即可 fetch 所有子表

### Cookie / 登录相关
- ⚠️ 必须用 `storage_state`（Playwright 完整状态），不是纯 cookies
- ⚠️ cookie 约 2 周过期，需要定期检查和续期
- ⚠️ 不能直接 HTTP POST dop-api（需要页面上下文中的 xsrf token），必须通过 Playwright 页面导航触发
- ⚠️ **"扫码续期" 语境歧义**（2026-06-26 踩坑）：用户说"扫码续期"时，先确认是哪个系统——① 浏览器 cookie（storage_state，~2周过期）② MCP 机器人授权（errcode 851014，不定期过期）③ 飞书 token（自动续期，不需要手动）。不要默认跳到飞书 token
- ⚠️ **QR 码图片格式**（2026-06-26 踩坑）：Playwright 拦截到的企微登录二维码是 **1-bit grayscale PNG**，企微客户端**无法渲染**会显示裂图。必须转 RGB 再发送：`Image.open(qr).convert('RGB').resize((800,800), Image.NEAREST).save(qr_v2)`
- ⚠️ **MCP errcode 区分**（2026-06-26 实测）：监控检测时区分三种 errcode——851014/2200063=授权过期（需告警）；851003=无此文档权限但授权有效（正常）；851000=无效URL但授权有效（正常）。检测脚本应用 smartsheet_get_sheet + 假URL，只有 851014/2200063 才告警
- ✅ **主动续期提醒**（2026-06-26 用户要求）：cookie 到期前 2 天主动提醒用户扫码；MCP 授权过期即时告警。用 `scripts/wecom_doc_auth_check.py` + crontab 每日检测，有异常才输出（静默=正常）
- ⚠️ **🚨 三个 cookie 文件必须同步**（2026-06-27 踩坑 — 误告警根因）：生产环境有**三个** cookie 文件，扫码续期后必须**全部更新**，否则监控 cron 读到旧文件会发误告警：
  - `/root/.hermes/scripts/wecom_states/_shared.json` — **主力**（`wecom_login.py` 扫码脚本写入此文件）
  - `/root/.hermes/workspace/wecom_browser_state.json` — **备用**（同步脚本 `monitor_wecom_sync.py` 读此文件）
  - `/root/.hermes/workspace/wecom_cookies.json` — **`wecom_auto_renew.py` 读此文件**（cron 续期检查用）
  - **踩坑场景**：6/26 晚扫码续期只更新了 `_shared.json` + `wecom_browser_state.json`，漏了 `wecom_cookies.json` → 6/27 早 09:00 cron 读旧文件报"剩余 1.6 天"误告警 → 用户困惑"昨晚刚搞过怎么又要搞"
  - **修复**：`wecom_auto_renew.py` 改为优先读 `_shared.json`（fallback 到 `wecom_cookies.json`），续期时同时写两个文件
  - **铁规**：任何 cookie 更新操作（扫码续期 / `wecom_login.py` / `wecom_auto_renew.py`）后，必须验证三个文件的 `wedoc_sid` expires 时间一致

### 🚨 不要混淆三种认证机制（2026-06-26 踩坑）
企微文档相关有**三套独立的认证**，用户说"续期/授权"时要先判断是哪个：

| 认证机制 | 作用 | 过期表现 | 续期方式 |
|---------|------|---------|---------|
| **飞书 token** (lark-cli) | 飞书 API 操作 | `expiresAt` 到期 | `feishu_token_keepalive.py` 自动续期，**不需手动** |
| **企微 MCP 授权** (errcode 851014) | MCP 工具调企微文档 API | errcode 851014 | 用户在企微点授权链接重新授权机器人 |
| **企微浏览器 cookie** (storage_state) | Playwright + dop-api 全量读取 | cookie 跳转登录页 | `wecom_login.py` 扫码登录，**约 2 周过期** |

**判断顺序**：用户说"续期"→ 先想是哪套 → 飞书 token 有自动续期不用管 → MCP 报 851014 才是 MCP 授权 → 用户说"扫码"多半是浏览器 cookie → 不确定就问，不要猜。
**踩坑场景**：用户说"扫码续期"，我误启动飞书 lark-cli QR 登录，用户纠正"不是飞书 token，是企微文档"。

### crontab 环境
- ⚠️ crontab PATH 极简（`/usr/bin:/bin`），调外部 CLI（如 lark-cli shebang `#!/usr/bin/env node`）会报 `No such file or directory`
- ✅ 修复：脚本内显式注入 PATH 到 `subprocess.run` 的 `env` 参数
- ⚠️ crontab 分钟避开整点（用 :07/:13/:17/:23/:37/:43），整点是 API 调用高峰

### Hermes cron `no_agent=true` script 参数（2026-06-27 踩坑 — cron 自创建以来一直 error）
- ⚠️ `no_agent=true` 的 cron job，`script` 参数必须是**相对文件名**（如 `wecom_doc_auth_check.py`），不是 shell 命令（如 `python3 /root/.hermes/scripts/wecom_doc_auth_check.py 2>&1`）
- ❌ 写成 shell 命令时，cron 框架把整个字符串当文件路径找 → `Script not found: /root/.hermes/scripts/python3 /root/...` → `last_status: "error"` 静默失败
- ✅ 正确写法：`script: "wecom_doc_auth_check.py"`（相对于 `~/.hermes/scripts/`）
- ⚠️ `.sh`/`.bash` 后缀走 bash 执行，其他后缀（`.py`）走 Python 执行
- ⚠️ 这种错误**不会告警**——cron 正常 schedule 但每次执行都失败，只有手动查 `last_status` 或看 `~/.hermes/cron/output/<job_id>/` 下的日志才发现

### Cron 合并原则（2026-06-27 踩坑 — 两个 cron 功能重叠）
- ⚠️ 不要为同一个检查创建多个 cron——如一个 LLM 驱动（`wecom_auto_renew.py` 检查 cookie）+ 一个纯脚本（`wecom_doc_auth_check.py` 检查 cookie + MCP），功能重叠，前者还浪费 LLM token
- ✅ 合并为一个纯脚本 cron（`no_agent=true`），覆盖所有检查项（cookie 过期 + MCP 授权）
- ✅ LLM 驱动的 cron 只用于需要推理的任务（如反思、分析），简单检查用纯脚本
- ⚠️ cron 里的自动续期功能（生成 QR + 等待扫码）在无人值守场景不实用——用户不一定在线。改为：cron 检测异常 → 推送告警 → 用户看到后主动触发续期
- ✅ 发现多个 cron 功能重叠时，自行分析合理性并合并，不要把决策抛给用户

### lark-cli 读写参数
- ⚠️ **读取**（`+record-list`）**必须加 `--format json`**，否则返回 markdown 表格，`json.loads` 失败（`Expecting value: line 1 column 1`）
- ⚠️ **写入**（`+record-upsert / +record-delete`）**禁止加 `--format json`**，否则报 `unknown flag: --format`
- ✅ 建议分两个函数：`lark_cli_read(*args)` 加 `--format json`，`lark_cli_write(*args)` 不加

### 文档类型完整性
- ⚠️ **不要假设已覆盖所有文档类型**：企微 UI 可创建的文档类型（9+）远多于 API 支持的（3种）
- ✅ 验证方法：登录官方 API 文档 + 实际打开企微 UI 创建菜单，交叉对比
- ✅ 对于新发现的类型：先获取 URL 前缀，再测试读取方式（dop-api → 剪贴板 → DOM）
- ⚠️ 2026-06-15 踩坑：只列了 7 种类型，用户指出还有"汇报"和"智能文档"未覆盖

### 写操作安全
- ⚠️ lark-cli `+record-upsert` 会**清空未传的字段**（select 类型尤其危险）
- ✅ upsert JSON 必须包含所有字段，即使值为空
- ✅ 生产环境默认 DRY-RUN，确认差异为 0 后才切写入模式
- ⚠️ **严禁在正式文档中写测试数据**：测试验证必须用 MCP 新建临时文档（带 `_测试_` 前缀），测完删除。2026-06-15 踩坑：差点在正式错误码表里加测试字段

### w3_ HYPERLINK 清理
- ⚠️ opendoc API 提取的文本包含 HYPERLINK 标记，需要清理
- ✅ 4 种格式的完整正则清理（2026-06-15 实测验证）：
  1. `HYPERLINK url text` — 简单格式
  2. `HYPERLINK \l "url" text` — 带参数（`\l`、`\h`、`\n` 等）
  3. `HYPERLINK "url" text` — 带引号 URL
  4. `HYPERLINK url text` — 残留关键字（无 URL）
- ✅ 清理逻辑：先处理带引号的复杂格式，再处理简单格式，最后清理残留关键字
- 详见 `scripts/wecom_doc_reader.py` 的 `_decode_wecom_text()` 函数

### e3_ 多子表切换延迟
- ⚠️ 切换 tab 后需要等待足够时间让 canvas 完全渲染（5s），否则剪贴板提取会拿到空数据
- ✅ v2.1 将等待时间从 3s 增加到 5s，解决最后一个子表偶尔 0 行的问题
- 详见 `scripts/wecom_doc_reader.py` 的 `_try_clipboard_for_spreadsheet()` 函数

### e3_ HTML 多子表遍历（v2.7.0 新增）
- ⚠️ `_try_clipboard_html_all_sheets` 会逐个切换 tab 并对每个子表做 Ctrl+A/C → 读 HTML clipboard
- ⚠️ 每次切换 tab 后必须重新隐藏 operate-board 遮罩层
- ⚠️ tab 元素在切换后 DOM 可能变化，需要重新 `query_selector_all('.tab-bar-item-title')`
- ✅ 如果 HTML clipboard 不可用，自动降级到纯文本 TSV（对该子表）
- ✅ 每条记录带 `_sheet_name` 字段标识来源子表

### e3_ xlsx 导出需要编辑权限
- ❌ **只读文档无法导出 xlsx**：点击"导出"→"本地Excel表格(.xlsx)"后，企微会弹出"申请编辑权限"对话框而不是触发下载
- ✅ xlsx 策略失败时自动降级到 HTML/TSV，不影响整体读取
- ⚠️ 文件菜单按钮的 DOM ID 是 `#headerbar-filemenu`，不是文本选择器 `text="文件"`
- ⚠️ 菜单按钮在 Playwright viewport 外（x=-9988），必须用 `page.evaluate('el.click()')` 绕过 viewport 检查

### e3_ 原生 JS API 是最佳方案（🚨 2026-06-15 v3.1 实测确认）
- ✅ **`sheet.getCellDataAtPosition(row, col)` 直接读内存**：`cell.getValue()` 返回值，800 cells < 1ms
- ✅ **`cell.getMergeReference()` 返回精确合并范围**：`{startRowIndex, endRowIndex, startColIndex, endColIndex}`
- ✅ **`cell.getExtendedValue()` 返回图片原始 URL**：如 `https://wdcdn.qpic.cn/...?w=4096&h=2304`
- ⚠️ **非活跃 tab 数据懒加载**：必须先点击 `.tab-bar-item-title` + `wait_for_timeout(5000)` 后才能读
- ❌ dop-api 返回 protobuf 二进制（非 JSON），v2.x 的 JSON.parse 从未跑通
- ❌ 剪贴板 HTML 需要模拟键盘操作，图片列只拿 base64，不如原生 API
- 详见 `references/e3-native-js-api.md`

### e3_ dop-api 返回 protobuf 二进制（🚨 2026-06-15 v3.0 实测确认）
- ❌ **dop-api/get/sheet 对 e3_ 返回 `related_sheet` 字段是 base64+zlib 压缩的 protobuf 二进制**，不是 JSON
- ❌ v2.x 的 `_try_dop_for_spreadsheet` 试图 `JSON.parse(item.smartsheet)` — e3_ 的 `smartsheet` 是**空字符串**
- ✅ 数据在 `item.related_sheet` 字段中（base64 url safe → zlib decompress → protobuf 二进制）
- ✅ 解压后可见中文 sheet 名和图片 URL（`https://wdcdn.qpic.cn/...`），但整体是 protobuf 格式，无法直接解析
- ✅ 替代方案：JS Runtime `SpreadsheetApp.workbook` 提供已解码的元数据（sheet 列表/名称/mergeList）

### e3_ 含图片/附件列的子表必须走 dop-api（2026-06-15 踩坑）
- ❌ **剪贴板只复制 base64 图片**：如"宣传工作日志"等含图片列的子表，Ctrl+A/C 后剪贴板里只有 `<img src="data:image/png;base64,...">` 标签，完全没有文字数据
- ❌ **截图+VL OCR 也不可行**：截图是缩略图（模糊、不完整、丢失原始 URL），建哥明确否决
- ✅ **必须走 dop-api**：dop-api 返回的原始 JSON 中包含图片列的原始 URL（非 base64 缩略图）
- ⚠️ 图片/附件列的 k31 类型 ID 尚未确认（已知 k31 映射：1=文本, 2=数字, 5=日期, 17=单选, 19=公式），需进一步实测

### async_playwright 必须带括号
- ❌ `async with async_playwright as p:` — 报错 `TypeError: 'function' object does not support the asynchronous context manager protocol`
- ✅ `async with async_playwright() as p:` — 正确用法（需要调用函数获取 context manager）

### 🚨 MCP get_doc_content 多子表 Markdown 解析（2026-06-29 踩坑 — 技术工单表 24 子表实测）
- **场景**：用 MCP `get_doc_content(type=2)` 读取含多个子表的智能表格，返回的是所有子表拼接的 Markdown 纯文本
- **🚨 陷阱 1 — 不同子表列数不同**：同一个文档的 24 个子表有三种列结构（25列旧格式 / 31-39列过渡格式 / 12-14列新格式）。用固定列数解析会导致数据丢失或列错位。**必须逐个子表独立解析表头**。
- **🚨 陷阱 2 — `|` 字符导致列错位**：Markdown 表格用 `|` 分隔列，但单元格内容含 `|`（如"模块A|模块B"）会拆出额外列。31-39列旧格式子表受影响最严重（问题描述列经常含 `|`）。**缓解**：检测行 cell 数 > 表头列数时合并多余列；大量行受影响时考虑替换 `|` 为制表符后 CSV 解析；报告中标注"此子表分类不准"。
- **🚨 陷阱 3 — 排序子表标记后解析会破坏边界**：`grep -n '^## '` 拿到标记后，**不能先排序再计算范围**。排序后相邻标记在原文中不相邻，`end_line = 下一个标记行号 - 1` 可能 < `start_line`，产生空范围。**正确流程**：保持原始顺序计算范围 → 逐表解析 → 解析完成后再排序输出。
- **陷阱 4 — 重复子表**：实测发现某些子表数据完全重复（工单ID一致）。需检测并在报告中标注，不计入总数。
- **陷阱 5 — 列名模糊匹配**：不同格式子表列名不同但语义相同（"故障模块" vs "产品模块"）。用 `in` 或正则模糊匹配，不要求精确匹配。
- **用户纠正**：用户指出"他不是很多子表吗，按子表来梳理" — 不要只按第一个子表的格式解析全部数据，必须识别多子表结构并逐表处理。
- **适用场景**：`get_doc_content` 适合快速浏览/分析/分类汇总；精确同步用 `smartsheet_get_records`（JSON，无列错位风险）。
- 详见 `references/mcp-get-doc-content-multisheet-parsing.md`（含解析脚本模板 + 数据质量检查清单 + 与 smartsheet_get_records 对比表）

### 验证充分性原则（2026-06-15 用户纠正）
- ❌ 不要只测一个子表就声称"全部成功"
- ✅ 多子表文档必须全量遍历验证，逐个报告每个子表的行数/列数/合并单元格数
- ✅ 报告格式：表格形式列出每个子表的指标，明确标注失败子表和原因

### 🚨 数据完整性验证 ≠ 表面指标（2026-06-15 踩坑）
- ❌ **行数合理 + 合并数 + 图片数 ≠ 数据正确**：v4.0.0 报告"15/15 成功、1443 条、226 合并、9 图片"，但建哥追问"你怎么知道每个单元格的值是对的？"——答不上来
- ✅ **必须做 ground-truth 对比**：随机抽样 N 行 M 列，肉眼对比原始文档 vs 提取结果，确认单元格值、合并边界、图片 URL 完全匹配
- ✅ **建议提供验证脚本**：导出前 20 行为 CSV/Markdown，让用户手动对照关键单元格（表头、日期列、图片列、合并区域）
- ⚠️ 表面指标只能证明"程序跑通了"，不能证明"数据提取正确"。建哥铁规："做事一次做对做专业"，验证必须严格

### 🚨 mergeList 行号偏移（2026-06-15 v4.0.2 修复 — 最容易踩的坑）

- ❌ **mergeList 的行号是 sheet 级别（0=表头行），records 数组是数据级别（0=第一条数据）**，直接当索引用会差 1
- ❌ 表现：合并单元格全部未填充，地块名丢失、列错位（另一个 Agent 反馈的"灌溉日志数据不可用"根因就是这个）
- ✅ **正确转换**：`record_index = merge_row - 1`
- ✅ **填充逻辑**：遍历 mergeList → 起始格 `records[sr-1][header]` 取值 → 填充 `records[sr-1]` 到 `records[er-1]` 的所有空格
- ✅ **验证方法**：spot-check 合并区域第一列（如灌溉日志的 col_0 地块名），逐行确认都有值
- ⚠️ 如果起始格本身为空（原表没填），填充值也是空，这是正确行为（不是 bug）

### 🚨 Skill 建设铁规：未实测的代码不准写进方案（2026-06-15 血泪教训）
- ❌ **v2.x 的 `_try_dop_for_spreadsheet` 方法假设 e3_ 的 dop-api 返回 JSON，写了完整解析代码，但从未实测** — 实际是 protobuf 二进制，代码从来没跑通过
- ❌ **v3.0 把剪贴板 HTML 当主力，xlsx/TSV/DOM 当"降级"，但这些降级方案从未在只读文档上验证过**（xlsx 需要编辑权限、DOM 对 canvas 无效）
- ✅ **正确做法**：先实测每一种数据路径的可行性，确认可用再写代码。不可用的不要写进方案
- ✅ **不要编造降级方案**：如果某条路径没验证过，不要写"降级到 XX"，标注为"未验证"或直接不写
- ✅ **追求最直接的方案**：能用原生 API 就不要模拟键盘，能用内存数据就不要走剪贴板

---

## 故障处理速查

| 错误码 | 含义 | 解决方案 |
|--------|------|----------|
| 851014 | MCP 授权过期 | 重新分享文档给机器人，或切浏览器方案 |
| 2200063 | MCP 授权过期（另一种） | 同上 |
| 851000 | 文档格式不支持（e3_） | 用浏览器方案 |
| 851003 | 文档类型不支持（blankpage） | 用浏览器方案 |
| cookie 过期 | 页面跳转到 login | 重新扫码登录 |
| base64 解码失败 | invalid characters | 换 urlsafe_b64decode + 加 padding |
| retcode 538002 | dop-api "Get content error" | 主动 fetch 缺少必要参数（xsrf/rev/needSheetState等），需拦截页面首次请求获取完整参数集 |

---

## 测试方案

### 单元测试（离线，不需要浏览器）

```bash
cd scripts/
python3 test_wecom_doc_reader.py --offline
```

覆盖：URL 解析、base64+zlib 解码（含 padding 边界）、列定义解析（k前缀/数字键）、select 选项提取。

### 集成测试（在线，需要浏览器+cookie）

```bash
cd scripts/
python3 test_wecom_doc_reader.py --state-dir /path/to/wecom_states --user _shared --url "https://doc.weixin.qq.com/smartsheet/s3_xxx"
```

覆盖：单子表读取、多子表读取（24+子表）、错误处理（无效URL/不存在文档）、性能测试（记录数/耗时）。

### 测试维度

| 维度 | 测试点 | 验证方法 |
|------|--------|----------|
| URL 解析 | s3_/w3_/e3_/m4_ 格式 + scode/tab 参数 | `parse_doc_url()` 返回值断言 |
| 解码 | base64 roundtrip + padding 补齐 + 无效数据 | 编码→解码对比 |
| 列定义 | k前缀/数字键 + select 选项 + 字段类型 | `_parse_column_defs()` 返回值 |
| 单子表 | 指定 tab 读取 + 记录数 + 字段数 + 首条记录 | `read(user, url+tab)` |
| 多子表 | 全量子表 + sheets 数组 + 记录总数一致 + 无空表 | `read(user, url)` |
| 错误处理 | 无效URL + 不存在文档 + 异常捕获 | 返回 `success: False` |
| 性能 | 24子表读取耗时 < 120s | 计时断言 |

---

## GitHub Issue 自动反馈机制

### 原理

skill 在遇到关键错误时，自动在 GitHub 仓库创建 issue（带 `auto-reported` label），实现"问题→反馈→修复"闭环。

### 配置

```bash
# 环境变量（必须）
export GITHUB_TOKEN="ghp_xxx"           # GitHub API token
export GITHUB_REPO="Againliu/wecom-doc-access-methods"  # 仓库（可选，有默认值）
export ISSUE_AUTO="1"                    # 1=自动提交, 0=只打印不提交
```

### 自动触发点

| 触发条件 | issue 标题 |
|---------|-----------|
| 未拦截到 get/sheet 请求 | "dop-api 未拦截到 get/sheet 请求" |
| base64+zlib 解码失败 | "base64+zlib 解码失败 (sheet: xxx)" |
| 其他关键异常 | 按错误类型自动生成 |

### 去重

提交前用 GitHub Search API 检查是否已有同名 open issue，避免重复提交。

### 文件

- `scripts/report_issue.py` — 独立可用的 issue 自动反馈脚本
- `scripts/test_wecom_doc_reader.py` — 完备测试套件（7 大维度）

---

## 支持文件

- `references/e3-native-js-api.md` — **🆕 e3_ 原生 JS API 完整参考**（getCellDataAtPosition 用法、cell 方法列表、图片URL、合并范围、日期转换）
- `references/e3-merge-fill-verification.md` — **🆕 合并填充验证方法论**（三层递进：表面指标→spot-check→ground-truth；mergeList 偏移根因分析）
- `references/dop-api-data-structure.md` — dop-api 完整数据结构参考（字段类型 ID、行列路径、用户映射、**e3_ protobuf 实测结论**）
- `references/e3-spreadsheet-fallback.md` — **e3_ 电子表格读取方案 v3.0**（JS Runtime + clipboard HTML，protobuf 实测）
- `references/e3-vs-s3-dop-api.md` — 🆕 e3_ vs s3_ dop-api 数据结构差异（已废弃，v3.0 统一用 JS Runtime）
- `references/w3-opendoc-extraction.md` — **w3_ 微文档 opendoc API 提取**（canvas 渲染、自定义格式解析、%uXXXX 解码）
- `references/m4-mind-extraction.md` — **m4_ 思维导图读取**（JSON 节点树递归提取）
- `references/wecom-messaging.md` — **WeCom 消息媒体发送指南**
- `references/wecom-media-delivery-debug.md` — **企微图片交付排错指南**
- `references/mcp-get-doc-content-multisheet-parsing.md` — **🆕 MCP get_doc_content 多子表 Markdown 解析**（不同子表列数不同、`|`字符列错位、排序破坏边界、重复子表检测、列名模糊匹配、解析脚本模板）
- `scripts/wecom_login.py` — 扫码登录脚本（生成 QR 码 + 保存 storage_state）
- `scripts/check_cookie_expiry.py` — **🆕 cookie 过期检查**（检查 wedoc_sid/wedoc_ticket 剩余天数，距过期 ≤2 天输出警告，供 cron 主动提醒）
- `scripts/wecom_reader.py` — 通用读取工具（check / fetch / fetch-sheet）
- `scripts/wecom_fetch.py` — 简化版 dop-api fetch
- `scripts/validate_extraction.py` — **🆕 提取结果 ground-truth 验证**（导出子表前 N 行为 CSV，对照原始文档逐列检查）
- `scripts/wecom_doc_auth_check.py` — **🆕 授权状态定时检测**（cookie 过期预警 + MCP 851014 告警，crontab 每日跑，有异常才输出）

---

## 更新日志

- **2026-06-29** (v4.1.5): 🔄 **推荐策略调整 — 浏览器 dop-api 上升为首选方案**
  - **用户要求**：建哥明确指示"以后优先用 wecom-doc-access-methods skill 获取微文档内容"（指浏览器 dop-api 方案）
  - **调整内容**：
    - "方案速查"表格新增"推荐度"列，Playwright dop-api 标为 ✅ 首选，MCP 标为 ⚠️ fallback
    - 方案编号调整：Playwright dop-api → 方案一（首选），MCP → 方案二（fallback）
    - 方案标题加注：（首选）/（fallback）
    - MCP 方案说明加警告：仅用于快速浏览/简单场景，多子表有 `|` 列错位风险
    - "适用场景"更新：第一条明确"优先使用浏览器 dop-api 方案"
  - **背景**：MCP `get_doc_content` 返回 Markdown 纯文本，技术工单表 24 子表实测中 31-39 列旧格式子表因 `|` 字符大量列错位。dop-api 返回结构化 JSON 无此问题。
  - **注**：写操作仍用 MCP（浏览器方案只读）
- **2026-06-29** (v4.1.4): 📄 **MCP get_doc_content 多子表 Markdown 解析 pitfalls + 参考文档**
  - **新增 Pitfall**：MCP `get_doc_content(type=2)` 返回多子表拼接 Markdown 时的 5 个陷阱
  - **陷阱 1**：不同子表列数不同（同一文档 24 子表有 3 种列结构：25列/31-39列/12-14列），必须逐表独立解析表头
  - **陷阱 2**：单元格内 `|` 字符导致 Markdown 列错位，31-39列旧格式子表受影响最严重
  - **陷阱 3**：排序子表标记后再计算范围会破坏边界（排序后相邻标记在原文不相邻，end_line 可能 < start_line）
  - **陷阱 4**：重复子表检测（实测发现两个子表数据完全重复）
  - **陷阱 5**：列名模糊匹配（"故障模块" vs "产品模块"）
  - **新增参考文档** `references/mcp-get-doc-content-multisheet-parsing.md`：含解析脚本模板、数据质量检查清单、与 smartsheet_get_records 对比表
  - **背景**：用户要求按子表（日期段）梳理技术工单表中 App 相关问题。初次解析只按第一个子表格式处理，遗漏大量数据；后续按时间排序后解析，边界计算错误产出 10000+ 条假数据；最终按原始顺序逐表解析才正确
- **2026-06-27** (v4.1.3): 🔧 **三文件同步 pitfall + 误告警根因修复 + cron 脚本路径修复 + 冗余 cron 合并**
  - **新增 Pitfall**：三个 cookie 文件（`_shared.json` / `wecom_browser_state.json` / `wecom_cookies.json`）必须同步更新
  - **踩坑场景**：扫码续期只更新了前两个文件，漏了 `wecom_cookies.json` → cron 读旧文件报"剩余 1.6 天"误告警 → 用户困惑
  - **修复**：`wecom_auto_renew.py` 改为优先读 `_shared.json`，续期时同时写两个文件
  - **铁规**：任何 cookie 更新操作后，必须验证三个文件的 `wedoc_sid` expires 时间一致
  - **更新续期命令**：`cp` 从 2 个文件改为 3 个文件
  - **新增 Pitfall**：Hermes cron `no_agent=true` 的 `script` 参数必须是**相对文件名**（如 `wecom_doc_auth_check.py`），不是 shell 命令。写成 shell 命令会导致 `Script not found` 静默失败（cron `693f2df31eb8` 自创建以来一直 error）
  - **新增 Pitfall**：不要为同一检查创建多个 cron。删除冗余的 LLM 驱动 cookie 检查 cron（`327db8642204`），保留纯脚本 cron（`693f2df31eb8`）统一检查 cookie + MCP 授权
- **2026-06-26** (v4.1.2): 🔧 **认证机制区分 + cookie 主动提醒**
  - **新增 Pitfall**: 不要混淆三种认证机制（飞书 token / 企微 MCP 授权 851014 / 企微浏览器 cookie storage_state）— 踩坑场景：用户说"扫码续期"，误启动飞书 lark-cli QR 登录，实际是企微浏览器 cookie 续期
  - **新增主动提醒机制**: cookie 到期前 2 天主动通知用户扫码续期（建哥要求机器人及时提醒）
  - **新增生产环境 storage_state 路径**: `/root/.hermes/scripts/wecom_states/_shared.json`（主力）+ `/root/.hermes/workspace/wecom_browser_state.json`（备用）
  - **新增脚本** `scripts/check_cookie_expiry.py`: 检查 cookie 剩余天数，距过期 ≤N 天输出警告，供 cron 主动提醒
  - **背景**: 企微文档浏览器 cookie 约 2 周过期，之前没有主动提醒机制，总是等过期了才发现
  - **新增 `_read_mind` 方法**：通过 `dop-api/get/mind` API 提取完整 JSON 节点树
  - **路由**：`read()` 方法自动识别 `m4_` 前缀，路由到 `_read_mind`
  - **实测修正**：`initialAttributedText.text` 是 JSON 字符串（非数组），结构为 `{content: [{rootTopic: {...}}]}`
  - **修正**：子节点在 `children.attached` 数组中（非直接在 `children` 下）
  - **修正**：`_extract_mind_nodes` 递归方法适配 `children.attached` 结构
  - **实测**：超级棉田设备关联情况（68 节点，6 层深度，完整设备→轮灌组→阀体编号层级）
  - **更新**：`references/m4-mind-extraction.md` 反映实测真实结构
  - **背景**：另一个 Agent 反馈 m4_ 思维导图读取走 DOM 兜底，只能拿到工具栏文字，建哥要求修复
- **2026-06-15** (v4.0.2): 🔧 **合并单元格填充修复**
  - **修复**：mergeList 行号是 sheet 级别（0=表头行），但 records 数组是数据级别（0=第一条数据），之前未做偏移转换导致合并填充全部失败
  - **修复**：新增合并填充逻辑 — 遍历 mergeList，将起始单元格的值填充到合并范围内的所有空格
  - **验证**：354/354 合并填充检查通过，0 失败；灌溉日志地块名、时间类型等全部正确填充
  - **验证**：图片 URL 全部有效（HTTP 200, image/jpeg）；15/15 子表 1443 行数据完整
  - **教训**：mergeList 行号偏移是最容易踩的坑，必须用 ground-truth 验证（逐行看 col_0 是否都有值）
- **2026-06-15** (v4.0.1): 🔍 **新增 ground-truth 验证 Pitfall + 验证脚本**
  - **新增 Pitfall**：数据完整性验证 ≠ 表面指标（行数+合并数+图片数≠数据正确）
  - **新增脚本** `scripts/validate_extraction.py`：导出指定子表前 N 行为 CSV，附 5 项验证清单（表头完整性、日期格式、合并区域、图片URL、公式结果）
  - **背景**：v4.0.0 报告"15/15 成功、1443 条"但建哥追问"你怎么知道每个单元格的值是对的？"——答不上来。教训：表面指标只能证明程序跑通，不能证明数据正确
- **2026-06-15** (v4.0.0): 🚀 **原生 JS API 完整实现 + 全量验证**
  - **新增 `_read_all_sheets_via_native_api()`**：逐 tab 切换 + `getCellDataAtPosition` 批量读取全部 cell
  - **日期自动转换**：Excel serial number (如 46030) → ISO 日期 (2026-01-08)，含表头行
  - **公式/富文本提取**：`getFormattedValue()` 拿纯文本，不再返回复杂 dict 对象
  - **图片原始 URL**：`getExtendedValue()` 提取 `https://wdcdn.qpic.cn/...?w=4096&h=2304`
  - **合并单元格精确范围**：`getMergeReference()` 返回 `{startRow, endRow, startCol, endCol}`
  - **全量实测**：15/15 子表成功，1443 条记录，226 个合并单元格，9 个图片 URL
  - **降级策略**：原生 API → xlsx 导出 → 剪贴板 HTML → DOM
  - **性能**：800 cells < 1ms（JS 端），总耗时 ~97s（主要 tab 切换等待）
- **2026-06-15** (v3.1.0): 🚨 **发现 e3_ 原生 JS API — 最佳方案**
  - **发现 `getCellDataAtPosition(row, col)`**：企微表格引擎原生 API，直接从内存读单元格值
  - `cell.getValue()` 返回值（800 cells < 1ms）、`cell.getMergeReference()` 精确合并范围、`cell.getExtendedValue()` 图片原始 URL
  - 废弃剪贴板 HTML 作为主力（图片列丢原始 URL、合并边界不精确、依赖模拟键盘）
  - 废弃 dop-api JSON 解析（e3_ 返回 protobuf 二进制）
  - 限制：非活跃 tab 需先切换+等 5 秒加载
  - 新增 `references/e3-native-js-api.md` 完整参考文档
  - 新增 Pitfall：Skill 建设铁规 — 未实测的代码不准写进方案
- **2026-06-15** (v3.0.0): 🚨 **实测重构 e3_ 读取方案**
  - **废弃 `_try_dop_for_spreadsheet`**：实测确认 e3_ 的 dop-api 返回 protobuf 二进制（非 JSON），v2.x 的 JSON.parse 代码从未真正跑通过
  - **新增 `_get_js_runtime_sheets()`**：从 `SpreadsheetApp.workbook` JS 运行时提取 sheet 列表/名称/mergeList/图片URL
  - **重写 `_read_spreadsheet`**：JS Runtime 元数据 + 剪贴板 HTML 为主路径，xlsx/TSV/DOM 为降级
  - **实测验证**：15 子表全量读取成功，684 条记录，JS Runtime 元数据正确匹配每个 sheetId
  - **版本号**：`wecom_doc_reader.py` → v3.0.0
  - **🚨 铁规：e3_ 表格 dop-api 必须先试**：另一个 Agent 用本 skill 读 e3_ 文档，只用了 TSV 导致数据质量严重不可用（列错位、表头丢失、合并结构消失）。建哥明确要求：必须从数据源头（dop-api）获取完整、准确、充分的数据
  - **e3_ dop-api 可用率比预期高**：部分较新的 e3_ 文档通过 `startrow=0` 可返回 JSON（非 protobuf），与 s3_ 解析方式完全一致。更新 `references/e3-spreadsheet-fallback.md` 策略1 从"大多数失败"改为"先试"
  - **含图片/附件列的子表必须 dop-api**：剪贴板只复制 base64 图片，截图+OCR 也不行（缩略图模糊不完整）。"宣传工作日志"实测验证
  - **TSV 明确标为不合格方案**：仅作为最后兜底，不可作为 e3_ 表格的主力读取方式
  - **k31 类型映射待补充**：图片/附件列的类型 ID 尚未确认
- **2026-06-15** (v2.7.1):
  - **多子表 HTML 遍历全量验证**：15 个子表实测 14/15 成功，668 条记录，164 个合并单元格正确还原
  - **新增 Pitfall**：xlsx 导出需要编辑权限（只读文档自动降级）
  - **新增 Pitfall**：文件菜单按钮 DOM ID 是 `#headerbar-filemenu`，在 viewport 外需用 JS click
  - **新增 Pitfall**：`async_playwright()` 必须带括号
  - **新增 Pitfall**：验证充分性原则——多子表必须全量遍历，不能只测一个子表就声称成功
  - **e3-spreadsheet-fallback.md**：补充完整 15 子表测试数据表
- **2026-06-15** (v2.7.0):
  - **e3_ 五级降级策略**：新增剪贴板 HTML（策略2）和 xlsx 导出（策略3），解决合并单元格解析问题
  - **剪贴板 HTML**：`navigator.clipboard.read()` 读 `text/html` MIME，解析 `<table>` 的 `colspan`/`rowspan`，展开合并单元格为二维矩阵
  - **xlsx 导出**：Playwright 触发"文件→导出为→Excel"→ openpyxl 解析 `merged_cells.ranges`，完整保留合并结构 + 所有子表
  - **context 权限**：`_read_spreadsheet` 的 context 创建时统一加 `permissions=["clipboard-read", "clipboard-write"]`
  - **公共方法**：提取 `_do_ctrl_a_c()` 统一处理隐藏遮罩 + mouse.click + Ctrl+A/C
  - **修复来源**：另一个 Agent 反馈灌溉日志等子表合并单元格丢失、列名混入数据行、列错位严重
- **2026-06-15** (v2.6.1):
  - 在 Pitfalls 中增加**完整性验证**条目：不要凭记忆列清单，必须交叉验证官方文档+实际测试
- **2026-06-15** (v2.6.0):
  - **文档类型完整性**：新增"汇报"和"智能文档"两种类型（共 9 种），标注 API 创建限制（仅 3 种）
  - **新增 Pitfall**：不要假设已覆盖所有文档类型，需交叉验证官方 API + UI
  - 账号权限隔离完整验证：并发锁、用户隔离、目录隔离全部通过
- **2026-06-15** (v2.5.0):
  - **s3_ 多子表默认行为调整**：默认读取所有子表（包括隐藏的），可通过 sheet_id 指定单个
  - **w3_ HYPERLINK 清理增强**：支持 4 种格式（带控制字符、带参数、无引号、残留关键字）
  - **e3_ 多子表等待时间优化**：从 3s 增加到 5s，确保 canvas 完全渲染
  - 账号权限隔离完整验证：并发锁、用户隔离、目录隔离
- **2026-06-15** (v2.4.0):
  - **s3_ 多子表自动遍历**：不指定 tab 时自动读取所有非隐藏子表，每条记录带 `_sheet_id` 标识来源
  - **e3_ 多子表自动遍历**：检测 `.tab-bar-item-title` 元素，逐个切换 tab 并剪贴板提取
  - **w3_ 微文档**：opendoc API 完整解析（canvas 渲染，10000+ 字符文档）
  - **m4_ 思维导图**：dop-api/get/mind JSON 节点树递归提取
  - **字段类型常量修正**：SELECT=17（不是 3），FORMULA=19（不是 15）
  - **用户隔离架构**：per-user cookies 独立存储
  - 更新 `references/e3-spreadsheet-fallback.md`：剪贴板提取实现细节（mouse.click 替代 canvas.click，permissions 在 context 创建时授予）
  - 更新 `references/dop-api-data-structure.md`：字段类型常量全量验证 + 新建子表延迟问题
- **2026-06-15** (v2.3.0):
  - **w3_ 微文档**：发现 canvas 渲染，DOM 无效，改用 opendoc API 提取完整正文
  - **m4_ 思维导图**：新增 dop-api/get/mind 提取（JSON 节点树递归）
  - **字段类型常量**：实测验证完整列表（TEXT=1, NUMBER=2, SELECT=3/17, DATE=5, USER=10, EDITOR=11, CREATED_AT=12, UPDATED_AT=13, FORMULA=19）
  - 新增 `references/w3-opendoc-extraction.md` — opendoc 自定义格式解析 + %uXXXX 解码
  - 新增 `references/m4-mind-extraction.md` — 思维导图节点树提取
  - 更新 `references/dop-api-data-structure.md` — 字段类型常量全量验证 + 新建子表延迟问题
- **2026-06-14** (v2.2.0):
  - e3_ 电子表格三级降级读取：dop-api → 剪贴板 TSV → DOM 文本
  - `wecom_doc_reader.py` 升级到 1195 行，新增 `_read_spreadsheet` / `_try_dop_for_spreadsheet` / `_try_clipboard_for_spreadsheet`
  - 新增 lark-cli `--format json` 读写分离 pitfall（读加写不加）
  - 新增 `references/wecom-media-delivery-debug.md` 指针
- **2026-06-14** (v2.1.0):
  - `wecom_doc_reader.py` 升级到 v2.0（810→935行）：用户隔离版 + 向后兼容老 CLI
  - 老版 CLI（`check`/`login`/`fetch`/`fetch-sheet`/`list`）自动检测并路由到 `_legacy_main()`
  - 新版 CLI（`--state-dir` + `login/check/read <user_id>`）支持 per-user 隔离
  - 新增 `references/wecom-messaging.md` — WeCom 图片/文件发送完整指南
  - 新增 `references/wecom-messaging.md` 指针到支持文件列表
- **2026-05-28**：
  - ~~`startrow=0` 主动 fetch 返回的 `text[0].smartsheet` 是 **JSON 字符串**（需 `JSON.parse()`）~~ — **2026-06-29 推翻：实际是 base64+zlib 压缩格式，需 `urlsafe_b64decode + zlib.decompress`**
  - 新增企微文档完整类型列表（7 种：DOC/SHEET/SMARTSHEET/FORM/SLIDE/MIND/FLOWCHART）
  - 新增用户隔离架构章节（多用户 Agent 系统必做）
  - 更新 dop-api-data-structure.md 参考文档
- **v2.0.0 (2026-06-13)**: 整合 wecom-smartsheet-browser-sync + dop-api-data-structure，去除项目特定内容，改为通用 skill
- **v1.0.0 (2026-05-28)**: 初始版本
- **2026-06-29** (v4.2.0):
  - **重大修正**：`startrow=0` 主动 fetch 返回的 `smartsheet` 字段是 **base64+zlib 压缩格式**（以 `eJ` 开头），不是 JSON 字符串。推翻 v2.0.0 (2026-06-13) 的错误结论
  - **关键发现**：主动 fetch 必须传完整参数集（`xsrf`, `needSheetState=2`, `rev`, `optimizedVer=2`, `chunkCellSize=15000`, `enableChunkRank=1`, `enablePermOpt=0`），否则返回 `retcode 538002`
  - **xsrf 获取方案**：拦截页面首次 `get/sheet` 请求的 URL 参数获取，不能硬编码
  - **多子表方案**：从 `collab_client_vars.initialAttributedText.text[0].workbook` 获取子表列表，用同一套参数+不同 `subId` 遍历所有子表，不需要切换 tab
  - **bug 修复**：`_parse_column_defs` 中 `k3 = k17.get("3") or k3.get("k3")` → 修正为 `k17.get("k3")`（typo 导致 UnboundLocalError）
  - `wecom_doc_reader.py` `_read_smartsheet` 方法完全重写：拦截参数 → 获取 workbook → 遍历子表 → base64+zlib 解码 → 结构化输出
  - 新增多子表返回格式（`sheets` 数组），单子表保持向后兼容
  - SKILL.md 方式 B 代码示例和说明完全更新
