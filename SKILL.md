---
name: wecom-doc-access-methods
version: 5.12.1
description: >
  读取：s3_ 智能表格(dop-api全量)、e3_ 电子表格(原生JS API)、w3_ 微文档(opendoc API完整正文)、m4_ 思维导图(dop-api/get/mind)。
  编辑：w3_ 微文档(MCP edit_doc_content全量覆写 + 浏览器键盘增删改)、e3_ 电子表格(MCP sheet_* + 浏览器 mutation API 写入)、s3_ 智能表格(MCP smartsheet_* 17种字段类型)。
  图片上传：直调MCP JSON-RPC(无8KB限制，99.3%质量保持)。
  浏览器UI创建：8种类型(智能文档/智能表格/文档/表格/幻灯片/收集表/思维导图/流程图)。
  不可编辑：p3_幻灯片/f4_流程图(方法待探索,非不可行)。m4_思维导图键盘编辑已验证(Tab添加子节点+键盘输入修改文本+自动保存)。SmartPage HTTP API 写入已突破(submit_command + application/protojson, 创建/删除/移动/改标题全部可行, 不需要 WebSocket/浏览器)。SmartPage删除已验证(浏览器键盘清空+Backspace)。
---

# 企微文档访问方法（精简卡 v6.0.0 · 2026-08-27 分层改造）

> 详细内容在 references/，用 `skill_view(file="references/<文件>")` 按需加载。

## 何时用本 skill
读写企业微信在线文档（w3_微文档 / e3_电子表格 / s3_智能表格 / m4_思维导图 / a1_SmartPage / 收集表 / 幻灯片 / 流程图）。
给定 doc.weixin.qq.com 链接就适用。

## 装完必跑 doctor（P0 铁律）
```bash
python3 -m wecom_doc_reader doctor   # 在 scripts/ 目录下
```
三层独立依赖（Python 包 / Skill 文件 / 浏览器二进制）逐层检查 + **真实启动浏览器**。
离线测试全绿 ≠ 可用（Codex/macOS 实证：19/19 通过但无 Chromium）。
浏览器启动 fallback 链：`PLAYWRIGHT_EXECUTABLE` → `PLAYWRIGHT_CHANNEL` → 系统 Chrome（自动）→ bundled Chromium。
SmartPage(a1_) 读取是纯 HTTP，不依赖浏览器，doctor 失败也能读。

## 三条硬禁令（违反必然浪费时间）
1. **禁止用 terminal 盲试接口。** 本 skill 的脚本已封装全部已知可行路径；接口报错先查
   `references/error-mapping.md`（原始报错 → 人话 → 修复步骤），不要换参数硬磕。
   实证：2026-08-27 一次盲试消耗 240 次命令 / 2 小时 15 分，而错误码答案就在该文件里。
2. **禁止把 URL 前缀当类型猜。** 类型判定看 `references/doc-type-matrix.md`，
   不同前缀（w3_/e3_/s3_/m4_）读写路径完全不同。
3. **身份隔离不可绕过。** 必须以当前回合绑定的 principal 调用，禁止复用他人 cookie/凭据。
   详见 `references/identity-resolution-pitfalls.md`。

## 默认正确路径（按类型直接取用）
| 目标 | 首选方法 | 脚本/入口 |
|---|---|---|
| 读 w3_ 微文档 | opendoc API（canvas 渲染，DOM 无效） | `scripts/test_wecom_doc_reader.py` 同目录 reader |
| 读 e3_ 电子表格 | SpreadsheetApp 原生 JS API | 同上，见 `references/e3-native-js-api.md` |
| 读 s3_ 智能表格 | dop-api 全量结构化 | 同上 |
| 读 m4_ 思维导图 | dop-api/get/mind | 同上 |
| 读 a1_ SmartPage | smartcanvasread 纯 HTTP（零浏览器依赖，带完整性指标） | `python3 -m wecom_doc_reader read <user> <url>` |
| 写 w3_ | MCP `edit_doc_content` 全量覆写 | `references/mcp-api-guide.md` |
| 写 e3_ / s3_ | MCP `sheet_*` / `smartsheet_*` | 同上 |
| 图片上传 | 直调 MCP JSON-RPC（无 8KB 限制） | `references/mcp-api-guide.md` |
| 安装自检 | doctor（真实启动浏览器） | `python3 -m wecom_doc_reader doctor` |
| **扫码授权（auth_required 时）** | 转图直发 + 后台轮询，**不发 URL** | 见下方「扫码授权铁律」 |

