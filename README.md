# 📄 WeCom Document Access — Enterprise WeChat Full-Format Document Reader

[中文](#中文说明)

Read **any document type** from Enterprise WeChat (企业微信 / WeCom) programmatically — smart tables, spreadsheets, micro-documents, mind maps, and more. Built as a reliable fallback when MCP authorization expires or hits row limits, and as the primary reader for document types that MCP doesn't support at all.

## The Problem It Solves

WeCom documents come in **10+ types**, each requiring a different access method. The built-in MCP integration only covers 2 types (smart tables and micro-docs) and has a 2,000-row hard limit. This skill provides:

1. **Full type coverage** — every document type has a verified read path
2. **No row limits** — bypass MCP's 2,000 row cap for smart tables
3. **No authorization dependency** — works even when MCP tokens expire
4. **Production-grade reliability** — every method is tested and verified, not theoretical

## Supported Document Types

| Type | URL Prefix | Read Method | Data Quality | Verified |
|------|-----------|-------------|-------------|----------|
| **Smart Table** (智能表格) | `s3_` | dop-api: full structured extraction (base64+zlib decoded) | ✅ Complete fields, options, user refs | ✅ |
| **Spreadsheet** (电子表格) | `e3_` | Native JS API: `getCellDataAtPosition()` memory read | ✅ Exact merged cells, image URLs, dates | ✅ |
| **Micro-Doc** (微文档) | `w3_` | opendoc API: full content extraction | ✅ Complete body text with formatting | ✅ |
| **Mind Map** (思维导图) | `m4_` | dop-api/get/mind: recursive JSON tree | ✅ Complete node hierarchy | ✅ |
| **Form** (收集表) | `/form/` | DOM text extraction | ⚠️ Basic text | ✅ |
| **Slide** (幻灯片) | `/slide/` | DOM text extraction | ⚠️ Basic text | ✅ |
| **Flowchart** (流程图) | `/flowchart/` | DOM text extraction | ⚠️ Basic text | ✅ |
| **Report** (汇报) | `/report/` | DOM text extraction | ⚠️ Untested | — |
| **Smart Doc** (智能文档) | `/smartdoc/` | DOM text extraction | ⚠️ Untested | — |

## What Data You Get Per Type

### Smart Tables (`s3_`) — Full Structured Data

| Data | Details |
|------|---------|
| All sheets | Automatic multi-sheet traversal via workbook metadata, no tab switching needed |
| All fields | Field name, type (text/number/select/date/user/image/URL…) |
| Select options | Option ID → display value mapping (single-select and multi-select) |
| User fields | User ID resolution to display names |
| Row data | **Unlimited rows** (bypasses MCP's 2,000 row limit) |
| Images | Image field URLs preserved |
| Decoding | base64 urlsafe + zlib decompress → JSON (not raw JSON string) |

**Technical depth**: Smart sheet cells are returned as base64-encoded zlib-compressed JSON (prefix `eJ`). The reader intercepts the page's initial `get/sheet` request to obtain dynamic `xsrf` and `rev` parameters, then fetches each sub-sheet with the complete parameter set (`xsrf`, `needSheetState=2`, `rev`, `optimizedVer=2`, `chunkCellSize=15000`, `enableChunkRank=1`, `enablePermOpt=0`). Missing any parameter returns retcode 538002.

### Spreadsheets (`e3_`) — Memory-Level Cell Access

| Data | Details |
|------|---------|
| Cell values | Direct memory read via `getCellDataAtPosition(row, col)` — **800 cells < 1ms** |
| Merged cells | Precise range detection via `getMergeReference()` + mergeList row-offset correction |
| Images | Original URLs via `getExtendedValue()` (e.g. `https://wdcdn.qpic.cn/...?w=4096`) |
| Dates | Automatic Excel serial number → ISO date conversion |
| Multiple sheets | Tab-by-tab reading with lazy-load handling (click + 5s wait) |

### Micro-Docs (`w3_`) — Full Content Extraction

| Data | Details |
|------|---------|
| Body text | Complete document content via opendoc API |
| Links | HYPERLINK markup cleaned to plain URLs |
| Canvas rendering | Adapted for WeCom's canvas-based document renderer |

### Mind Maps (`m4_`) — Complete Node Tree

| Data | Details |
|------|---------|
| Node hierarchy | Full recursive extraction of `children.attached` structure |
| Node content | Text, links, notes per node |
| Structure | Central topic → branches → sub-branches preserved |

## Included Scripts

| Script | Purpose |
|--------|---------|
| `scripts/wecom_doc_reader.py` | **Main reader** (v4.2.0) — auto-detects document type (s3_/e3_/w3_/m4_) and uses the appropriate method |
| `scripts/wecom_fetch.py` | Low-level fetch utilities for dop-api and opendoc endpoints |
| `scripts/wecom_login.py` | QR-code login script — generates QR image + saves browser storage_state for cookie-based auth |
| `scripts/check_cookie_expiry.py` | Checks cookie expiry time in storage_state files, alerts before expiration |
| `scripts/validate_extraction.py` | Data validation utility — checks for empty fields, type mismatches, structural issues |
| `scripts/wecom_doc_auth_check.py` | MCP authorization status checker — detects errcode 851014/851003 before reading |
| `scripts/wecom_reader.py` | Legacy reader (deprecated — use `wecom_doc_reader.py` instead) |
| `scripts/test_wecom_doc_reader.py` | **Test suite** — 19 offline tests covering URL parsing, field decoding, data extraction, error handling |
| `scripts/report_issue.py` | **GitHub issue auto-report** — automatically creates GitHub issues when critical errors occur (with dedup) |

### GitHub Issue Auto-Report

When the reader encounters critical errors (e.g. failed to intercept `get/sheet` request, base64+zlib decode failure), it automatically creates a GitHub issue with:

- Error type and stack trace
- Document URL (sanitized)
- Parameter set used
- Dedup check (won't create duplicate issues for the same error within 24h)

Configure via environment variable `GITHUB_TOKEN` (needs `repo:issues` scope). If not set, auto-report is silently skipped — the reader continues working without it.

### Test Suite

```bash
cd scripts/
python3 -m pytest test_wecom_doc_reader.py -v
# or standalone:
python3 test_wecom_doc_reader.py
```

19 tests covering: URL parsing (s3_/e3_/w3_/m4_), base64+zlib decoding, field type mapping, column definition parsing, row data extraction, error handling, edge cases.

## Reference Documentation

| File | Contents |
|------|----------|
| `references/dop-api-data-structure.md` | dop-api response structure for smart tables — field types, option mapping, pagination |
| `references/e3-native-js-api.md` | Spreadsheet native JS API (`SpreadsheetApp`) method reference |
| `references/e3-spreadsheet-fallback.md` | Spreadsheet reading strategy evolution: v2.x (broken) → v3.0 (clipboard) → v3.1 (native JS API) |
| `references/e3-merge-fill-verification.md` | Merged cell verification and row-offset correction methodology |
| `references/e3-vs-s3-dop-api.md` | Comparison: e3 spreadsheet dop-api vs s3 smart sheet dop-api differences |
| `references/m4-mind-extraction.md` | Mind map JSON node structure and recursive extraction algorithm |
| `references/w3-opendoc-extraction.md` | Micro-doc opendoc API content extraction method |
| `references/mcp-get-doc-content-multisheet-parsing.md` | MCP `get_doc_content` multi-sheet parsing pitfalls (column misalignment with `\|` characters) |
| `references/wecom-messaging.md` | WeCom messaging integration for notification workflows |

## Prerequisites

- Python 3.8+
- `playwright` (for browser-based reading paths)
- `requests` and `beautifulsoup4`
- Valid WeCom session cookies (obtain via `wecom_login.py` QR-code login)

## Setup

1. Copy `wecom-doc-access-methods/` into your agent's skills directory
2. Install dependencies: `pip install playwright requests beautifulsoup4`
3. Run `playwright install chromium` if using browser paths
4. Run QR-code login to obtain session cookies:
   ```bash
   python3 scripts/wecom_login.py --state /path/to/state.json --qr /tmp/qr.png --timeout 300
   ```
5. Scan the QR code with your WeCom app to authenticate

## When to Use This Skill

| Scenario | Why This Skill |
|----------|---------------|
| MCP token expired (errcode 851014) | Browser/dop-api paths don't need MCP |
| Need >2,000 rows from smart table | dop-api has no row limit |
| Complex spreadsheet with merged cells + images | Native JS API is the only reliable method |
| Mind map data extraction | dop-api/get/mind returns complete structure |
| Giving another agent WeCom read access | Self-contained scripts, easy to integrate |
| Micro-doc content extraction | opendoc API handles canvas rendering |

## Version History

| Version | Key Changes |
|---------|-------------|
| **v4.2.0** | Smart sheet: base64+zlib decoding, complete dop-api parameter set (xsrf/rev/etc.), multi-sheet via workbook metadata (no tab switching). Added test suite (19 tests), GitHub issue auto-report, auth check script, cookie expiry monitor |
| v4.1.1 | Added mind map (`m4_`) support, complete document type coverage table |
| v4.0.2 | Fixed merge-cell row-offset bug (mergeList sheet-level vs data-level offset) |
| v4.0.0 | Native JS API (`getCellDataAtPosition`) replaces clipboard HTML approach |
| v3.1.0 | Spreadsheet rewrite: direct memory read, image URLs, date conversion |
| v3.0.0 | JS Runtime + clipboard HTML for spreadsheets (14/15 sheets worked) |
| v2.x | dop-api JSON parsing (**deprecated** — actually returns protobuf, never worked) |

## Version

v4.2.0 · Updated 2026-06-29

## License

MIT © Jian Liu 2026

---

## 中文说明

# 📄 企微文档读取 — 企业微信全类型文档稳定读取方案

编程读取企业微信中的 **任意文档类型** — 智能表格、电子表格、微文档、思维导图等。当 MCP 授权过期或触发行数限制时作为可靠兜底方案，也是 MCP 不支持的文档类型的主力读取器。

## 解决的问题

企微文档有 **10+ 种类型**，每种需要不同的读取方式。内置 MCP 集成只覆盖 2 种类型（智能表格和微文档），且有 2000 条硬限制。本 Skill 提供：

1. **全类型覆盖** — 每种文档类型都有经过验证的读取路径
2. **无行数限制** — 突破 MCP 的 2000 条智能表格限制
3. **不依赖授权** — MCP Token 过期时仍然可用
4. **生产级可靠性** — 每种方法都经过实测验证，不是理论方案

## 支持的文档类型

| 类型 | URL 前缀 | 读取方式 | 数据质量 | 已验证 |
|------|---------|---------|---------|--------|
| **智能表格** | `s3_` | dop-api 全量结构化提取（base64+zlib 解码） | ✅ 完整字段、选项、用户引用 | ✅ |
| **电子表格** | `e3_` | 原生 JS API 内存直读 | ✅ 精确合并单元格、图片 URL、日期 | ✅ |
| **微文档** | `w3_` | opendoc API 正文提取 | ✅ 完整正文含格式 | ✅ |
| **思维导图** | `m4_` | dop-api/get/mind JSON 树 | ✅ 完整节点层级 | ✅ |
| **收集表** | `/form/` | DOM 文本提取 | ⚠️ 基础文本 | ✅ |
| **幻灯片** | `/slide/` | DOM 文本提取 | ⚠️ 基础文本 | ✅ |
| **流程图** | `/flowchart/` | DOM 文本提取 | ⚠️ 基础文本 | ✅ |
| **汇报** | `/report/` | DOM 文本提取 | ⚠️ 待测试 | — |
| **智能文档** | `/smartdoc/` | DOM 文本提取 | ⚠️ 待测试 | — |

## 各类型数据详情

### 智能表格（`s3_`）— 全量结构化数据

| 数据 | 说明 |
|------|------|
| 所有子表 | 通过 workbook 元数据自动遍历多子表，无需切换 tab |
| 所有字段 | 字段名、类型（文本/数字/单选/日期/成员/图片/链接…） |
| Select 选项 | 选项 ID → 显示值映射（单选和多选） |
| 成员字段 | 用户 ID 解析为显示名 |
| 行数据 | **无行数限制**（突破 MCP 的 2000 条上限） |
| 图片 | 图片字段 URL 保留 |
| 解码方式 | base64 urlsafe + zlib 解压 → JSON（非原始 JSON 字符串） |

**技术深度**：智能表格单元格返回的是 base64 编码的 zlib 压缩 JSON（前缀 `eJ`）。读取器拦截页面首次 `get/sheet` 请求获取动态 `xsrf` 和 `rev` 参数，然后用完整参数集（`xsrf`、`needSheetState=2`、`rev`、`optimizedVer=2`、`chunkCellSize=15000`、`enableChunkRank=1`、`enablePermOpt=0`）逐子表获取。缺少任何参数返回 retcode 538002。

### 电子表格（`e3_`）— 内存级单元格访问

| 数据 | 说明 |
|------|------|
| 单元格值 | 通过 `getCellDataAtPosition(row, col)` 直接内存读取 — **800 cells < 1ms** |
| 合并单元格 | 通过 `getMergeReference()` + mergeList 行号偏移修正精确检测 |
| 图片 | 通过 `getExtendedValue()` 获取原始 URL（如 `https://wdcdn.qpic.cn/...?w=4096`） |
| 日期 | Excel 序列号 → ISO 日期自动转换 |
| 多子表 | 逐 tab 读取，处理懒加载（点击 + 等待 5 秒） |

### 微文档（`w3_`）— 完整内容提取

| 数据 | 说明 |
|------|------|
| 正文 | 通过 opendoc API 获取完整文档内容 |
| 链接 | HYPERLINK 标记清理为纯 URL |
| Canvas 渲染 | 适配企微 Canvas 文档渲染器 |

### 思维导图（`m4_`）— 完整节点树

| 数据 | 说明 |
|------|------|
| 节点层级 | 完整递归提取 `children.attached` 结构 |
| 节点内容 | 每个节点的文本、链接、备注 |
| 结构 | 中心主题 → 分支 → 子分支完整保留 |

## 附带脚本

| 脚本 | 用途 |
|------|------|
| `scripts/wecom_doc_reader.py` | **主读取器**（v4.2.0）— 自动检测文档类型（s3_/e3_/w3_/m4_）并使用对应方法 |
| `scripts/wecom_fetch.py` | dop-api 和 opendoc 底层 fetch 工具 |
| `scripts/wecom_login.py` | 扫码登录脚本 — 生成 QR 码图片 + 保存浏览器 storage_state 用于 cookie 认证 |
| `scripts/check_cookie_expiry.py` | 检查 storage_state 文件中的 cookie 过期时间，到期前告警 |
| `scripts/validate_extraction.py` | 数据校验工具 — 检查空字段、类型不匹配、结构异常 |
| `scripts/wecom_doc_auth_check.py` | MCP 授权状态检查 — 读取前检测 errcode 851014/851003 |
| `scripts/wecom_reader.py` | 旧版读取器（已废弃，请用 `wecom_doc_reader.py`） |
| `scripts/test_wecom_doc_reader.py` | **测试套件** — 19 个离线测试，覆盖 URL 解析、字段解码、数据提取、错误处理 |
| `scripts/report_issue.py` | **GitHub issue 自动反馈** — 遇到关键错误时自动创建 GitHub issue（带去重） |

### GitHub Issue 自动反馈

当读取器遇到关键错误（如未拦截到 `get/sheet` 请求、base64+zlib 解码失败）时，会自动创建 GitHub issue，包含：

- 错误类型和堆栈信息
- 文档 URL（已脱敏）
- 使用的参数集
- 去重检查（同一错误 24 小时内不重复创建）

通过环境变量 `GITHUB_TOKEN` 配置（需要 `repo:issues` 权限）。未设置时自动跳过，不影响读取器正常工作。

### 测试套件

```bash
cd scripts/
python3 -m pytest test_wecom_doc_reader.py -v
# 或独立运行：
python3 test_wecom_doc_reader.py
```

19 个测试覆盖：URL 解析（s3_/e3_/w3_/m4_）、base64+zlib 解码、字段类型映射、列定义解析、行数据提取、错误处理、边界情况。

## 参考文档

| 文件 | 内容 |
|------|------|
| `references/dop-api-data-structure.md` | 智能表格 dop-api 响应结构 — 字段类型、选项映射、分页 |
| `references/e3-native-js-api.md` | 电子表格原生 JS API（`SpreadsheetApp`）方法参考 |
| `references/e3-spreadsheet-fallback.md` | 电子表格读取策略演进：v2.x（不可用）→ v3.0（剪贴板）→ v3.1（原生 JS API） |
| `references/e3-merge-fill-verification.md` | 合并单元格验证和行号偏移修正方法 |
| `references/e3-vs-s3-dop-api.md` | 对比：e3 电子表格 dop-api vs s3 智能表格 dop-api 差异 |
| `references/m4-mind-extraction.md` | 思维导图 JSON 节点结构和递归提取算法 |
| `references/w3-opendoc-extraction.md` | 微文档 opendoc API 内容提取方法 |
| `references/mcp-get-doc-content-multisheet-parsing.md` | MCP `get_doc_content` 多子表解析陷阱（含 `\|` 字符导致列错位） |
| `references/wecom-messaging.md` | 企微消息集成（通知工作流） |

## 环境要求

- Python 3.8+
- `playwright`（浏览器读取路径需要）
- `requests`、`beautifulsoup4`
- 有效的企微会话 Cookie（通过 `wecom_login.py` 扫码登录获取）

## 安装

1. 将 `wecom-doc-access-methods/` 目录复制到你的 Agent skills 目录
2. 安装依赖：`pip install playwright requests beautifulsoup4`
3. 运行 `playwright install chromium`（如果使用浏览器路径）
4. 运行扫码登录获取会话 Cookie：
   ```bash
   python3 scripts/wecom_login.py --state /path/to/state.json --qr /tmp/qr.png --timeout 300
   ```
5. 用企业微信扫描 QR 码完成认证

## 何时使用本 Skill

| 场景 | 为什么选本 Skill |
|------|----------------|
| MCP Token 过期（errcode 851014） | 浏览器/dop-api 路径不需要 MCP |
| 智能表格需要 >2000 行 | dop-api 无行数限制 |
| 复杂电子表格含合并单元格+图片 | 原生 JS API 是唯一可靠方法 |
| 思维导图数据提取 | dop-api/get/mind 返回完整结构 |
| 给其他 Agent 集成企微读取 | 自包含脚本，易于集成 |
| 微文档内容提取 | opendoc API 处理 Canvas 渲染 |

## 版本历史

| 版本 | 关键变更 |
|------|---------|
| **v4.2.0** | 智能表格：base64+zlib 解码、完整 dop-api 参数集（xsrf/rev 等）、通过 workbook 元数据遍历多子表（无需切 tab）。新增测试套件（19 项）、GitHub issue 自动反馈、授权检查脚本、Cookie 过期监控 |
| v4.1.1 | 新增思维导图（`m4_`）支持，文档类型全覆盖 |
| v4.0.2 | 修复合并单元格行号偏移 bug |
| v4.0.0 | 原生 JS API（`getCellDataAtPosition`）替代剪贴板 HTML |
| v3.1.0 | 电子表格重构：内存直读、图片 URL、日期转换 |
| v3.0.0 | JS Runtime + 剪贴板 HTML（14/15 子表成功） |
| v2.x | dop-api JSON 解析（**已废弃** — 实际返回 protobuf，从未跑通） |

## 版本

v4.2.0 · 更新于 2026-06-29

## 许可证

MIT © Jian Liu 2026
