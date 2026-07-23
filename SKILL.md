---
name: wecom-doc-access-methods
version: 5.3.0
description: >
  读取：s3_ 智能表格(dop-api全量)、e3_ 电子表格(原生JS API)、w3_ 微文档(opendoc API完整正文)、m4_ 思维导图(dop-api/get/mind)。
  编辑：w3_ 微文档(MCP edit_doc_content全量覆写 + 浏览器键盘增删改)、e3_ 电子表格(MCP sheet_* + 浏览器 mutation API 写入)、s3_ 智能表格(MCP smartsheet_* 17种字段类型)。
  图片上传：直调MCP JSON-RPC(无8KB限制，99.3%质量保持)。
  浏览器UI创建：8种类型(智能文档/智能表格/文档/表格/幻灯片/收集表/思维导图/流程图)。
  不可编辑：p3_幻灯片/f4_流程图(方法待探索,非不可行)。m4_思维导图键盘编辑已验证(Tab添加子节点+键盘输入修改文本+自动保存)。SmartPage编辑已验证(submit_command API + EtherPad changeset, 跨session持久化)。SmartPage删除已验证(浏览器键盘清空+Backspace)。
---
---

# 企微文档稳定读取 — 通用 Skill

> 参考文件：[851003-diagnostic](references/851003-diagnostic.md)（851003 权限错误诊断）、[identity-resolution-pitfalls](references/identity-resolution-pitfalls.md)（身份识别故障排查）、[e3-reader-output-pitfalls](references/e3-reader-output-pitfalls.md)（e3 读取：PYTHONPATH / JSON 前缀 / 表头 / 空行 / tab 定位）、[e3-browser-write-research](references/e3-browser-write-research.md)（e3 浏览器写入 API：mutation 模型闭环 — applyMutation + commitMutation + WS USER_CHANGES 持久化验证）

## Skill 定位与架构（2026-07-16 团队负责人要求）

本 skill 是**企微文档操作的底层引擎** — 提供读写企微文档的通用能力（dop-api 读取、MCP 编辑、浏览器编辑、登录、授权检查）。

其他 skill（同步管道、质量检查等）应**引用**本 skill 的 CLI/Python API，不自己实现文档操作逻辑：

```bash
# 其他 skill 调用方式（需 PYTHONPATH，否则 No module named wecom_doc_reader）
PYTHONPATH=./scripts python3 -m wecom_doc_reader read <user_id> <doc_url>
```

```python
# Python API
from wecom_doc_reader import WeComDocReader
reader = WeComDocReader()
result = reader.read(user_id, url)
```

**已禁用的重复 skill**：
- `openclaw-imports/wecom-doc` — OpenClaw 侧的企微文档 skill，已重命名 `.disabled` + DEPRECATED 标记（2026-07-16）
- OpenClaw agent侧已安装本 skill 替代

---

## 适用场景

- 需要读取企微智能表格（`s3_`）或微文档（`w3_`）的数据
- **优先使用浏览器 dop-api 方案**（结构化 JSON，无列错位，全量数据）— 2026-06-29 团队负责人要求
- MCP `get_doc_content` 仅用于快速浏览/简单场景（返回 Markdown，多子表时有 `|` 列错位风险）
- MCP 授权过期（errcode 851014 / 2200063）时浏览器方案是唯一可用路径
- 需要突破 MCP 2000 条硬限制获取全量数据
- 需要给其他 Agent 系统集成企微文档读取能力

## 企微文档完整类型列表

