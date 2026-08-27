# references 完整索引（从 SKILL.md 外移，2026-08-27 分层改造）

> 原 SKILL.md 的「详细方案与参考」+「支持文件」两章内容重复，合并于此。


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
| `references/error-mapping.md` | **🆕 错误映射表**（原始报错→人话→修复步骤，覆盖 MCP/浏览器/Cookie/SmartPage/集成 5 大类） | 遇到任何报错时先查此表 |
| `references/e3-browser-write-research.md` | **✅ e3 浏览器写入 API（已闭环）**（mutation 模型：applyMutation + await commitMutation，WS USER_CHANGES 同步，重载持久化验证通过。含完整流程 + pitfall） | 实现 e3 浏览器写入时 |

### 最高频 Pitfalls 速记(细节见 references/pitfalls.md)

> **🆕 2026-08 三周复盘**：行为级教训(验证/台账/假成功清单/发布盲区)已系统整理,见 [retrospective-2026-08](references/retrospective-2026-08.md)。速记新增四条铁律:
> - 🚨 **企微 HTTP API ret=0 ≠ 生效**:假成功清单(sp_submit缺render_mode/listRemove删children/file_modify_secure_setting改internal_auth/children重排op 6-7/webdisk file_status参数)持续增长,每个写操作必须 readback
> - 🚨 **发布状态不能只看版本号**:权限变更等编辑器外操作产生待发布但不推 pad_ver(2026-08-24 假绿事故)。判据=version+publish_time+面板态三交叉;大文档发布走 UI 不走 HTTP API
> - 🚨 **正式文档用用户本人身份创建**(浏览器 per-user cookie),机器人身份建的文档用户只是协作者,删改受限(v0 文档废弃教训)
> - 🚨 **listAfter 是 PREPEND**:按源树正序建页=顺序全反,必须逆序提交+readback 比对
> - 🚨 **图片管线修好后存量占位符不会自愈**(2026-08-24 实测,5页74张 `[图片: alt]` 留存3天):增量同步"未变页面不重建",修复前同步的页面保持旧缺陷。修完图片管线必须:全量审计 → `resync_problem_pages.py` 定向重同步(页面ID不变只重建内容) → 独立读回验证真图块数=源图数(当日 74/74 修复,clean 94.6%→98.4%)。诊断注意:源md里是 authcode URL 时管线本身是通的(实测 200/PNG),别先怀疑外链

- 🚨 **长文档/审核报告必须用 SmartPage 智能文档，不用 w3_ 微文档**（2026-07-24 团队负责人明确要求："这个微文档排版很差，要用智能文档"）。w3_ 微文档渲染 Markdown 表格/层级排版差，SmartPage 排版正常。交付报告类内容默认 `wecom_doc_writer.py smartpage create-with-images --title "标题" --markdown @file`
- 🚨 **smartpage create 的 pages JSON 不支持 @file**：`--pages '[{"page_title":"x","content":"@/path/file.md"}]'` 里的 `@file` 不会被解析，内容会变成字面字符串。必须用 `smartpage create-with-images --markdown @file`（无图片也可用）
- 🚨 **扫码成功判断不能只看 URL**：企微跳转后 URL 可能仍含 `login`/`scenario`（中间跳转页），URL-only 检测永远等不到 → timeout → 不保存 cookie。修复：URL + `wedoc_sid` cookie 双重判断（OR 关系）。保存前轮询等 `wedoc_sid` 写入（最多 15s），保存后验证 `wedoc_sid` 存在
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
- 🚨 **smartpage create --pages 的 JSON content 字段不解析 @file 语法**：`--pages '[{"page_title":"正文","content":"@/path/file.md"}]'` 会把 `@/path/file.md` 当字面字符串写入，不读取文件内容。**改用 `smartpage create-with-images --title "标题" --markdown @/path/file.md`**，该子命令用 `_load_text_arg` 正确解析 @file（2026-07-24 实测：create --pages 写入字面路径，create-with-images 正确写入全文）
- 🚨 **报告类文档优先用 SmartPage（智能文档），不用 w3_ 微文档**：用户明确反馈「微文档排版很差，要用智能文档」。审核报告/分析报告/总结类文档 → SmartPage；w3_ 微文档仅用于纯文本草稿或简单内容（2026-07-24 用户反馈）

---



