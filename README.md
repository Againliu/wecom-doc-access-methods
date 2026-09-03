# 📄 WeCom Document Access — Read & Write Any Enterprise WeChat Document

> One self-contained toolkit for any AI agent to read and write Enterprise WeChat (企业微信/WeCom) documents — smart tables, spreadsheets, micro-docs, mind maps, and SmartPages. No MCP framework required.

**中文版见文末 [中文说明](#中文说明)。**

---

## Why You Need This

WeCom (企业微信) has 10+ document types. The official MCP integration only covers 2 types and caps at 2,000 rows. If you're building an AI agent that needs to read or write WeCom documents, you'd normally have to:

- Reverse-engineer each document type's internal API separately
- Handle MCP token expiration (error 851014)
- Hit the 2,000-row limit on smart tables
- Deal with canvas-based renderers that break text extraction

This skill solves all of that in one package. Every method is tested in production — not theoretical.

## Quick Start (30 seconds)

```bash
# 1. Install
git clone https://github.com/Againliu/wecom-doc-access-methods.git
cd wecom-doc-access-methods
pip install -r requirements.txt && playwright install chromium

# 2. Verify the install REALLY works (3 layers: python pkg / skill files / browser binary)
PYTHONPATH=./scripts python3 -m wecom_doc_reader doctor
#   → playwright install chromium 下载约 165MB，慢/失败也没关系：
#     doctor 会自动 fallback 到系统 Chrome；都没有时输出结构化修复命令

# 3. Set your WeCom MCP API key (from admin console → AI Helper → MCP config)
export WECOM_MCP_APIKEY=your_key_here

# 4. Read any document (browser path — no row limit)
PYTHONPATH=./scripts python3 -m wecom_doc_reader read \
  --user <wecom_userid> --url <doc_url> --state /tmp/state.json

# Or write via MCP (no browser needed):
python3 scripts/wecom_doc_writer.py s3 add --url <url> --sheet-id <id> \
  --records '[{"标题":"hello"}]'
```

**Two credential paths**: MCP API key (writes + fast reads) or browser cookie (reads, no row limit, survives MCP token expiry). See [Installation](#installation) for full setup.

## What Can It Do?

| Doc Type | URL Prefix | Read | Write | Method |
|----------|-----------|:----:|:----:|--------|
| **Smart Table** (智能表格) | `s3_` | ✅ | ✅ CRUD | MCP (write) + browser dop-api (read, no row limit) |
|| **Spreadsheet** (电子表格) | `e3_` | ✅ | ✅ range/append + browser mutation API | MCP (range write) + browser JS API (read) + browser mutation API (cell write, v5.3.0) |
| **Micro-Doc** (微文档) | `w3_` | ✅ | ✅ create/edit* | MCP + browser opendoc API. *Edit only on bot-created docs |
| **SmartPage** (智能画布) | `a1_` `/smartpage/a1_` | ✅ | ✅ create + images | smartcanvasread pure HTTP (read, v5.9.0: first-class doc_type + page tree + completeness metrics, zero browser dependency) + MCP/HTTP write |
| **Mind Map** (思维导图) | `m4_` | ✅ | — | Browser dop-api/get/mind (read only) |
| Form / Slide / Flowchart | `/form/` etc. | ⚠️ | — | DOM text extraction (read only) |

**Write coverage detail:**

| Operation | s3_ | e3_ | w3_ | SmartPage | m4_ |
|-----------|:---:|:---:|:---:|:---------:|:---:|
| Create | ✅ | ✅ (sub-sheet) | ✅ | ✅ (with images) | — |
| Add records/rows | ✅ | ✅ (append) | — | — | — |
| Update | ✅ | ✅ (range) | ✅* | — | — |
| Delete | ✅ | ✅ (sub-sheet) | — | — | — |
| Image embed | — | — | — | ✅ (four-step) | — |

> **Roadmap**: browser-based write paths for e3_/w3_/SmartPage/m4_ (for when MCP can't do the operation — e.g., editing member-created micro-docs, deleting SmartPages, writing to mind maps). These require live API research and are being implemented incrementally.

## Installation

### Prerequisites

- **Python 3.8+**
- **A WeCom account** with access to the documents you want to read/write
- For browser-based reads: **Playwright** + Chromium

### Step 1: Clone

```bash
git clone https://github.com/Againliu/wecom-doc-access-methods.git
cd wecom-doc-access-methods
```

### Step 2: Install Python dependencies

```bash
pip install -r requirements.txt
```

**Dependencies** (only 2 packages):

| Package | Version | Used by |
|---------|---------|---------|
| `playwright` | ≥1.40.0 | `wecom_doc_reader/`, `wecom_login.py`, `wecom_fetch.py` (browser reads) |
| `requests` | ≥2.28.0 | `wecom_doc_writer.py`, `wecom_doc_auth_check.py` (MCP JSON-RPC) |

> All other scripts (`check_cookie_expiry.py`, `report_issue.py`, `test_wecom_doc_reader.py`, `validate_extraction.py`) use **Python stdlib only** — zero extra dependencies.

### Step 3: Install browser (for read paths)

```bash
playwright install chromium
```

> Only needed if you'll use browser-based reading (recommended — it bypasses MCP row limits and token expiration).

### Step 4: Configure credentials

You need **one or both** of these credential sources:

**Option A — MCP API Key** (for MCP read/write paths):

1. Go to your WeCom admin console → AI Helper → MCP configuration
2. Copy the **API Key** from the StreamableHTTP URL
3. Set it as an environment variable:

```bash
export WECOM_MCP_APIKEY=your_api_key_here
```

**Option B — Browser Cookie** (for browser read paths):

```bash
python3 scripts/wecom_login.py --state /tmp/state.json --qr /tmp/qr.png --timeout 300
```

Scan the QR code with your WeCom app. This saves a browser session that lasts ~24 hours.

> **Tip**: Set up both. MCP is faster for writes; browser has no row limits for reads. Cookie expiry is monitored by `check_cookie_expiry.py`.

## Usage — Reading

### Smart Table (`s3_`) — via browser (no row limit)

```bash
PYTHONPATH=./scripts python3 -m wecom_doc_reader read \
  --user <your_wecom_userid> \
  --url "https://doc.weixin.qq.com/smartsheet/s3_xxx?scode=xxx" \
  --state /tmp/state.json
```

Returns: all sheets, all fields, all records, select options, user references — **no 2,000-row cap**.

### Smart Table (`s3_`) — via MCP (faster, for ≤2000 rows)

```bash
python3 scripts/wecom_doc_writer.py s3 sheets --url <url>
python3 scripts/wecom_doc_writer.py s3 fields --url <url> --sheet-id <id>
python3 scripts/wecom_doc_writer.py s3 get --url <url> --sheet-id <id> --limit 100
```

### Spreadsheet (`e3_`) — via browser JS API

```bash
PYTHONPATH=./scripts python3 -m wecom_doc_reader read \
  --user <your_wecom_userid> \
  --url "https://doc.weixin.qq.com/sheet/e3_xxx" \
  --state /tmp/state.json
```

Returns: exact cell values, merged cell ranges, image URLs, dates — 800 cells in <1ms.

### Micro-Doc (`w3_`) — via MCP (async)

```bash
python3 scripts/wecom_doc_writer.py w3 get --url <w3_url>
# Auto-polls until done, returns Markdown content
```

### SmartPage — via MCP export (async)

```bash
python3 scripts/wecom_doc_writer.py smartpage export --url <smartpage_url>
# Auto-polls, returns Markdown with embedded image CDN URLs
```

### Mind Map (`m4_`) — via browser

```bash
PYTHONPATH=./scripts python3 -m wecom_doc_reader read \
  --user <your_wecom_userid> \
  --url "https://doc.weixin.qq.com/mind/m4_xxx" \
  --state /tmp/state.json
```

Returns: complete node hierarchy (central topic → branches → sub-branches).

## Usage — Writing

All write operations go through `scripts/wecom_doc_writer.py` — a unified CLI that calls WeCom's MCP API directly via JSON-RPC over HTTPS. **No MCP client framework needed** — just `requests` + `json`.

### Smart Table (`s3_`) — Full CRUD

```bash
# Add records (simple dict → auto-wrapped to field format)
python3 scripts/wecom_doc_writer.py s3 add \
  --url <url> --sheet-id <id> \
  --records '[{"标题": "hello", "进度": 50}]'

# Update records (needs record_id — get it from s3 get first)
python3 scripts/wecom_doc_writer.py s3 update \
  --url <url> --sheet-id <id> \
  --records '[{"record_id": "r_xxx", "进度": 80}]'

# Delete records
python3 scripts/wecom_doc_writer.py s3 delete \
  --url <url> --sheet-id <id> --record-ids r_aaa,r_bbb
```

### Spreadsheet (`e3_`) — Range write + append

```bash
# Write a 2D array to a range (auto-wrapped to CellData)
python3 scripts/wecom_doc_writer.py e3 update-range \
  --url <url> --sheet-id <id> \
  --start-row 0 --start-col 0 \
  --data '[["姓名","分数"],["张三",95]]'

# Append a single row
python3 scripts/wecom_doc_writer.py e3 append \
  --url <url> --sheet-id <id> \
  --row '["李四",88]'
```

### Spreadsheet (`e3_`) — Browser cell write (mutation API)

For cell-level writes that go through WeCom's OT/mutation sync protocol (verified: reload-persistent), use the browser mutation API. This is useful when you need to write to specific cells beyond MCP's range/append operations.

> See `references/e3-browser-write-research.md` for the full implementation (applyMutation + await commitMutation → WS USER_CHANGES → server persistence).

### Micro-Doc (`w3_`) — Create + edit

```bash
# Create a new doc with content
python3 scripts/wecom_doc_writer.py w3 create \
  --name "会议纪要" --content @meeting.md

# Edit a bot-created doc (⚠️ only works on docs created by the bot — see Troubleshooting)
python3 scripts/wecom_doc_writer.py w3 edit \
  --url <w3_url> --content @updated.md
```

### SmartPage — Create with images (four-step method)

SmartPages support Markdown image syntax, but images must be uploaded through a container document first. The `create-with-images` command automates all four steps:

```bash
# Write your Markdown with local: image placeholders:
# # My Page
# Here's a screenshot:
# ![screenshot](local:/tmp/screenshot.png)

python3 scripts/wecom_doc_writer.py smartpage create-with-images \
  --title "项目周报" \
  --markdown @weekly-report.md \
  --container-url <existing_container_url>  # optional — auto-creates if omitted
```

**What it does:**
1. Creates a container SmartPage (or reuses `--container-url`) for image uploads
2. Uploads each `local:` image to the container → gets CDN URLs
3. Replaces placeholders with `![](cdn_url)` — ⚠️ **English parentheses `()` only!**
4. Creates the final SmartPage with complete content in one call

> **Why a container?** CDN URLs are document-independent. One persistent container serves all your SmartPages. Keep it, don't delete it.

### Upload files/images

```bash
# Upload an image to a document (returns CDN URL)
python3 scripts/wecom_doc_writer.py upload-image \
  --file screenshot.png --doc-url <doc_url>

# Upload any file (returns file_id for smart table ATTACHMENT fields)
python3 scripts/wecom_doc_writer.py upload-file \
  --file report.pdf --file-name "Q3-report.pdf"
```

## Configuration Reference

| Variable | Required? | Purpose |
|----------|-----------|---------|
| `WECOM_MCP_APIKEY` | For MCP paths | WeCom bot's MCP API key (from admin console) |
| `WECOM_MCP_URL` | Alternative | Full MCP endpoint URL (overrides above) |
| `WECOM_USERID` | For browser reads | Your WeCom user ID (for cookie isolation) |
| `WECOM_COOKIE_CHECK_URL` | Optional | Override the cookie-validity check URL (default: `https://doc.weixin.qq.com/home/recent`) |
| `WECOM_RETRY_MAX` | Optional | Max retry attempts (default: 3) |
| `WECOM_RETRY_DELAY` | Optional | Initial retry delay in seconds (default: 2, exponential) |
| `WECOM_RETRY_SHEET_MAX` | Optional | Max per-sheet retries (default: 2) |
| `GITHUB_TOKEN` | Optional | Enables automatic GitHub issue creation on errors (scope: `repo:issues`) |

**No credentials are stored in the repository.** Cookie files go in `scripts/wecom_states/` (gitignored). MCP keys come from environment variables or your agent's config file.

## Troubleshooting

> **Quick diagnosis**: `python3 scripts/wecom_status.py --user <userid>` — checks cookie + MCP key + gives fix suggestions. Full error lookup table: `references/error-mapping.md`.

| Error | Meaning | Fix |
|-------|---------|-----|
| `errcode 850001` | Invalid MCP API key | Re-copy the key from WeCom admin console → AI Helper → MCP config. Verify no characters were dropped. |
| `errcode 851003` | Bot not authorized for this document | Share the document to the bot in WeCom, or use `w3 create` to create a new doc the bot owns. |
| `errcode 851014` | MCP token expired | Re-obtain the MCP API key from admin console. For reads, use the browser path (no MCP needed). |
| `errcode 301085` | `upload_doc_image` missing `url` parameter | Always pass `--doc-url` (the container/document URL). The image upload target must be specified. |
| SmartPage images not rendering | Used Chinese parentheses `（）` | Use **English parentheses `()`** in Markdown: `![](url)` not `![]（url）`. |
| Cookie expired | Browser session timed out (~24h) | Re-run `wecom_login.py` to get a fresh session. |
| `fixture 'reader' not found` | pytest trying to collect browser integration tests | These are integration tests — run via `python3 scripts/test_wecom_doc_reader.py --offline` for unit tests only. |

## Testing

### Unit tests (offline, no browser needed)

```bash
cd scripts/
python3 -m pytest test_wecom_doc_reader.py -v
# or: python3 test_wecom_doc_reader.py --offline
```

19 tests covering: URL parsing (s3_/e3_/w3_/m4_), base64+zlib decoding, field type mapping, column definition parsing, row data extraction, error handling.

### End-to-end test plan (for AI agents)

See **`references/testing-plan.md`** — 18 test cases + 7 known-pitfall checks, designed for AI coding agents (GPT Cowork, Codex, Trea) to execute against a live WeCom environment.

## Included Scripts

| Script | Purpose |
|--------|---------|
| `scripts/wecom_doc_reader/` | Main reader — auto type detection, two-layer retry, 7 modules |
| `scripts/wecom_doc_writer.py` | **Unified writer** — s3_/e3_/w3_/SmartPage/uploads via MCP JSON-RPC |
| `scripts/upload_image.py` | Standalone image upload helper |
| `scripts/wecom_login.py` | QR-code login → browser `storage_state` |
| `scripts/check_cookie_expiry.py` | Cookie expiry watchdog |
| `scripts/wecom_doc_auth_check.py` | MCP auth pre-flight checker (detects 851014/851003) |
| `scripts/wecom_fetch.py` | Low-level dop-api/opendoc fetch utilities |
| `scripts/validate_extraction.py` | Extracted-data validation |
| `scripts/test_wecom_doc_reader.py` | Offline test suite |
| `scripts/report_issue.py` | GitHub issue auto-report with 24h dedup |
| `scripts/wecom_status.py` | One-shot status check: cookie validity + MCP key validity + smoke test |

## Reference Documentation

| File | What's inside |
|------|--------------|
| `references/mcp-api-guide.md` | MCP JSON-RPC direct-call guide: endpoint, payload, error codes |
| `references/testing-plan.md` | Full E2E test plan for AI agents (18 cases + 7 pitfalls) |
| `references/pitfalls.md` | All known pitfalls across every doc type |
| `references/error-mapping.md` | Error lookup: raw error → plain meaning → fix (5 categories) |
| `references/wecom-doc-image-embedding.md` | SmartPage image embedding four-step details |
| `references/e3-native-js-api.md` | Spreadsheet `SpreadsheetApp` JS API reference |
| `references/dop-api-data-structure.md` | Smart table dop-api response structure |
| `references/m4-mind-extraction.md` | Mind map JSON structure + recursion |
| `references/w3-opendoc-extraction.md` | Micro-doc opendoc extraction |
| `references/crud-coverage-gap.md` | CRUD coverage analysis (drives the roadmap) |
| `references/playwright-dop-api-guide.md` | Browser dop-api interception deep-dive |
| `references/retry-mechanism.md` | Reader retry architecture |
| `references/cookie-watchdog.md` | Cookie expiry monitoring |

## Version History

| Version | Key Changes |
|---------|-------------|
| **v5.11.1** | **职责边界修订**（2026-09-03）：本 skill 只管企微文档逻辑（含扫码登录+用户信息捕获）；四渠道/多渠道账号对应关系移至 Agent 侧多用户方案（skill-building-standard）。 |
| **v5.11.0** | **多渠道账号自动入库**（2026-09-02）：四渠道姓名/ID 入库矩阵补齐——企微文档扫码登录自动捕获 `userName`（`login_user` 字段）回写 principal.display_name；飞书 OAuth `verify_profile` 升 3 元返回，授权完成自动回写姓名（不覆盖已验证成员）。新增 `references/multi-channel-account-enrollment-2026-09.md`（四渠道矩阵+改动详情+双存储系统说明）。 |
| **v5.10.0** | **扫码授权体验固化**（来自 8-27 某成员授权案 8 轮返工复盘）：① 新增 `scripts/qr_to_wecom.py`——把 `wecom_auth_flow.py` 拦截的 1-bit PNG 二维码转成 1160×1160 白边 RGB JPEG（企微长按识别一次成功），实测通过。② SKILL.md 精简卡新增「扫码授权铁律」四条（--wait-done 入口 / 发图不发 URL / 等待期后台轮询不空转 / 同一 transaction_id 不重发），修复 8-27 分层改造时误删授权流程导致教训不可见。③ pitfalls.md 新增完整链路复盘条目（三层根因：链接不可用 + 1-bit 裂图 + 教训写错 skill）。**核心教训：教训写错 skill 等于没写——反思类准则要落到实际任务加载的那张卡上。** |
| **v5.9.0** | **安装契约修复 + SmartPage 一等类型**（来自 Codex/macOS v5.8.0 实战反馈）：① `browser.py` 共享启动 helper，统一全部 9 个 `chromium.launch` 点（reader 6 + login/fetch/status 3），fallback 链 `PLAYWRIGHT_EXECUTABLE` → `PLAYWRIGHT_CHANNEL` → 系统 Chrome 自动探测 → bundled Chromium，全失败输出结构化 JSON（缺失层级+已查路径+修复命令），不再甩 traceback。② `doctor` 子命令：三层依赖逐层检查 + 真实 launch→about:blank→close，修复"19/19 离线通过但首次运行无 Chromium"的三层依赖误报（Python 包/Skill 文件/浏览器二进制是独立三层）。③ a1_ 前缀映射 `doc_type=smartpage`，`_read_smartpage` 纯 HTTP 读取（smartcanvasread/opendoc + get_block_filter_by_type 分页），零浏览器依赖，带完整性指标（page_count/block_count/text_length/attachment_count/orphan_block_count/has_more_remaining，如实报告 API 10k 块上限）。④ `wecom_status.py` MCP/浏览器分栏 + MCP 失效自动 fallback 浏览器读取（两通道独立）。⑤ 测试套件离线模式自动跑 doctor，"ALL PASS"改为"离线+doctor 通过（在线未测）"。实测：无浏览器故障态结构化报错 ✅ / npmmirror 镜像装 Chrome 后 doctor 全绿 ✅ / 89 页 10k 块 SmartPage E2E ✅。Chromium 官方 CDN 卡死时用 npmmirror 镜像 45s 下完 168MB（官方 57min 0%）。 |
| **v5.7.1** | **发布链路修复 + 全平台推送**: 修 publish_skill.sh 三个坑（脱敏扫描集≠发布集、curl\|grep -m1 在 pipefail 下 exit 23、GitHub 远端领先需先 rebase）。skill 正文全量脱敏（本地绝对路径改写为 `~` 相对形式、复盘文档人名泛化后全平台发布）、check_cookie_expiry.py 补 expanduser。六端版本闭环验证。 |
| **v5.7.0** | **三周实战复盘系统化**: 新增 `references/retrospective-2026-08.md`，从 27 个会话提取 21 条教训（同步管线专项 L1-L14 + 行为级 B1-B7）。核心新增：企微 HTTP API ret=0 ≠ 生效的假成功清单、发布状态判定必须 version+publish_time+面板态三交叉（权限变更不推 pad_ver 的盲区）、正式文档必须用用户本人身份创建、`listAfter` 是 PREPEND 需逆序提交。 |
| **v5.6.0** | **SmartPage HTTP API 写入突破**: `submit_command` + `Content-Type: application/protojson` 实现创建/删除/移动/改标题全操作，不需要 WebSocket/浏览器。operation 枚举（set=1/listAfter=4/listRemove=5）、block ID 6 字符、`enabled` 为 bool、`childId` 驼峰。新增 `references/smartpage-http-api-write.md`。实测 130 页面全量同步零失败。 |
| **v5.5.0** | **Pro 文档全元素提取 + 扫码自动闭环**: OT mutation 全量解析（正文 8,840 字 + 图片 24 张 + 表格 35 个行列结构 + 批注 11 条 + 附件 6 个 PDF/MP4 + 内部链接 2 条）。`_decode_wecom_text` 保留表格结构标记（`\\x1a`/`\\x1b`/`\\x07`/`\\x06`）。`wecom_auth_flow.py --wait-done` 扫码自动轮询。 |
| **v5.4.0** | **Pro 文档解析**: `isPro:true` 文档正文从 `clientVars.collab_client_vars.initialAttributedText` OT mutation 提取。图片/表格/批注从 `mutation.pr` 提取。运行时副本同步修复。 |
| v5.3.1 | Error mapping reference (`references/error-mapping.md`), `wecom_status.py` status checker, permission model docs. |
| v5.3.0 | **Browser write**: e3_ spreadsheet cell-level write via mutation API (applyMutation + await commitMutation → WS USER_CHANGES → server persistence verified). Quick Start + dependency table in README. |
| v5.2.0 | **Write support**: `wecom_doc_writer.py` unified write entry (s3_ CRUD, e3_ range/append, w3_ create/edit, SmartPage create + image four-step, uploads). Security hardening, E2E test plan. |
| v5.0.0 | Browser-path reads production-hardened; retry mechanism; auth pre-flight |
| v4.5.0 | Two-layer auto-retry, exponential backoff |
| v4.4.0 | Modularization: single 2311-line file → 7-module package |
| v4.2.0 | Smart sheet base64+zlib decoding, full dop-api param set, test suite |
| v4.1.1 | Mind map (`m4_`) support |
| v4.0.0 | Native JS API replaces clipboard for spreadsheets |
| v3.x | Spreadsheet via clipboard HTML (deprecated) |
| v2.x | dop-api JSON parsing (deprecated — returned protobuf) |

## Version

v5.7.1 · Updated 2026-08-24

## License

MIT © Jian Liu 2026

---

## 中文说明

# 📄 企微文档读写工具

一个自包含工具包，让任何 AI Agent 读写企业微信中的**任意文档类型**——智能表格、电子表格、微文档、思维导图、SmartPage。无需 MCP 框架。

### 解决什么问题？

企微文档有 10+ 种类型，官方 MCP 只覆盖 2 种且有 2000 行限制。本工具：

1. **全类型覆盖**——每种文档类型都有经过验证的读写路径
2. **无行数限制**——浏览器路径突破 MCP 2000 条上限
3. **不依赖 MCP 授权**——Token 过期时浏览器路径仍可用
4. **无需 MCP 框架**——所有 MCP 操作封装为纯 JSON-RPC（`requests` + `json`）
5. **安全默认**——仓库零硬编码凭据，全部环境变量

### 安装

```bash
git clone https://github.com/Againliu/wecom-doc-access-methods.git
cd wecom-doc-access-methods
pip install -r requirements.txt
playwright install chromium
```

### 配置凭据（二选一或都配）

```bash
# MCP 方式（读写都可用）
export WECOM_MCP_APIKEY=<从企微后台 AI Helper → MCP 配置获取>

# 浏览器方式（读取，无行数限制）
python3 scripts/wecom_login.py --state /tmp/state.json --qr /tmp/qr.png
# 扫码登录，Cookie 约 24 小时有效
```

### 快速使用

```bash
# 读智能表格（浏览器，无行数限制）
PYTHONPATH=./scripts python3 -m wecom_doc_reader read --user <企微ID> --url <s3_链接> --state /tmp/state.json

# 写智能表格（MCP）
python3 scripts/wecom_doc_writer.py s3 add --url <链接> --sheet-id <子表ID> --records '[{"标题":"测试"}]'

# 创建带图的 SmartPage
python3 scripts/wecom_doc_writer.py smartpage create-with-images --title "周报" --markdown @report.md
```

### 能力矩阵

| 类型 | 读 | 写 | 说明 |
|------|:--:|:--:|------|
| 智能表格 s3_ | ✅ | ✅ CRUD | MCP 写 + 浏览器读（无行数限制） |
| 电子表格 e3_ | ✅ | ✅ 范围/追加 | MCP 写 + 浏览器 JS API 读 |
| 微文档 w3_ | ✅ | ✅ 创建/编辑* | *编辑仅限机器人创建的文档 |
| SmartPage | ✅ | ✅ 创建+图片 | 无编辑 API，改内容只能重建 |
| 思维导图 m4_ | ✅ | — | 只读 |

> **路线图**：浏览器写路径（e3_ 行删除、w3_ 成员文档编辑、SmartPage 删除、m4_ 写入）需要原始 API 调研，正在逐步实现。

### 常见问题

| 错误 | 原因 | 解决 |
|------|------|------|
| 850001 | MCP key 无效 | 从企微后台重新复制（注意别漏字符） |
| 851003 | 机器人无权访问此文档 | 在企微里把文档分享给机器人，或用 `w3 create` 新建 |
| 851014 | MCP Token 过期 | 重新获取 key，或用浏览器路径读取 |
| 图片不渲染 | 用了中文括号 | 必须英文括号 `()` |
| Cookie 过期 | 会话超时（约24h） | 重新运行 `wecom_login.py` |

### 测试

```bash
python3 -m pytest scripts/test_wecom_doc_reader.py -v  # 离线单元测试
# 端到端测试方案见 references/testing-plan.md
```

### 版本

v5.7.1 · 2026-08-24 · MIT License