## MCP 挂了 ≠ 读不了（通道独立）
MCP 返回 850001/851014 时，浏览器通道（扫码 cookie）完全独立可用。
`wecom_status.py` 已分栏显示 MCP / Browser 两通道，浏览器通就还能读。

## 扫码授权铁律（2026-08-27 某成员授权案 8 轮返工换来的）
1. **入口(统一,自动识别本机是 Hermes 还是 OpenClaw)**：`python3 scripts/wecom_auth_entry.py --check <发信人ID>`(本 skill 目录下;需要授权时改用 `--wait-done <发信人ID>`,返回二维码路径+轮询命令)。
   发信人 ID 用收到消息时看到的那个(Hermes 侧 `wo…`,OpenClaw 侧企业 userid),不要互换。
   Hermes/OpenClaw 双入口的内部实现、显式传 wecom_userid 的原因（2026-09-01 修）、
   小明禁止用 `~/.hermes` 入口等细节 → `references/auth-entry-details.md`。
   `auth_required` → `--wait-done`（不是 `--wait`），返回 `reply_media` + `poll_command`。
2. **发二维码一律发图片，绝不发 URL/链接**：企微聊天里链接打不开（8-27 实测 7 轮扫不了）。
   `reply_media` 是 1-bit PNG 裂图，必须先转换：
   `python3 scripts/qr_to_wecom.py <qr.png> <qr.jpg>` → 1160×1160 白边 RGB JPEG，
   用 `MEDIA:` 直发 + 提示「长按识别图中二维码」。
3. **等待期禁止空转刷屏**：用 `poll_command` 后台轮询（terminal background 或下回合再查
   `--status`），不要连发空消息催用户（同案 10+ 条空消息把会话推到 364 条）。
   **授权完成必须第一时间主动告知用户**（「授权成功，可以正常用」一句话），
   绝不许只发图不跟结果、干等用户来问（2026-09-14 某负责人纠正：授权完成他来问才知道）。
   实现方式：发图后立刻起后台轮询进程（terminal background + notify_on_complete，
   循环 `--status <transaction_id>` 直到 completed），完成即回复。
4. **只查同一 transaction_id**：用户扫码后不要重新生成二维码，超时就明说并重新起一个。
5. **扫码即自动捕获姓名（2026-09-02 v5.11.0）**：扫码登录自动带名回写 principal，
   无需人工配对；细节（login_user 字段、cookie 有效才能拿名字、登录页标注≠身份验证）
   → `references/auth-entry-details.md` 与 `references/wecom-login-user-info-capture-2026-09.md`。
6. **MCP server v1.0.5 能力重估（2026-09-10 v5.12.0）**：实测 25 个工具——
   e3_ 在线表格已有专用读写工具（sheet_* 5 个，旧认知"e3_ 不支持 MCP"已过时，仅 get_doc_content 不支持）；
   新增 create_doc / smartpage_create / smartpage_export_task / upload_doc_file 等。
   **MCP 仍无全局搜索工具**（按关键词找文档走浏览器）。
   全量工具清单 → `references/mcp-api-guide.md`。

## 卡住时的固定顺序（不要自创第四步）
1. 读 `references/error-mapping.md` 对号入座；
2. 读 `references/pitfalls.md`（60+ 条实战踩坑，多数问题在此有解）；
3. 仍无解 → 向用户说明「已查 X/Y，卡在 Z，需要的是 A 还是 B」，不要继续试错。

## 章节索引（按需加载）
| 需求 | 加载文件 |
|---|---|
| 类型/前缀/能力矩阵 | `references/doc-type-matrix.md` |
| 报错定位 | `references/error-mapping.md` |
| 全部踩坑 | `references/pitfalls.md` |
| Playwright + dop-api 详细步骤 | `references/playwright-dop-api-guide.md` |
| MCP 能力范围与限制 | `references/mcp-api-guide.md` |
| 身份隔离规则 | `references/identity-resolution-pitfalls.md` |
| 扫码登录后捕获用户信息（login_user/回写姓名） | `references/wecom-login-user-info-capture-2026-09.md` |
| 其余 30+ 文件完整索引 | `references/reference-index.md` |
| 改造前原始章节（定位/适用场景/身份隔离全文/方案速查/故障速查） | `references/original-context.md` |

## 反馈
踩到新坑 → 追加到 `references/pitfalls.md`，不要改写历史条目；重大方法变更同时更新本卡的
「默认正确路径」表。
