# 原 SKILL.md 中被分层改造遗漏的章节（2026-08-28 恢复）

> 2026-08-27 分层改造时，这些章节未被外移也未保留在精简卡中，属信息丢失。
> 本文件从改造前备份 `SKILL.md.bak-layered-20260827T215658` 完整恢复。

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

## 🔒 身份隔离（2026-07-16）

**双通道架构（2026-08-18 新增）**：企微文档读写走两个通道，**MCP 优先 + 浏览器 per-user 兜底**。

| 通道 | 凭据 | 隔离方式 | 适用场景 |
|------|------|----------|----------|
| **MCP** (`~/.hermes/scripts/wecom_doc_write.py` / `wecom_doc_read.py` 的 MCP 部分） | 应用级 apikey（robot-doc 机器人） | 机器人身份，**不代表任何用户** | w3_ 读、w3_/s3_/e3_ 写、SmartPage 创建（仅机器人创建的文档） |
| **浏览器** (`wecom_doc_read.py` / `wecom_doc_write.py` 的浏览器部分） | per-user cookie（`~/.hermes/identity/wecom/{principal_id}.json`） | 当前对话人身份 | 成员文档读写、SmartPage 图片上传（`doc_img_upload`）、s3_ 全量读 |

**铁规**：
1. 读：先 MCP `get_doc_content`（仅 w3_），失败/不支持 → 浏览器 `wecom_doc_read.py`
2. 写：先 MCP `wecom_doc_write.py`（w3_/s3_/e3_/SmartPage 创建），遇 851003（成员文档）/850005（MCP 限制） → 浏览器 `doc_img_upload` / SmartPage 同步流程
3. **MCP 通道永远不会"冒用用户身份"**——它写出的文档创建者就是机器人，天然中立。per-user 隔离只针对浏览器 cookie 通道
4. 浏览器通道必须走 `wecom_auth_flow.py --check` 验证当前对话人已授权，禁止借用他人 cookie

**权限模型（重要）**：企微文档权限分三层——**群聊可见 ≠ 文档可读 ≠ 文档可编辑**。群里能创建文档不代表机器人能读取它（会报 851014）。机器人需要被**明确分享**目标文档才有权限。遇到 851003/851014 时先确认机器人是否被分享该文档。详细错误对照见 `references/error-mapping.md`。

**状态自检**：`python3 scripts/wecom_status.py --user <userid>` 一键检查 cookie 有效性 + MCP key 有效性，输出结构化状态报告和修复建议。
操作前必须调封装脚本：企微 `python3 ~/.hermes/scripts/wecom_auth_flow.py --check <wecom_userid>`，飞书 `python3 ~/.hermes/scripts/lark_auth_flow.py --check <wecom_userid>`。脚本内部处理检查/二维码/授权/轮询全流程。定时任务用创建人 cookie（`WECOM_USERID` 环境变量）。`~/.hermes/scripts/` 下两个脚本自 2026-08-17 起为软链，真源在 `~/.hermes/plugins/identity-guard/`（逻辑单点维护，不再手工同步副本）。
- **扫码自动闭环（v5.4.0 新增，v5.5.0 起强制）**：`wecom_auth_flow.py --wait-done` 模式让 Agent 自动管理扫码全流程，**不需要用户说"扫完了"**。流程：①Agent 调 `--check` 检查凭证 → ②`auth_required` 时调 `--wait-done` → ③脚本启动 worker、生成 QR、返回 `scan` payload（含 `reply_media` + `poll_command`）→ ④Agent 把二维码发给用户并告知"请扫码，我会自动等待" → ⑤Agent 用返回的 `poll_command` 轮询 `--status` 直到 `completed` 或 `timeout` → ⑥完成或超时后向用户报告结果。`wecom_login.py` 的 `--status-file` 输出 JSON 状态文件（qr_ready→scanned→success/timeout/error），脚本内部自动轮询 `wedoc_sid` cookie 写入。
- **⚠️ 企微 `--wait` 已废弃（v5.5.0 起硬报错）**：`--wait` 只返回 QR 就退出、把轮询责任丢给 Agent，历史上每个 Agent（各 Agent 实例）都因此漏轮询；改用 `--wait-done`。**飞书 `lark_auth_flow.py` 不在此列** —— 它尚未提供 `--wait-done`，`--wait` 仍是唯一可用模式。
- 全局 cookie 文件（`_shared.json` / `wecom_browser_state.json` / `wecom_cookies.json`）改为软链接指向团队负责人 per-user 文件
- `wecom_auth_flow.py` QR 图片保存到 `~/.hermes/workspace/`（企微 MEDIA 白名单目录，可直接发）
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

## 故障处理速查

| 错误码 | 含义 | 解决方案 |
|--------|------|----------|
| 850001 | MCP apikey 无效 | **先区分报错来源**：若 gateway `mcp________*` 工具报 850001 但脚本直调（wecom_doc_writer.py）正常 → gateway 启动时缓存了旧 key，用 writer 直调或重启 gateway（见上方 pitfalls 速记）；否则 key 本身错误——核对录入是否丢/多字符（与原始消息逐字符 diff，见下）、或后台又轮换过；从机器人后台重新复制完整 StreamableHTTP URL |
| 851014 | MCP 授权过期 | 重新分享文档给机器人，或切浏览器方案 |
| 2200063 | MCP 授权过期（另一种） | 同上 |
| 851000 | 文档格式不支持（e3_） | 用浏览器方案 |
| 851003 | 文档类型不支持（blankpage） | 用浏览器方案 |
| cookie 过期 | 页面跳转到 login | 重新扫码登录 |
| base64 解码失败 | invalid characters | 换 urlsafe_b64decode + 加 padding |
| retcode 538002 | dop-api "Get content error" | 主动 fetch 缺少必要参数（xsrf/rev/needSheetState等），需拦截页面首次请求获取完整参数集 |

---

## 反馈与贡献

使用本 skill 过程中遇到任何问题或有功能建议，欢迎到 GitHub 提 issue：
https://github.com/Againliu/wecom-doc-access-methods/issues

提 issue 时请包含：
- 你使用的 AI 工具（Hermes / Cursor / Claude Code 等）
- 操作场景（读/写什么类型的文档）
- 完整错误信息

---



<!-- --wait 废弃口径已补完(2026-08-18):企微硬报错改用 --wait-done,飞书仍用 --wait。改动同时覆盖 SKILL.md 与 references/pitfalls.md。 -->

## 原 SKILL.md 顶部的参考文件索引行（2026-08-28 补录，此前遗漏）

> 参考文件：[851003-diagnostic](references/851003-diagnostic.md)（851003 权限错误诊断）、[identity-resolution-pitfalls](references/identity-resolution-pitfalls.md)（身份识别故障排查）、[e3-reader-output-pitfalls](references/e3-reader-output-pitfalls.md)（e3 读取：PYTHONPATH / JSON 前缀 / 表头 / 空行 / tab 定位）、[e3-browser-write-research](references/e3-browser-write-research.md)（e3 浏览器写入 API：mutation 模型闭环 — applyMutation + commitMutation + WS USER_CHANGES 持久化验证）