| 类型 | API doc_type | URL 前缀 | MCP 支持 | 浏览器读取方式 | 数据质量 |
|------|-------------|---------|---------|-------------|---------|
| 微文档 | DOC (3) | `w3_` → `/doc/w3_xxx` | ⚠️ | **opendoc API**（canvas 渲染，DOM 无效） | ✅ opendoc API 完整正文提取（v5.0 实现） |
| 电子表格 | SHEET (4) | `e3_` → `/sheet/e3_xxx` | ❌ | **SpreadsheetApp 原生 JS API**（v3.1 实测）。`getCellDataAtPosition` 直接读值+合并范围+图片URL | ✅ 内存直读，合并精确，图片原始URL |
| 智能表格 | SMARTSHEET (10) | `s3_` → `/smartsheet/s3_xxx` | ✅(2000条限制) | dop-api 全量结构化 | ✅ 完整字段+选项 |
| 思维导图 | MIND | `m4_` → `/mind/m4_xxx` | ❌ | **dop-api/get/mind**（JSON 节点树） | ✅ 完整节点 |
| 收集表 | FORM | `/form/...` | ❌ | DOM 文本提取 | ✅ |
| 幻灯片 | SLIDE | `/slide/...` | ❌ | DOM 文本提取 | ✅ |
| 流程图 | FLOWCHART | `/flowchart/...` | ❌ | DOM 文本提取 | ✅ |
| 汇报 | REPORT | `/report/...` | ❌ | DOM 文本提取 | ⏸️ 待测试 |
| 智能文档 | SMARTDOC | `/smartdoc/...` | ❌ | DOM 文本提取 | ⏸️ 待测试 |

**⚠️ API 创建限制**：官方 API（`create_doc`）仅支持创建 3 种类型：`doc_type=3`（微文档）、`4`（电子表格）、`10`（智能表格）。其他类型（幻灯片、汇报、智能文档等）只能通过企微 UI 创建。

### e3_ 电子表格 wecom_doc_reader 输出格式（2026-07-16 实测）

`wecom_doc_reader` 读取 e3_ 表格后返回的 JSON 结构与 s3_ 智能表格**不同**，消费者需注意：

```
{
  "success": true,
  "doc_type": "sheet",
  "sheets": {                          # ⚠️ dict（按 sheet 名索引），不是 list
    "工作排期": {
      "sheetId": "BB08J2",
      "headers": ["P系列文档排期", "col_1"],  # col_1 是自动生成的列名（无名列）
      "rows": [                         # ⚠️ 是 rows，不是 records
        {"_row": 1, "P系列文档排期": "阶段1:\n主流程相关文档优化", "col_1": "自主作业\n测地", "_sheet_name": "工作排期"},
        ...
      ],
      "row_count": 4,
      "mergeList": [...],
      "mergeCount": 0,
      "method": "native-js-api",
      "usedRange": "...",
      "readRange": "..."
    },
    "知识库目录结构": { ... }
  },
  "sheet_names": ["工作排期", "知识库目录结构"],  # 顺序列表
  "sheet_count": 2,
  "total": 203,
  "records": [...],                     # ⚠️ 兼容字段：所有 sheet 的 rows 合并（带 _sheet_name）
  "failed_sheets": [],
  "title": "P系列清单",
  "method": "native-js-api"
}
```

**关键差异（e3_ vs s3_）**：

| 字段 | e3_ 电子表格 | s3_ 智能表格 |
|---|---|---|
| `sheets` | dict，key=sheet 名，value={rows, headers, ...} | dict，同结构 |
| 行数据字段 | `rows` 数组，每行用 header 名做 key | `records` 数组（兼容字段），同结构 |
| 列名 | `headers` 数组，无名列为 `col_1`/`col_2`... | `field_names`（从 dop-api 列定义提取） |
| 单元格值 | 直接字符串/数字，含 `\n` 换行 | 按 k30 字段类型提取，select 需选项映射 |
| 合并单元格 | `mergeList` + `mergeCount` | 同 |

**消费 e3_ 数据的正确方式**：
```python
sheets = data["sheets"]  # dict
for sheet_name, sheet_data in sheets.items():
    headers = sheet_data["headers"]  # 列名列表
    rows = sheet_data["rows"]        # 行数据列表
    for row in rows:
        val = row.get(headers[0], "")  # 用 header 名取值
```

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