- `references/e3-native-js-api.md` — **🆕 e3_ 原生 JS API 完整参考**（getCellDataAtPosition 用法、cell 方法列表、图片URL、合并范围、日期转换）
- `references/e3-browser-write-research.md` — **✅ e3 浏览器写入 API（已闭环）**（mutation 模型：applyMutation + await commitMutation → WS USER_CHANGES → 服务端持久化。含完整流程、pitfall、验证记录、探索历程）
- `scripts/e3_browser_write.py` — **🆕 e3 浏览器写入脚本**（mutation API 写入封装：cookie 加载 → monkey-patch 捕获 → 修改属性 → apply + commit → 读回验证 + 重载持久化验证。`--user <id> --url <e3_url> --row N --col M --value "xxx"`）
- `references/e3-merge-fill-verification.md` — **🆕 合并填充验证方法论**（三层递进：表面指标→spot-check→ground-truth；mergeList 偏移根因分析）
- `references/dop-api-data-structure.md` — dop-api 完整数据结构参考（字段类型 ID、行列路径、用户映射、**e3_ protobuf 实测结论**）
- `references/e3-spreadsheet-fallback.md` — **e3_ 电子表格读取方案 v3.0**（JS Runtime + clipboard HTML，protobuf 实测）
- `references/e3-vs-s3-dop-api.md` — 🆕 e3_ vs s3_ dop-api 数据结构差异（已废弃，v3.0 统一用 JS Runtime）
- `references/w3-opendoc-extraction.md` — **w3_ 微文档 opendoc API 提取**（canvas 渲染、自定义格式解析、%uXXXX 解码）
- `references/w3-opendoc-extraction.md` — **w3_ 微文档 opendoc API 提取**（canvas 渲染、自定义格式解析、%uXXXX 解码）
- `references/m4-mind-extraction.md` — **m4_ 思维导图读取**（JSON 节点树递归提取）
- `references/m4-engine-api-extraction.md` — **🆕 m4_ 思维导图 engine API 提取与编辑探索**（React fiber 提取路径、171 方法清单、engineConfig、textContainerEl caret 分析、fileData 结构、键盘编辑验证、p3_/f4_ 方向）
| `references/smartpage-editing-exploration.md` | SmartPage 编辑深度探索（v2-v9 浏览器方案全记录，已被 HTTP API 方案取代） | 了解浏览器方案失败原因时 |
- `references/smartpage-http-api-write.md` | **🆕 SmartPage HTTP API 写入协议**（submit_command + application/protojson，创建/删除/移动/改标题完整格式+错误码+示例代码） | SmartPage 写入操作时必读 |
- `references/retrospective-2026-08.md` | **🆕 2026-08 三周复盘**（同步管线 v0→v3 演进 14 条专项教训 L1-L14 + 7 条行为级教训 B1-B7 + 假成功 API 清单 + 当前管线状态/开放问题） | 做同步/发布/删除/权限操作前,或被用户反复纠正同类问题时必读 |
- `references/smartpage-delete-block.md` — **🆕 SmartPage 删除 block 完整记录**（浏览器键盘验证 + 拦截完整请求体格式 + API 直接删除调试笔记 + 变量获取路径表）
- `references/wecom-messaging.md` — **WeCom 消息媒体发送指南**
- `references/wecom-media-delivery-debug.md` — **企微图片交付排错指南**
- `references/mcp-get-doc-content-multisheet-parsing.md` — **🆕 MCP get_doc_content 多子表 Markdown 解析**（不同子表列数不同、`|`字符列错位、排序破坏边界、重复子表检测、列名模糊匹配、解析脚本模板）
- `references/wecom-doc-image-embedding.md` — **🆕 企微文档图片嵌入与上传**（w3 vs SmartPage 图片支持差异、upload_image.py 直调 API vs Hermes MCP 限制、CDN 二次压缩、晨报高清原理、SmartPage 带图四步法）
- `references/crud-coverage-gap.md` — **🆕 CRUD 覆盖矩阵与差距分析**（各文档类型 × 增删改查 × MCP/浏览器 现状表 + 4 个已识别差距 + 推荐执行顺序；定期复审）
- `scripts/wecom_login.py` — 扫码登录（`--status-file` 输出 JSON 状态文件，轮询即可自动检测扫码完成，不需要用户说"扫完了"。状态值：qr_ready→waiting_scan→scanned→success/timeout/error）
- `scripts/check_cookie_expiry.py` — **🆕 cookie 过期检查**（检查 wedoc_sid/wedoc_ticket 剩余天数，距过期 ≤4 天输出警告，供 cron 主动提醒）
- `scripts/wecom_fetch.py` — 底层 dop-api 调试工具（7 个函数，直接 HTTP 请求 dop-api）
- `scripts/validate_extraction.py` — **🆕 提取结果 ground-truth 验证**（导出子表前 N 行为 CSV，对照原始文档逐列检查）
- `scripts/wecom_doc_auth_check.py` — **🆕 授权状态定时检测**（cookie 提前 4 天预警 + MCP 851014 告警 + 授权历史追踪，Hermes cron 每 6 小时跑，有异常才输出）
- `scripts/wecom_status.py` — **🆕 一键状态自检**（cookie 有效性 + MCP key 有效性 + 可选读写冒烟测试，结构化状态报告 + 每项修复建议。`--user <id> [--test-url <doc_url>] [--json]`。agent 排查"为什么读不了"时先跑这个）
- `scripts/upload_image.py` — **🆕 图片/文件上传工具（直调 MCP JSON-RPC）**（绕过 Hermes 客户端 8KB 限制，无大小限制，99.3% 质量保持，120s 超时。用法：`python3 upload_image.py <image_path> <docid>` 或 `--file` 上传文件）
- `scripts/wecom_doc_writer.py` — **🆕 统一写入口 v5.2.0**（s3_ 记录 CRUD / e3_ 范围写+追加 / w3_ 创建+编辑 / SmartPage 创建+带图四步法 / 图片文件上传。纯 requests 直调 MCP JSON-RPC，无 MCP 框架依赖，任意 AI 工具可用。简单数据结构自动包装：2D 数组→CellData、标量→字段值格式；SmartPage 图片用 `![alt](local:/path)` 占位符自动上传替换 CDN URL。`--help` 查全部子命令）

---
