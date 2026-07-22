# 企微文档 CRUD 覆盖矩阵与差距分析（2026-07-22 评估）

> 对照「任意 AI 工具 × 任意企微文档 × 增删改查 × 高效顺畅」目标的现状评估。定期复审——写能力短板会随版本演进收窄，每次重大更新后重测对应格子。

## 一、CRUD 覆盖矩阵

| 类型 | 读(MCP) | 读(浏览器) | 写(MCP) | 写(浏览器) |
|---|---|---|---|---|
| s3_ 智能表格 | ✅(2000 条限) | ✅ dop-api 全量 | ✅ 完整 17 字段类型 + records CRUD | ⚠️ 键盘增/改（删未验证） |
| e3_ 电子表格 | ❌(851000) | ✅ 原生 JS API | ✅ range/append/add_sub/delete_sub | ✅ 键盘增删改 |
| w3_ 微文档 | ✅ 异步轮询 | ✅ opendoc | ⚠️ edit_doc_content 只改 bot 创建的（成员文档报 851003） | ✅ 键盘增删改 |
| SmartPage 智能文档 | ✅ smartpage_export_task | ✅ pageStore | ❌ 无 edit API（不支持 edit_doc_content） | ⚠️ submit_command（需手工构造 changeset）+ smartpage_create 带图四步法 |
| m4_ 思维导图 | ❌ | ✅ dop-api/get/mind | ❌ | ⚠️ 键盘增/改（删未验证；engine 常量未确定） |
| 收集表/幻灯片/流程图/汇报 | ❌ | ⚠️ DOM 文本/部分未测 | ❌ | ❌ 基本无写方案 |

**读能力**：成熟——4 种主力类型（s3_/e3_/w3_/m4_）+ SmartPage 都有验证过的读取路径。
**写能力**：短板——只有 s3_/e3_/w3_ 三种成熟；SmartPage 编辑有突破但未封装；m4_ 只能键盘模拟；收集表/幻灯片/流程图基本无写能力。

## 二、四个已识别差距

### P0 — 安全：MCP API key 明文泄露在公开 GitHub 仓库
- `scripts/wecom_doc_auth_check.py:36` 含明文 `apikey=<key>`，本地 + GitHub 公开版两边都有
- 2026-07-17 那轮脱敏审查（222 处替换）漏扫了 .py 源码里的凭据字符串
- **修复**：① 企微后台轮换 key ② 脚本改读 `WECOM_MCP_APIKEY` 环境变量 ③ 清 git 历史 ④ 详见 skill-building-standard §17.6

### P1 — 同步滞后：公开仓库落后本地 2 周以上
- GitHub 35 文件 vs 本地 46+，缺 pitfalls.md（1045 行）/ playwright-dop-api-guide.md / mcp-api-guide.md / changelog.md / retry-mechanism.md / cookie-watchdog.md / smartpage-delete-block.md 等
- README 停留 v4.5.0/2026-07-01，本地已 v5.1.0/2026-07-17
- **修复**：推送 + 文件清单 diff 校验，详见 skill-building-standard §10.6

### P2 — 写能力未封装：缺统一写入口 + SmartPage 编辑未函数化
- 没有 `wecom_doc_writer.py`：s3_/e3_/w3_ 写操作散落在 MCP 调用 + 浏览器键盘 + submit_command 三套机制，AI 工具要拼三种范式
- SmartPage 编辑要手工构造 EtherPad changeset（base-36 编码长度），极易出错；没有封装函数
- m4_ engine API 方法常量未确定（传字符串返 null），删操作未验证
- **修复优先级**：① 封装 `wecom_doc_writer.py`（s3_/e3_/w3_ 一个函数搞定，MCP 优先浏览器 fallback）② SmartPage 编辑封装成 Python 函数（自动算 changeset）纳入主包 ③ m4_ 确定 engine 常量或确认键盘方案够用

### P3 — 可移植性：MCP server 名硬编码 + 身份隔离章节依赖 Hermes 本地脚本
- SKILL.md 用 `mcp________smartsheet_*`（Hermes 命名），其他 AI 工具 MCP server 名不同
- 身份隔离章节引用 `wecom_auth_flow.py`/`lark_auth_flow.py`（Hermes/OpenClaw 专用），全新 AI 工具没有
- 缺「0→1 集成指南」（copy 目录 / pip install / 扫码 三步上手）
- `reader.py:258` 硬编码 `doc.weixin.qq.com/home/recent`
- **修复**：抽离身份隔离章节到独立 reference 标「Hermes/OpenClaw 专用」；主 SKILL.md 给通用 onboarding；MCP 工具名改通用占位 + 说明

## 三、推荐执行顺序

1. **立即**：轮换泄露的 key + 脚本环境变量化 + 清 git 历史（P0）
2. **1-2 天**：推送 + 文件清单校验 + README 更新到 v5.1.0（P1）
3. **本周**：封装 `wecom_doc_writer.py` + SmartPage 编辑函数化（P2）
4. **后续**：m4_ 常量确定、幻灯片/流程图写能力 PoC、可移植性抽离（P2/P3）

## 四、幻灯片/流程图写能力探索方向（待 PoC）

- **p3_ 幻灯片**：service 架构（canvasService 21 法 / slideListService 45 法），双击出现 CopyPasteAssist textarea（剪贴板辅助非编辑器），无 engine。方向：通过 slideListService 方法操作
- **f4_ 流程图**：mxGraph 库渲染，fileData 是 mxGraph XML（draw.io 兼容），双击后 INPUT 出现（可能节点文本编辑器）。方向：① 双击触发文本编辑 ② 直接改 mxGraph XML 回写 ③ mxGraph JS API
