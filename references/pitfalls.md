# 企微文档读写 Pitfalls 全集(索引)

> 原文件 56629 字符超 5000 门禁,已拆为 18 个分片(2026-09-08,只搬不删,备份 `references/pitfalls.md.bak-20260908`)。
> 新增坑:追加到对应分片,不要往本索引写正文。

## 分片索引

- `references/pitfalls/p1.md` — auth_flow 脚本:轮询超时 ≠ 授权失败,标 invalid 前必须先验证(2026-07-21 修复);Pitfalls;解码相关;opendoc 陷阱;startrow 陷阱
- `references/pitfalls/p2.md` — Cookie / 登录相关
- `references/pitfalls/p3.md` — 🚨 不要混淆三种认证机制（2026-06-26 踩坑）;🚨 用户发送文件附件到企微机器人 — 平台不支持（2026-07-13 实测）;🚨 QR 图片必须在 workspace 目录 + 转 RGB（2026-07-16 踩坑）;🚨 "不要覆盖了再恢复"（2026-07-16 团队负责人纠正）;crontab / cron 环境异常处理;crontab 环境…
- `references/pitfalls/p4.md` — Cron 合并原则（2026-06-27 踩坑 — 两个 cron 功能重叠）;lark-cli 读写参数;文档类型完整性;写操作安全;w3_ 微文档 opendoc API 已实现（2026-07-16 v5.0 修复）;w3_ HYPERLINK 清理…
- `references/pitfalls/p5.md` — e3_ dop-api 返回 protobuf 二进制（🚨 2026-06-15 v3.0 实测确认）;e3_ 含图片/附件列的子表必须走 dop-api（2026-06-15 踩坑）;async_playwright 必须带括号;🚨 MCP get_doc_content 多子表 Markdown 解析（2026-06-29 踩坑 — 技术工单表 24 子表实测）;w3_ 微文档 _read_dom 只返回工具栏文字（2026-07-16 实测，已修复）
- `references/pitfalls/p6.md` — edit_doc_content 编辑能力完整图谱（2026-07-16 系统性实测）;w3_ 微文档浏览器编辑：增删改三项验证（2026-07-16 实测）
- `references/pitfalls/p7.md` — 对比总结（2026-07-16 全部实测验证）;权限隔离铁规（2026-07-16 团队负责人要求）;🚨 一键授权脚本 — 脚本做厚，SOUL.md 做薄（2026-07-16 同事A对话复盘）;🚨 轮询超时 ≠ 授权失败 — 标记凭证 invalid 前必须先 verify（2026-07-21 修复）;🚨 MCP 失败后必须 Fallback 到浏览器方案（2026-07-16 团队负责人纠正）
- `references/pitfalls/p8.md` — 🚨 分层架构：脚本做厚，SOUL 做薄（2026-07-16 团队负责人纠正）;🚨 发图片/链接要直接能用，不要让用户复制（2026-07-16 团队负责人要求）;🚨 系统性设计原则：不要打补丁式修复（2026-07-16 团队负责人纠正）;🚨 QR 码保存路径必须在企微 MEDIA 白名单目录（2026-07-16 实测）;🚨 wecom_login.py 扫码成功但 cookie 未保存（2026-07-23 修复）;🚨 QR 登录异步集成：--status-file 模式（2026-07-23 团队负责人要求）…
- `references/pitfalls/p9.md` — 🚨 企微文档 Skill 集中化（2026-07-16 团队负责人要求）;🚨 身份隔离通用原则（2026-07-16 团队负责人要求）;🚨 lark-cli config.json 新用户 OAuth 会覆盖旧用户 token（2026-07-16 发现+修复）;🚨 分层架构验证：脚本做厚 vs SOUL 做薄的实际效果（2026-07-16 复盘）;🚨 安全加固：5 个审计问题修复（2026-07-16 Codex 审计）
- `references/pitfalls/p10.md` — 🚨 企微登录 vs 飞书 OAuth 不要搞混（2026-07-16 实际踩坑）
- `references/pitfalls/p11.md` — e3_ 电子表格 MCP 编辑功能矩阵（2026-07-16 实测）;s3_ 智能表格 MCP 编辑功能矩阵（2026-07-16 实测）
- `references/pitfalls/p12.md` — m4_ 思维导图编辑能力探索（2026-07-16 深度实测 v3）;浏览器 UI 创建文档流程（2026-07-16 实测）
- `references/pitfalls/p13.md` — 其他类型编辑能力探索（收集表/幻灯片/流程图 — 2026-07-16 实测）;SmartPage 浏览器编辑：机器人创建的文档用户无写入权限（2026-07-15 实测）;🆕 SmartPage 嵌入图片坑（2026-07-22 另一 Agent 实测）
- `references/pitfalls/p14.md` — SmartPage（智能文档）编辑探索（2026-07-16 深度实测）
- `references/pitfalls/p15.md` — SmartPage（智能文档）编辑 — submit_command API（2026-07-16 重大突破）
- `references/pitfalls/p16.md` — Playwright canvas bounding_box 返回 None（2026-07-16 实测）;Playwright 点击视口外元素超时（2026-07-16 实测）;浏览器编辑结论原则（2026-07-16 团队负责人纠正）;🚨 USER.md 是全局的，不按 sender 隔离（2026-07-16 严重踩坑）;SOUL.md 是系统提示词源头（2026-07-16 发现）;不改框架，用现有机制解决（2026-07-16 团队负责人要求）
- `references/pitfalls/p17.md` — 验证充分性原则（2026-06-15 用户纠正）;🚨 数据完整性验证 ≠ 表面指标（2026-06-15 踩坑）;🚨 mergeList 行号偏移（2026-06-15 v4.0.2 修复 — 最容易踩的坑）;🚨 用最轻量的工具完成任务（2026-07-07 设计原则）;🚨 Skill 建设铁规：未实测的代码不准写进方案（2026-06-15 血泪教训）;🚨 安装完整性 = 三层独立依赖（2026-08-27 Codex/macOS 实证）…
- `references/pitfalls/p18.md` — 🚨 MCP 通道与浏览器通道相互独立（2026-08-27 新增）;🚨 测试套件禁止"ALL PASS"过度承诺（2026-08-27 Codex 反馈）;陷阱：版本改了但没走发布闭环 = 集成没完成（2026-09-03）