## 🔒 身份隔离（2026-07-16）
操作前必须调封装脚本：企微 `python3 ~/.config/wecom-doc/scripts/wecom_auth_flow.py --check <wecom_userid>`，飞书 `python3 ~/.config/wecom-doc/scripts/lark_auth_flow.py --check <wecom_userid>`。脚本内部处理检查/二维码/授权/轮询全流程。定时任务用创建人 cookie（`WECOM_USERID` 环境变量）。
- `wecom_doc_check_auth.sh` / `lark_check_auth.sh` 已标记 DEPRECATED，功能合并到 auth_flow 脚本
- 全局 cookie 文件（`_shared.json` / `wecom_browser_state.json` / `wecom_cookies.json`）改为软链接指向团队负责人 per-user 文件
- `wecom_auth_flow.py` QR 图片保存到 `~/.config/wecom-doc/workspace/`（企微 MEDIA 白名单目录，可直接发）
- **定时同步脚本必须设 `LARKSUITE_CLI_CONFIG_DIR`**
- **⚠️ 非 Hermes 环境注意**：上述 `wecom_auth_flow.py` / `lark_auth_flow.py` 是 Hermes 专用封装脚本（依赖 gateway 会话上下文）。其他 AI 工具（Codex / Trea / GPT Cowork）直接用 MCP apikey 环境变量（`WECOM_MCP_APIKEY`）或 WeCom OAuth Device Flow 自行实现身份验证即可，不需要这些脚本。：所有用 `lark-cli --as user` 的 crontab 脚本，开头根据 `WECOM_USERID` 构造 `LARKSUITE_CLI_CONFIG_DIR` 指向 per-user 目录。crontab 显式设 `WECOM_USERID=创建人`。详见 `lark-multi-user-auth` skill 的「定时同步脚本必须设置 LARKSUITE_CLI_CONFIG_DIR」章节。

## 方案速查

| 方案 | 推荐度 | 数据完整性 | 稳定性 | 写能力 | 维护成本 |
|------|--------|-----------|--------|--------|----------|
| **Playwright + dop-api** | **✅ 首选** | ✅ 全量 | ⚠️ 中（cookie ~2周） | ⚠️ e3_可写(mutation API) | 中（定期扫码续期） |
| **MCP API** | ⚠️ fallback | ⚠️ 前2000条 | ✅ 高 | ✅ | 低（授权过期重分享） |

**推荐策略**：**优先用浏览器 dop-api 方案**（结构化 JSON，无列错位风险，全量数据）。MCP `get_doc_content` 返回 Markdown 纯文本，多子表拼接时单元格内 `|` 字符导致列错位（2026-06-29 实测 24 子表技术工单表，31-39 列旧格式子表大量错位），仅作为快速浏览/简单场景的 fallback。需要写操作时用 MCP（浏览器方案只读）。

---

---

## 详细方案与参考(已拆分至 references/)

> 2026-07-21:原 SKILL.md 152KB 超 skill_manage 100KB 上限,详细内容拆分至以下 references 文件。按需用 `skill_view(name="wecom-doc-access-methods", file_path="references/xxx.md")` 加载。

