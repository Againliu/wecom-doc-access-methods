# 📄 WeCom Document Access — Full CRUD for Enterprise WeChat Documents

[中文](#中文说明)

Read **and write** any document type from Enterprise WeChat (企业微信 / WeCom) programmatically — smart tables, spreadsheets, micro-documents, mind maps, SmartPages, and more. One self-contained skill that any AI agent (with or without an MCP client framework) can integrate in minutes.

## What It Provides

1. **Full CRUD coverage** — read *and* write paths for every major document type, all verified in production
2. **No MCP framework required** — every MCP operation is also wrapped as plain JSON-RPC over HTTPS (`requests` + `json` only)
3. **No row limits** — bypass MCP's 2,000-row cap for smart tables via the browser/dop-api path
4. **No authorization single-point-of-failure** — browser cookie path keeps working when MCP tokens expire
5. **Secure by default** — no hardcoded credentials; everything via environment variables or your own config file

## Quick Start (0 → 1)

```bash
# 1. Clone
git clone https://github.com/Againliu/wecom-doc-access-methods.git
cd wecom-doc-access-methods

# 2. Install
pip install -r requirements.txt
playwright install chromium   # only needed for browser/cookie read paths

# 3. Configure credentials (choose one)
export WECOM_MCP_APIKEY="<your bot's MCP apikey>"     # for MCP read/write paths
#   — get it from your WeCom bot admin console (AI helper → MCP config)
python3 scripts/wecom_login.py --state /tmp/state.json --qr /tmp/qr.png
#   — scan the QR with WeCom app, for browser/cookie read paths

# 4. First read (smart table, no row limit, browser path)
PYTHONPATH=./scripts python3 -m wecom_doc_reader read <wecom_userid> <s3_doc_url> --state /tmp/state.json

# 5. First write (add a record to a smart table, MCP path)
python3 scripts/wecom_doc_writer.py s3 add --url <s3_doc_url> --sheet-id <sheet_id> \
  --records '[{"标题": "hello from CLI"}]'
```

## CRUD Coverage Matrix

| Type | URL Prefix | Read | Create | Update | Delete | Notes |
|------|-----------|:----:|:------:|:------:|:------:|-------|
| Smart Table (智能表格) | `s3_` | ✅ MCP / ✅ browser | ✅ | ✅ | ✅ | MCP write; browser read has no row cap |
| Spreadsheet (电子表格) | `e3_` | ✅ browser JS API | ✅ | ✅ | ⚠️ rows only | range write + append via MCP |
| Micro-Doc (微文档) | `w3_` | ✅ MCP / ✅ browser | ✅ | ✅* | — | *edit only works on bot-created docs (851003 otherwise) |
| SmartPage (智能文档) | `/smartdoc/` or `dop_` | ✅ MCP export | ✅ | ❌ rebuild only | ❌ | no edit API — recreate with full content |
| Mind Map (思维导图) | `m4_` | ✅ browser dop-api | — | — | — | read-only |
| Form / Slide / Flowchart (收集表/幻灯片/流程图) | `/form/` `/slide/` `/flowchart/` | ⚠️ DOM text | — | — | — | read-only, basic text |
| Image / File upload | — | — | ✅ | — | — | `upload_doc_image` / `upload_doc_file` via MCP |

## Write Support — `scripts/wecom_doc_writer.py` (NEW in v5.2.0)

Unified write entry for all MCP-writable types. Pure `requests` + `json` — **no MCP client framework needed**, works from any agent/runtime.

```bash
# s3_ smart table
wecom_doc_writer.py s3 sheets --url <url>                     # list sheets
wecom_doc_writer.py s3 fields --url <url> --sheet-id <id>     # list fields
wecom_doc_writer.py s3 get    --url <url> --sheet-id <id> --limit 10
wecom_doc_writer.py s3 add    --url <url> --sheet-id <id> --records '[{"标题":"x","进度":50}]'
wecom_doc_writer.py s3 update --url <url> --sheet-id <id> --records '[{"record_id":"r_x","进度":80}]'
wecom_doc_writer.py s3 delete --url <url> --sheet-id <id> --record-ids r_a,r_b

# e3_ spreadsheet — plain 2D arrays, auto-wrapped to CellData
wecom_doc_writer.py e3 info --url <url>
wecom_doc_writer.py e3 update-range --url <url> --sheet-id <id> \
  --start-row 0 --start-col 0 --data '[["姓名","分数"],["张三",95]]'
wecom_doc_writer.py e3 append --url <url> --sheet-id <id> --row '["李四",88]'

# w3_ micro-doc
wecom_doc_writer.py w3 create --name "标题" --content @doc.md
wecom_doc_writer.py w3 edit   --url <url> --content @doc.md
wecom_doc_writer.py w3 get    --url <url>          # async-polls until done, returns Markdown

# SmartPage
wecom_doc_writer.py smartpage create --title "标题" --pages '[{"page_title":"页1","content":"# 内容"}]'
wecom_doc_writer.py smartpage create-with-images --title "标题" --markdown @page.md \
  [--container-url <image-container-url>]
wecom_doc_writer.py smartpage export --url <url>

# uploads
wecom_doc_writer.py upload-image --file img.png --doc-url <container/doc url>
wecom_doc_writer.py upload-file  --file a.zip
```

Simple data structures are auto-wrapped: scalars → field-value format, 2D arrays → `CellData` grids. Pass `@file.json` / `@file.md` for larger payloads.

## SmartPage Image Embedding — Four-Step Method (verified)

SmartPages support Markdown image syntax `![](cdn_url)`, but images must first be uploaded through `upload_doc_image` against a container document:

1. **Create a container SmartPage** (once, reuse forever) → get its `url`
2. **Upload image** to the container: `upload_doc_image(base64_content=..., url=<container url>)` → returns `https://wdcdn.qpic.cn/...` CDN URL
3. **Reference in Markdown**: `![](<cdn_url>)` — ⚠️ **English parentheses `()` only**; Chinese parentheses `（）` silently fail to render
4. **Create the final SmartPage** with the complete content in one call

`create-with-images` automates all four steps — write `![alt](local:/abs/path.png)` placeholders in your Markdown, it uploads each and substitutes the CDN URLs. CDN URLs are document-independent, so one persistent container serves all your SmartPages.

Known SmartPage limits: no `edit_doc_content` support (recreate instead), no delete API, 4K images auto-scale.

## Read Support — `scripts/wecom_doc_reader/`

Auto-detects document type (s3_/e3_/w3_/m4_) and picks the right method, with **two-layer auto-retry** (per-sheet + whole-operation). Modular package: `constants.py`, `utils.py`, `parsers.py`, `reader.py`, `cli.py`.

| Type | Method | Data Quality |
|------|--------|-------------|
| `s3_` | dop-api full structured extraction (base64+zlib decoded) | ✅ complete fields, options, user refs, **unlimited rows** |
| `e3_` | Native JS API `getCellDataAtPosition()` memory read | ✅ exact merged cells, image URLs, dates — 800 cells < 1ms |
| `w3_` | opendoc API full content extraction | ✅ complete body with formatting |
| `m4_` | dop-api/get/mind recursive JSON tree | ✅ complete node hierarchy |
| form/slide/flowchart | DOM text extraction | ⚠️ basic text |

**Technical depth**: smart-sheet cells are base64+zlib JSON (prefix `eJ`); the reader intercepts the page's initial `get/sheet` request for dynamic `xsrf`/`rev` params, then fetches each sub-sheet with the full parameter set — missing any returns retcode 538002. Spreadsheet merged cells need `getMergeReference()` + mergeList row-offset correction. See `references/` for full write-ups.

## Configuration

| Source | Priority | Purpose |
|--------|----------|---------|
| `WECOM_MCP_URL` | 1 | Full MCP endpoint URL (with apikey) |
| `WECOM_MCP_APIKEY` | 2 | Just the key; URL is composed automatically |
| agent config file | 3 | fallback — an `mcp_servers` entry containing `robot-doc` in `~/.hermes/config.yaml` or `~/.openclaw/config.yaml` if present |
| `WECOM_USERID` | — | default WeCom userid for browser read paths |
| `WECOM_RETRY_MAX` / `WECOM_RETRY_DELAY` / `WECOM_RETRY_SHEET_MAX` | — | reader retry tuning |
| `GITHUB_TOKEN` | — | optional, enables GitHub issue auto-report (`repo:issues` scope) |

No credentials are stored in the repo. Browser/cookie paths use the `storage_state` file you generate via `wecom_login.py` — keep it out of version control (`.gitignore` already covers `scripts/wecom_states/`).

## All Scripts

| Script | Purpose |
|--------|---------|
| `scripts/wecom_doc_reader/` | Main reader — auto type detection, two-layer retry |
| `scripts/wecom_doc_writer.py` | **Unified writer (v5.2.0)** — s3_/e3_/w3_/SmartPage/uploads via MCP JSON-RPC |
| `scripts/upload_image.py` | Standalone image upload helper |
| `scripts/wecom_login.py` | QR-code login → browser `storage_state` |
| `scripts/check_cookie_expiry.py` | Cookie expiry watchdog |
| `scripts/wecom_doc_auth_check.py` | MCP authorization status checker (851014/851003 pre-flight) |
| `scripts/wecom_fetch.py` | Low-level dop-api / opendoc fetch utilities |
| `scripts/validate_extraction.py` | Extracted-data validation |
| `scripts/test_wecom_doc_reader.py` | Offline test suite |
| `scripts/report_issue.py` | GitHub issue auto-report with 24h dedup |

## Testing

```bash
python3 -m pytest scripts/test_wecom_doc_reader.py -v   # offline unit tests
```

End-to-end test plan (18 cases + 7 known-pitfall checks, designed for AI coding agents to execute): **`references/testing-plan.md`**.

## Reference Documentation

| File | Contents |
|------|----------|
| `references/mcp-api-guide.md` | MCP JSON-RPC direct-call guide — endpoint, payload shape, error codes |
| `references/testing-plan.md` | Full E2E test plan for AI agents |
| `references/pitfalls.md` | All known pitfalls across every doc type |
| `references/playwright-dop-api-guide.md` | Browser dop-api interception deep-dive |
| `references/dop-api-data-structure.md` | Smart-table dop-api response structure |
| `references/e3-native-js-api.md` | Spreadsheet native JS API reference |
| `references/e3-spreadsheet-fallback.md` | e3 strategy evolution: v2.x → v3.0 → v3.1 |
| `references/e3-merge-fill-verification.md` | Merged-cell row-offset correction |
| `references/e3-vs-s3-dop-api.md` | e3 vs s3 dop-api differences |
| `references/m4-mind-extraction.md` | Mind-map JSON structure + recursion |
| `references/w3-opendoc-extraction.md` | Micro-doc opendoc extraction |
| `references/wecom-doc-image-embedding.md` | SmartPage image embedding four-step details |
| `references/mcp-get-doc-content-multisheet-parsing.md` | MCP multi-sheet parsing pitfalls (`\|` column misalignment) |
| `references/retry-mechanism.md` | Reader retry architecture |
| `references/cookie-watchdog.md` | Cookie expiry monitoring |
| `references/crud-coverage-gap.md` | CRUD coverage analysis (drives the roadmap) |

## Version History

| Version | Key Changes |
|---------|-------------|
| **v5.2.0** | **Write support**: new `wecom_doc_writer.py` unified write entry (s3_ records CRUD, e3_ range write/append, w3_ create/edit, SmartPage create + image four-step, file/image upload). SmartPage image-embedding method documented & automated. Security hardening: all credentials → env vars, repo fully desensitized, publish-time secret scanning. New `references/testing-plan.md` E2E suite |
| v5.0.0 | Browser-path reads for s3_/e3_/w3_/m4_ production-hardened; retry mechanism; auth pre-flight checker |
| v4.5.0 | Two-layer auto-retry, exponential backoff, non-retryable error detection |
| v4.4.0 | Modularization: single 2311-line file → 7-module package |
| v4.2.0 | Smart sheet base64+zlib decoding, full dop-api param set, test suite, issue auto-report |
| v4.1.1 | Mind map (`m4_`) support |
| v4.0.0 | Native JS API replaces clipboard approach for spreadsheets |
| v3.x | Spreadsheet via clipboard HTML (deprecated) |
| v2.x | dop-api JSON parsing (**deprecated** — actually protobuf, never worked) |

## Version

v5.2.0 · Updated 2026-07-22

## License

MIT © Jian Liu 2026

---

## 中文说明

# 📄 企微文档读写 — 企业微信全类型文档 CRUD 方案

编程读写企业微信中的**任意文档类型**——智能表格、电子表格、微文档、思维导图、SmartPage 等。一个自包含 Skill，任何 AI Agent（有无 MCP client 框架）都能几分钟内接入。

## 核心能力

1. **全类型 CRUD 覆盖**——每种主要文档类型都有经过验证的读写路径
2. **不依赖 MCP 框架**——所有 MCP 操作都封装为纯 JSON-RPC HTTPS 调用（只需 `requests` + `json`）
3. **无行数限制**——浏览器/dop-api 路径突破 MCP 2000 条智能表格上限
4. **授权无单点故障**——MCP Token 过期时浏览器 cookie 路径仍可用
5. **默认安全**——仓库零硬编码凭据，全部走环境变量或本地配置

## 快速上手（0→1）

```bash
# 1. 克隆
git clone https://github.com/Againliu/wecom-doc-access-methods.git
cd wecom-doc-access-methods

# 2. 装依赖
pip install -r requirements.txt
playwright install chromium   # 仅浏览器/cookie 读取路径需要

# 3. 配凭据（二选一或都配）
export WECOM_MCP_APIKEY="<你的机器人 MCP apikey>"   # MCP 读写路径
python3 scripts/wecom_login.py --state /tmp/state.json --qr /tmp/qr.png   # 扫码，cookie 读取路径

# 4. 第一次读（智能表格，无行数限制）
PYTHONPATH=./scripts python3 -m wecom_doc_reader read <企微userid> <s3_文档链接> --state /tmp/state.json

# 5. 第一次写（智能表格加记录）
python3 scripts/wecom_doc_writer.py s3 add --url <s3_文档链接> --sheet-id <子表id> \
  --records '[{"标题": "hello from CLI"}]'
```

## CRUD 覆盖矩阵

| 类型 | URL 前缀 | 读 | 增 | 改 | 删 | 说明 |
|------|---------|:--:|:--:|:--:|:--:|------|
| 智能表格 | `s3_` | ✅ MCP / ✅ 浏览器 | ✅ | ✅ | ✅ | MCP 写；浏览器读无行数上限 |
| 电子表格 | `e3_` | ✅ 浏览器 JS API | ✅ | ✅ | ⚠️ 仅行 | MCP 范围写入 + 追加 |
| 微文档 | `w3_` | ✅ MCP / ✅ 浏览器 | ✅ | ✅* | — | *只能改机器人创建的文档（否则 851003） |
| SmartPage 智能文档 | `/smartdoc/` | ✅ MCP 导出 | ✅ | ❌ 只能重建 | ❌ | 无编辑 API，写错只能重做 |
| 思维导图 | `m4_` | ✅ 浏览器 dop-api | — | — | — | 只读 |
| 收集表/幻灯片/流程图 | `/form/` 等 | ⚠️ DOM 文本 | — | — | — | 只读，基础文本 |
| 图片/文件上传 | — | — | ✅ | — | — | `upload_doc_image` / `upload_doc_file` |

## 写能力 — `scripts/wecom_doc_writer.py`（v5.2.0 新增）

统一写入口，纯 `requests` + `json`，**无需 MCP client 框架**，任意 Agent/运行时可用。简单数据结构自动包装：标量 → 字段值格式，2D 数组 → `CellData` 网格。用法见上文英文区命令表（参数完全一致）。

## SmartPage 图片嵌入四步法（已验证）

1. **建容器 SmartPage**（一次性，长期复用）→ 拿访问链接
2. **上传图片到容器**：`upload_doc_image(base64_content=..., url=<容器链接>)` → 返回 `wdcdn.qpic.cn` CDN URL
3. **Markdown 引用**：`![](<cdn_url>)`——⚠️ **必须英文括号 `()`**，中文括号 `（）` 不渲染
4. **一次性创建正式 SmartPage**

`create-with-images` 命令自动完成全部四步——Markdown 里写 `![alt](local:/绝对路径.png)` 占位符即可。CDN URL 与文档无关，一个持久容器服务所有 SmartPage。

已知限制：SmartPage 不支持 `edit_doc_content`（写错只能重建）、无删除 API、4K 图自动缩放。

## 读能力 — `scripts/wecom_doc_reader/`

自动识别文档类型（s3_/e3_/w3_/m4_）选择对应方法，**两层自动重试**（子表级 + 整体级）。各类型提取细节见英文区与 `references/`。

## 配置

| 来源 | 优先级 | 用途 |
|------|--------|------|
| `WECOM_MCP_URL` | 1 | 完整 MCP 端点 URL（含 apikey） |
| `WECOM_MCP_APIKEY` | 2 | 仅 key，自动拼 URL |
| agent 配置文件 | 3 | 兜底——`~/.hermes/config.yaml` 或 `~/.openclaw/config.yaml` 中含 `robot-doc` 的 `mcp_servers` 条目 |
| `WECOM_USERID` | — | 浏览器读取路径的默认企微 userid |
| `WECOM_RETRY_MAX` / `WECOM_RETRY_DELAY` / `WECOM_RETRY_SHEET_MAX` | — | 读取器重试调优 |
| `GITHUB_TOKEN` | — | 可选，启用 GitHub issue 自动反馈 |

仓库不存任何凭据。cookie 路径用 `wecom_login.py` 生成的 `storage_state` 文件，请勿提交版本库（`.gitignore` 已覆盖 `scripts/wecom_states/`）。

## 测试

```bash
python3 -m pytest scripts/test_wecom_doc_reader.py -v   # 离线单元测试
```

端到端测试方案（18 个用例 + 7 个已知坑验证，专为 AI coding agent 执行设计）：**`references/testing-plan.md`**。

## 版本

v5.2.0 · 更新于 2026-07-22

## 许可证

MIT © Jian Liu 2026
