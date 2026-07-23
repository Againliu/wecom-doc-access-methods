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

# 2. Set your WeCom MCP API key (from admin console → AI Helper → MCP config)
export WECOM_MCP_APIKEY=your_key_here

# 3. Read any document (browser path — no row limit)
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
| **SmartPage** (智能文档) | `/smartdoc/` | ✅ | ✅ create + images | MCP export (read) + MCP create (write). No edit API — recreate |
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

## Reference Documentation

| File | What's inside |
|------|--------------|
| `references/mcp-api-guide.md` | MCP JSON-RPC direct-call guide: endpoint, payload, error codes |
| `references/testing-plan.md` | Full E2E test plan for AI agents (18 cases + 7 pitfalls) |
| `references/pitfalls.md` | All known pitfalls across every doc type |
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
| **v5.3.0** | **Browser write**: e3_ spreadsheet cell-level write via mutation API (applyMutation + await commitMutation → WS USER_CHANGES → server persistence verified). Quick Start + dependency table in README. |
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

v5.3.0 · Updated 2026-07-23

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

v5.3.0 · 2026-07-23 · MIT License