| 文件 | 内容 | 何时加载 |
|---|---|---|
| `references/playwright-dop-api-guide.md` | **方案一(首选)**:Playwright + dop-api 全量读取详细步骤(扫码登录/cookie 检查/全量获取/解析/select 映射/多子表/w3_/m4_ 读取) | 要读企微文档全量数据时 |
| `references/mcp-api-guide.md` | **方案二(fallback)**:MCP API 能力范围/调用方式/限制/授权流程 | 快速浏览或需要写操作时 |
| `references/pitfalls.md` | **Pitfalls 全集**(60+ 条实战踩坑):解码/opendoc/startrow/cookie/三种认证/QR 图片/cron 环境/编辑能力矩阵/SmartPage/权限隔离等 | 遇到报错或做写操作前必查 |
| `references/retry-mechanism.md` | 自动重试机制 v4.5.0+(两层重试架构/不可重试错误/环境变量) | 调用 wecom_doc_reader 脚本时 |
| `references/testing-and-issue-feedback.md` | 测试方案(单元/集成)+ GitHub Issue 自动反馈机制 | 改脚本后验证、配置反馈 |
| `references/cookie-watchdog.md` | Cookie 与授权状态定时检查(部署方式/配置/续期) | 部署定时检查任务时 |
| `references/changelog.md` | 完整更新日志 | 追溯版本历史时 |
| `references/testing-plan.md` | **🆕 E2E 测试方案 v5.2.0**（T1-T18 用例 + 7 个已知坑验证，面向所有主流 AI coding agent。含标准化结果 JSON + GitHub Issues 提交机制） | 验证 skill 安装与读写能力时 |
| `references/e3-browser-write-research.md` | **✅ e3 浏览器写入 API（已闭环）**（mutation 模型：applyMutation + await commitMutation，WS USER_CHANGES 同步，重载持久化验证通过。含完整流程 + pitfall） | 实现 e3 浏览器写入时 |

### 最高频 Pitfalls 速记(细节见 references/pitfalls.md)

- 🚨 **不要混淆三种认证机制**:企微扫码 cookie / 飞书 OAuth / MCP 应用 token,三者独立
- 🚨 **MCP 失败后必须 fallback 到浏览器方案**,反之亦然,不要死磕单一路径
- 🚨 **MCP 操作也受身份隔离约束**:只操作当前对话人有权访问的文档
- 🚨 **QR 图片必须在 workspace 目录 + 转 RGB**,否则企微 MEDIA 白名单静默拦截
- 🚨 **per-user cookie 隔离**:定时任务用创建人的 cookie,不用 `_shared.json`
- 🚨 **e3_ 原生 JS API 是最佳方案**;dop-api 返回 protobuf 二进制需特殊解析
- 🚨 **edit_doc_content 只能编辑机器人创建的文档**,成员创建的报 851003
- 🚨 **SmartPage 嵌入图片必须用英文括号 `()`**,中文括号 `（）`不渲染;完整四步法见 references/wecom-doc-image-embedding.md 第四节
- 🚨 **未实测的代码不准写进方案**(血泪教训)
- 🚨 **公开前必须扫描 .py 脚本里的硬编码凭据**（`apikey=`/`secret=`/`token=`），不只是 .md 文档——2026-07-22 实测 `wecom_doc_auth_check.py:36` 的 MCP apikey 漏过 07-17 脱敏审查、在公开 GitHub 仓库暴露。修复：改读 `WECOM_MCP_APIKEY` 环境变量 + 轮换 key + 清 git 历史。详见 skill-building-standard §17.6 + `references/crud-coverage-gap.md` P0
- 🚨 **MCP list 类接口成功 ≠ apikey 有效**：`tools/list`/`list_prompts` 可能返回连接初始化时的缓存，apikey 已失效也显示"成功"。配 key 后**必须立刻用真实 tools/call 验证**（如对假 URL 调 `get_doc_content`）：errcode 850001 = key 错；851003/851014 = 鉴权通过、文档权限问题。2026-07-22 被缓存假象误导过一次
- 🚨 **gateway MCP 工具用启动时缓存的凭据**：改了 config.yaml 的 MCP apikey 后，gateway 的 `mcp________*` 工具仍用启动时加载的旧 key（报 850001），而脚本直调（wecom_doc_writer.py 的 `mcp_call`）运行时读 config.yaml 立即生效。改 key 后要么重启 gateway，要么用直调脚本验证/操作——别被 gateway 工具的陈旧凭据缓存误导（2026-07-22 实测：gateway create_doc 报 850001，writer 直调同 key 成功）
- 🚨 **e3 浏览器写入 mutation 只改属性不替换对象**：`mutationApi.applyMutation` + `commitService.commitMutation` 是 e3_ 浏览器写入的正确路径（OT/Mutation 模型）。mutation 的 `cell` 和 `gridRangeData` 是类实例（有 `isInvalid()`/`getAuthor()` 方法），**只能改标量属性（`.value`/`.startRowIndex` 等），不能替换整个对象为 plain JSON**——替换会丢实例方法导致 `isInvalid is not a function`。commitMutation 返回 **Promise**（不是 generator），必须 `await`。详见 `references/e3-browser-write-research.md`
- 🚨 **凭据录入后立即逐字符核对**：用户粘贴的长 key 手工转录极易丢字符（2026-07-22 86 位 key 录成 85 位报 850001）。验证失败时先从 state.db `messages.content`（role=user）恢复原文 difflib 比对，不要凭记忆重敲、也不要先怀疑用户的 key 错了
- 🚨 **GitHub push 必须从技能目录推，不能从 GitLab clone 推**：`publish_skill.sh` 的 GitHub push 是从 `$LOCAL_SKILL`（技能目录自己的 git repo，origin=GitHub）推的。从包含所有 skill 的本地 GitLab clone 推到 GitHub 会覆盖为 172+ 文件 + 内部信息泄露。实测踩坑——force push 从错误 repo 把其他 skill 的文件 + 内部团队信息字样推到了公开 GitHub
- 🚨 **GIT_HTTP_VERSION=HTTP/1.1 解决 GitHub "Empty reply from server"**：push 到 GitHub 间歇性报 `fatal: Empty reply from server`（网络抖动）。设 `GIT_HTTP_VERSION=HTTP/1.1` 环境变量可解决。`publish_skill.sh` 和手动 push 都适用
- 🚨 **脱敏扫描必须包含团队人名和公司名**：publish_skill.sh 的 pattern 不能只有 IP/userid/apikey——还必须包含：团队成员人名、内部域名、内部产品名。否则团队特征信息泄露到公开 GitHub。实测 changelog.md/pitfalls.md 含人名、testing-plan.md 含内部域名，均已清理
- 🚨 **README 面向用户安装使用，不面向开发者内部**：用户要求 README 完整、通俗、准确——覆盖安装步骤、凭据配置、每类型读写示例（copy-paste）、故障排查表。不写内部实现细节、不提团队名

---

## 故障处理速查

| 错误码 | 含义 | 解决方案 |
|--------|------|----------|
| 850001 | MCP apikey 无效 | key 本身错误——核对录入是否丢/多字符（与原始消息逐字符 diff，见下）、或后台又轮换过；从机器人后台重新复制完整 StreamableHTTP URL |
| 851014 | MCP 授权过期 | 重新分享文档给机器人，或切浏览器方案 |
| 2200063 | MCP 授权过期（另一种） | 同上 |
| 851000 | 文档格式不支持（e3_） | 用浏览器方案 |
| 851003 | 文档类型不支持（blankpage） | 用浏览器方案 |
| cookie 过期 | 页面跳转到 login | 重新扫码登录 |
| base64 解码失败 | invalid characters | 换 urlsafe_b64decode + 加 padding |
| retcode 538002 | dop-api "Get content error" | 主动 fetch 缺少必要参数（xsrf/rev/needSheetState等），需拦截页面首次请求获取完整参数集 |

---


## 支持文件

- `references/e3-native-js-api.md` — **🆕 e3_ 原生 JS API 完整参考**（getCellDataAtPosition 用法、cell 方法列表、图片URL、合并范围、日期转换）
- `references/e3-merge-fill-verification.md` — **🆕 合并填充验证方法论**（三层递进：表面指标→spot-check→ground-truth；mergeList 偏移根因分析）
- `references/dop-api-data-structure.md` — dop-api 完整数据结构参考（字段类型 ID、行列路径、用户映射、**e3_ protobuf 实测结论**）
- `references/e3-spreadsheet-fallback.md` — **e3_ 电子表格读取方案 v3.0**（JS Runtime + clipboard HTML，protobuf 实测）
- `references/e3-vs-s3-dop-api.md` — 🆕 e3_ vs s3_ dop-api 数据结构差异（已废弃，v3.0 统一用 JS Runtime）
- `references/w3-opendoc-extraction.md` — **w3_ 微文档 opendoc API 提取**（canvas 渲染、自定义格式解析、%uXXXX 解码）
- `references/w3-opendoc-extraction.md` — **w3_ 微文档 opendoc API 提取**（canvas 渲染、自定义格式解析、%uXXXX 解码）
- `references/m4-mind-extraction.md` — **m4_ 思维导图读取**（JSON 节点树递归提取）
- `references/m4-engine-api-extraction.md` — **🆕 m4_ 思维导图 engine API 提取与编辑探索**（React fiber 提取路径、171 方法清单、engineConfig、textContainerEl caret 分析、fileData 结构、键盘编辑验证、p3_/f4_ 方向）
- `references/smartpage-editing-exploration.md` — SmartPage 编辑深度探索（v2-v9 全记录：lastCanWrite 强制激活 / dataDispatcher 签名 / createEditor prototype / DI 上下文搜索 / 根因分析）
- `references/smartpage-delete-block.md` — **🆕 SmartPage 删除 block 完整记录**（浏览器键盘验证 + 拦截完整请求体格式 + API 直接删除调试笔记 + 变量获取路径表）
- `references/wecom-messaging.md` — **WeCom 消息媒体发送指南**
- `references/wecom-media-delivery-debug.md` — **企微图片交付排错指南**
- `references/mcp-get-doc-content-multisheet-parsing.md` — **🆕 MCP get_doc_content 多子表 Markdown 解析**（不同子表列数不同、`|`字符列错位、排序破坏边界、重复子表检测、列名模糊匹配、解析脚本模板）
- `references/wecom-doc-image-embedding.md` — **🆕 企微文档图片嵌入与上传**（w3 vs SmartPage 图片支持差异、upload_image.py 直调 API vs Hermes MCP 限制、CDN 二次压缩、晨报高清原理、SmartPage 带图四步法）
- `references/crud-coverage-gap.md` — **🆕 CRUD 覆盖矩阵与差距分析**（各文档类型 × 增删改查 × MCP/浏览器 现状表 + 4 个已识别差距 + 推荐执行顺序；定期复审）
- `scripts/wecom_login.py`
- `scripts/check_cookie_expiry.py` — **🆕 cookie 过期检查**（检查 wedoc_sid/wedoc_ticket 剩余天数，距过期 ≤4 天输出警告，供 cron 主动提醒）
- `scripts/wecom_fetch.py` — 底层 dop-api 调试工具（7 个函数，直接 HTTP 请求 dop-api）
- `scripts/validate_extraction.py` — **🆕 提取结果 ground-truth 验证**（导出子表前 N 行为 CSV，对照原始文档逐列检查）
- `scripts/wecom_doc_auth_check.py` — **🆕 授权状态定时检测**（cookie 提前 4 天预警 + MCP 851014 告警 + 授权历史追踪，Hermes cron 每 6 小时跑，有异常才输出）
- `scripts/upload_image.py` — **🆕 图片/文件上传工具（直调 MCP JSON-RPC）**（绕过 Hermes 客户端 8KB 限制，无大小限制，99.3% 质量保持，120s 超时。用法：`python3 upload_image.py <image_path> <docid>` 或 `--file` 上传文件）
- `scripts/wecom_doc_writer.py` — **🆕 统一写入口 v5.2.0**（s3_ 记录 CRUD / e3_ 范围写+追加 / w3_ 创建+编辑 / SmartPage 创建+带图四步法 / 图片文件上传。纯 requests 直调 MCP JSON-RPC，无 MCP 框架依赖，任意 AI 工具可用。简单数据结构自动包装：2D 数组→CellData、标量→字段值格式；SmartPage 图片用 `![alt](local:/path)` 占位符自动上传替换 CDN URL。`--help` 查全部子命令）

---

