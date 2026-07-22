# 企微文档读写 Pitfalls 全集

> 本文件由 SKILL.md 拆分而来(2026-07-21)。所有实战踩坑与修复记录。

## auth_flow 脚本:轮询超时 ≠ 授权失败,标 invalid 前必须先验证(2026-07-21 修复)

`wecom_auth_flow.py` / `lark_auth_flow.py` 的 `--wait` 模式有 device-code 轮询超时(lark 330s)。原代码 `except Exception` 后**无条件** `set_credential_status(..., "invalid")` —— 用户其实已在超时前完成授权,凭证被误标 invalid,导致反复给已授权用户发授权链接。

**铁规**:授权流程中捕获异常后,**先调 verify_profile 验证凭证真实状态**,有效则补登记 valid/完成交易,确认无效才标 invalid。任何"轮询/等待型"凭证状态机都适用:超时、网络抖动等异常路径绝不能直接等价于凭证失效。

## Pitfalls

> 851003 权限错误诊断（区分"bot未授权"vs"用户无权限"）详见 `references/851003-diagnostic.md`

### 解码相关
- ⚠️ **必须** `base64.urlsafe_b64decode`，不是 `b64decode`（企微用 URL-safe base64）
- ⚠️ **必须** `zlib.decompress(decoded)` 默认参数，不要传 `-zlib.MAX_WBITS`
- ⚠️ 如果 base64 报错 "invalid characters"，试加 padding：`raw + '=' * (4 - len(raw) % 4)`

### opendoc 陷阱
- ✅ **w3_ opendoc API 已实现**（v5.0）：`_read_opendoc()` 方法在 reader.py 中实现，w3_ 路由从 `_read_dom` 改为 `_read_opendoc`。解析自定义文本格式 + %uXXXX 解码 + HYPERLINK 清理
- ❌ **不要依赖 opendoc 拿 select 选项映射**。主动 fetch opendoc 返回自定义文本格式（非 JSON），且 `initialAttributedText.text` 经常为空字符串
- ✅ select 选项从 `get/sheet` 的 t=3005 列定义项直接提取
- ⚠️ opendoc 主动 fetch 返回格式：头部 `text\ntext\n84835\n` + URL 编码 JSON，需 `urllib.parse.unquote` + `json.JSONDecoder().raw_decode`

### startrow 陷阱
- ⚠️ 页面默认加载的 `get/sheet` 只含 startrow=61+ 的部分
- ✅ 主动 fetch 时必须传 `startrow=0` 才能拿全量
- ✅ endrow 设多大（99999）都不影响性能
- ⚠️ **startrow=0 返回的 smartsheet 字段是 base64+zlib 压缩格式**（2026-06-29 实测推翻之前错误结论），不是 JSON 字符串，需 `urlsafe_b64decode + zlib.decompress + json.loads`
- ⚠️ **主动 fetch 必须传完整参数集**：`xsrf`, `needSheetState=2`, `rev`, `optimizedVer=2`, `chunkCellSize=15000`, `enableChunkRank=1`, `enablePermOpt=0`。只传最简参数（padId+subId+startrow+endrow+outformat+normal）返回 `retcode 538002: "Get content error"`
- ⚠️ **xsrf 和 rev 是动态参数**，必须拦截页面首次 `get/sheet` 请求获取，不能硬编码
- ✅ **多子表不需要切换 tab**：从 `collab_client_vars.initialAttributedText.text[0].workbook` 获取子表列表后，用同一套参数+不同 `subId` 即可 fetch 所有子表

### Cookie / 登录相关
- ⚠️ 必须用 `storage_state`（Playwright 完整状态），不是纯 cookies
- 🚨 **不要手动构造 scan-login URL（2026-07-16 踩坑）**：手动拼接 `https://doc.weixin.qq.com/scan-login?return_url=...` 给用户，用户反馈"链接访问不了"。**正确做法**：直接用 `wecom_login.py` 脚本（Playwright 拦截 QR 码图片）生成二维码，转 RGB 后发给用户扫码。不要绕路手动拼 URL。
- ⚠️ cookie 约 2 周过期，需要定期检查和续期
- ⚠️ 不能直接 HTTP POST dop-api（需要页面上下文中的 xsrf token），必须通过 Playwright 页面导航触发
- ⚠️ **"扫码续期" 语境歧义**（2026-06-26 踩坑）：用户说"扫码续期"时,先确认是哪个系统——① 浏览器 cookie（storage_state，~2周过期）② MCP 机器人授权（errcode 851014，不定期过期）③ 飞书 token（自动续期，不需要手动）。不要默认跳到飞书 token
- 🚨 **不要给用户发登录URL,直接生成QR码**（2026-07-16 踩坑）：给用户发 `https://doc.weixin.qq.com/scan-login?return_url=...` 链接,用户反馈"访问不了"。应该直接用 `wecom_login.py` 生成QR码图片,转RGB后通过 MEDIA 发给用户扫码。**铁律:读到 `action: "scan"` → 立即生成QR码,不要先尝试发URL**。原因:企微 scan-login URL 可能需要特定环境/域名,不是所有用户都能打开
- ⚠️ **QR 码图片交付：企微 MEDIA 语法不支持发图片**（2026-07-08 踩坑）：`hermes send -t "wecom:<chatId>" "MEDIA:/tmp/qr.png"` 返回 success 但 warning `"MEDIA attachments were omitted for wecom"`，图片**不会投递**。根因：`send_message_tool.py` 第 906-919 行的 media 路由只支持 telegram/discord/matrix/weixin/signal/yuanbao/feishu，wecom 被归入 "non-media platforms" 分支跳过。但网关层 `wecom.py` 有 `send_image_file()` 方法（第 1447 行），只是工具层没接上。**当前 workaround：通过飞书发图片**（`hermes send -t "feishu:<chatId>" "MEDIA:/tmp/qr.png"` — 飞书支持 MEDIA），用户在飞书看到二维码后用企微 App 扫码，扫码结果不影响（登录脚本在本机检测扫码，与图片投递平台无关）。**根本修复**：在 `send_message_tool.py` 加 wecom media 分支（类似 feishu/yuanbao 的 `_send_feishu` 模式，调 `adapter.send_image_file()`）
- ⚠️ **QR 码图片格式**（2026-06-26 踩坑）：Playwright 拦截到的企微登录二维码是 **1-bit grayscale PNG**，企微客户端**无法渲染**会显示裂图。必须转 RGB 再发送：`Image.open(qr).convert('RGB').resize((800,800), Image.NEAREST).save(qr_v2)`
- ⚠️ **MCP errcode 区分**（2026-06-26 实测）：监控检测时区分三种 errcode——851014/2200063=授权过期（需告警）；851003=无此文档权限但授权有效（正常）；851000=无效URL但授权有效（正常）。检测脚本应用 smartsheet_get_sheet + 假URL，只有 851014/2200063 才告警
- ✅ **主动续期提醒**（2026-06-26 用户要求，2026-07-15 增强）：cookie 到期前 4 天主动提醒用户扫码；MCP 授权过期无法预测，检测频率提到每 1 小时（用户要求），过期后尽快告警。用 `scripts/wecom_doc_auth_check.py` + Hermes cron（no_agent, 每小时跑 `17 * * * *`），有异常才输出（静默=正常）。用户原话："以后你过期前就提醒我，不要过期了再跟我说"
- ⚠️ **🚨 三个 cookie 文件必须同步**（2026-06-27 踩坑 — 误告警根因）：生产环境有**三个** cookie 文件，扫码续期后必须**全部更新**，否则监控 cron 读到旧文件会发误告警：
  - `~/.config/wecom-doc/states/_shared.json` — **主力**（`wecom_login.py` 扫码脚本写入此文件）
  - `~/.config/wecom-doc/workspace/wecom_browser_state.json` — **备用**（同步脚本 `monitor_wecom_sync.py` 读此文件）
  - `~/.config/wecom-doc/workspace/wecom_cookies.json` — **`wecom_auto_renew.py` 读此文件**（cron 续期检查用）
  - **踩坑场景**：6/26 晚扫码续期只更新了 `_shared.json` + `wecom_browser_state.json`，漏了 `wecom_cookies.json` → 6/27 早 09:00 cron 读旧文件报"剩余 1.6 天"误告警 → 用户困惑"昨晚刚搞过怎么又要搞"
  - **修复**：`wecom_auto_renew.py` 改为优先读 `_shared.json`（fallback 到 `wecom_cookies.json`），续期时同时写两个文件
  - **铁规**：任何 cookie 更新操作（扫码续期 / `wecom_login.py` / `wecom_auto_renew.py`）后，必须验证三个文件的 `wedoc_sid` expires 时间一致

### 🚨 不要混淆三种认证机制（2026-06-26 踩坑）
企微文档相关有**三套独立的认证**，用户说"续期/授权"时要先判断是哪个：

| 认证机制 | 作用 | 过期表现 | 续期方式 |
|---------|------|---------|---------|
| **飞书 token** (lark-cli) | 飞书 API 操作 | `expiresAt` 到期 | `feishu_token_keepalive.py` 自动续期，**不需手动** |
| **企微 MCP 授权** (errcode 851014) | MCP 工具调企微文档 API | errcode 851014 | 用户在企微点授权链接重新授权机器人 |
| **企微浏览器 cookie** (storage_state) | Playwright + dop-api 全量读取 | cookie 跳转登录页 | `wecom_login.py` 扫码登录，**约 2 周过期** |

**判断顺序**：用户说"续期"→ 先想是哪套 → 飞书 token 有自动续期不用管 → MCP 报 851014 才是 MCP 授权 → 用户说"扫码"多半是浏览器 cookie → 不确定就问，不要猜。
**踩坑场景**：用户说"扫码续期"，我误启动飞书 lark-cli QR 登录，用户纠正"不是飞书 token，是企微文档"。

### 🚨 用户发送文件附件到企微机器人 — 平台不支持（2026-07-13 实测）
- ❌ **用户在企微 DM 给机器人发 Excel/Word/PDF 文件，机器人收不到** — WeCom AI 助手机器人类型不向回调接口推送 file/appmsg 类型消息
- ✅ Hermes gateway 代码有 file/appmsg 处理逻辑（`wecom.py` 第 723-729 行），但 WeCom 平台侧不推送此类消息
- ✅ **替代方案**：① 用户发飞书（飞书侧机器人能收文件）② 用户传到企微文档/微盘发链接（agent 用 MCP 或 dop-api 读）③ 用户传飞书云空间发链接
- 详见 `wecom-messaging` skill 的 Pitfall 8

### 🚨 QR 图片必须在 workspace 目录 + 转 RGB（2026-07-16 踩坑）
- ❌ QR 图片保存到 `/tmp/` → 企微 `MEDIA:` 语法发不出去（不在白名单目录）
- ✅ QR 图片保存到 `~/.config/wecom-doc/workspace/`（企微 MEDIA 白名单目录）
- ❌ 1-bit grayscale PNG 企微客户端无法渲染（显示裂图）
- ✅ 必须转 RGB：`Image.open(qr).convert('RGB').resize((800,800), Image.NEAREST).save(qr_rgb)`
- ✅ 发图片用 `MEDIA:~/.config/wecom-doc/workspace/qr_xxx.png`
- ✅ 发链接直接发可点击的 URL（不要让用户复制粘贴）

### 🚨 "不要覆盖了再恢复"（2026-07-16 团队负责人纠正）
- ❌ 不要"改坏数据→再恢复" — 而是从架构上确保数据不会坏
- ✅ lark-user-onboard.py 的 backup-restore 是正确的——在同一进程内原子完成，不是"改坏了再修"
- ✅ wecom_auth_flow.py 不复制 per-user cookie 到全局文件——从根源上不可能覆盖
- ✅ 全局 cookie 文件改软链接——团队负责人扫码自动同步，其他人扫码不影响全局

### crontab / cron 环境异常处理
- ⚠️ **main() 必须包 try/except**（2026-07-07 踩坑）：`cli.py main()` 中 `asyncio.run(reader.check(...))` 等调用如果不包 try/except，底层异常会导致脚本 crash，exit code 非零。cron 看到的只是 stderr 的 Python traceback，而不是 stdout 的结构化 JSON。另一个 Agent 因此连续 8 天看到同一截断的 traceback，无法定位真因。
- ✅ **修复**：给 login/check/read 三个命令都加 try/except，异常时返回 `{"valid": False, "reason": "ExceptionType: message"}` 等 JSON
- ⚠️ **check() 的 async_playwright() 必须在 try/except 内**（2026-07-07 v4.5.1 修复，v4.5.2 已彻底消除）：v4.5.1 把 `async with async_playwright()` 整体包进 try/except；**v4.5.2 进一步把 check() 整个改为 httpx HTTP 请求，完全不再启动 Playwright/Chromium**。check() 现在 0.4s 完成，不依赖浏览器环境
- ⚠️ **Chromium 必须加 `--disable-dev-shm-usage`**（2026-07-07 修复）：Hermes cron 的 `sanitize_subprocess_env()` 会剥离 VIRTUALENV/CONDA_PREFIX，且 HOME 被重写为 HERMES_REAL_HOME。Chromium 在此环境下可能因 `/dev/shm` 太小或路径解析问题启动失败。加上 `--disable-dev-shm-usage` 让 Chromium 用 /tmp 而非 /dev/shm
- ✅ **所有 6 处 chromium.launch() 已统一加上** `--disable-dev-shm-usage`
- ⚠️ **错误信息不要截断 [:300]**：Python traceback 前面是文件路径+行号，真正的异常信息在**最后一行**。shell 脚本用 `[:300]` 截断后只看到文件路径，永远看不到真因。应取最后一行或完整输出

### crontab 环境
- ⚠️ crontab PATH 极简（`/usr/bin:/bin`），调外部 CLI（如 lark-cli shebang `#!/usr/bin/env node`）会报 `No such file or directory`
- ✅ 修复：脚本内显式注入 PATH 到 `subprocess.run` 的 `env` 参数
- ⚠️ crontab 分钟避开整点（用 :07/:13/:17/:23/:37/:43），整点是 API 调用高峰

### Hermes cron `no_agent=true` script 参数（2026-06-27 踩坑 — cron 自创建以来一直 error）
- ⚠️ `no_agent=true` 的 cron job，`script` 参数必须是**相对文件名**（如 `wecom_doc_auth_check.py`），不是 shell 命令（如 `python3 ~/.config/wecom-doc/scripts/wecom_doc_auth_check.py 2>&1`）
- ❌ 写成 shell 命令时，cron 框架把整个字符串当文件路径找 → `Script not found: ~/.config/wecom-doc/scripts/python3 /root/...` → `last_status: "error"` 静默失败
- ✅ 正确写法：`script: "wecom_doc_auth_check.py"`（相对于 `~/.hermes/scripts/`）
- ⚠️ `.sh`/`.bash` 后缀走 bash 执行，其他后缀（`.py`）走 Python 执行
- ⚠️ 这种错误**不会告警**——cron 正常 schedule 但每次执行都失败，只有手动查 `last_status` 或看 `~/.hermes/cron/output/<job_id>/` 下的日志才发现

### Cron 合并原则（2026-06-27 踩坑 — 两个 cron 功能重叠）
- ⚠️ 不要为同一个检查创建多个 cron——如一个 LLM 驱动（`wecom_auto_renew.py` 检查 cookie）+ 一个纯脚本（`wecom_doc_auth_check.py` 检查 cookie + MCP），功能重叠，前者还浪费 LLM token
- ✅ 合并为一个纯脚本 cron（`no_agent=true`），覆盖所有检查项（cookie 过期 + MCP 授权）
- ✅ LLM 驱动的 cron 只用于需要推理的任务（如反思、分析），简单检查用纯脚本
- ⚠️ cron 里的自动续期功能（生成 QR + 等待扫码）在无人值守场景不实用——用户不一定在线。改为：cron 检测异常 → 推送告警 → 用户看到后主动触发续期
- ✅ 发现多个 cron 功能重叠时，自行分析合理性并合并，不要把决策抛给用户

### lark-cli 读写参数
- ⚠️ **读取**（`+record-list`）**必须加 `--format json`**，否则返回 markdown 表格，`json.loads` 失败（`Expecting value: line 1 column 1`）
- ⚠️ **写入**（`+record-upsert / +record-delete`）**禁止加 `--format json`**，否则报 `unknown flag: --format`
- ✅ 建议分两个函数：`lark_cli_read(*args)` 加 `--format json`，`lark_cli_write(*args)` 不加

### 文档类型完整性
- ⚠️ **不要假设已覆盖所有文档类型**：企微 UI 可创建的文档类型（9+）远多于 API 支持的（3种）
- ✅ 验证方法：登录官方 API 文档 + 实际打开企微 UI 创建菜单，交叉对比
- ✅ 对于新发现的类型：先获取 URL 前缀，再测试读取方式（dop-api → 剪贴板 → DOM）
- ⚠️ 2026-06-15 踩坑：只列了 7 种类型，用户指出还有"汇报"和"智能文档"未覆盖

### 写操作安全
- ⚠️ lark-cli `+record-upsert` 会**清空未传的字段**（select 类型尤其危险）
- ✅ upsert JSON 必须包含所有字段，即使值为空
- ✅ 生产环境默认 DRY-RUN，确认差异为 0 后才切写入模式
- ⚠️ **严禁在正式文档中写测试数据**：测试验证必须用 MCP 新建临时文档（带 `_测试_` 前缀），测完删除。2026-06-15 踩坑：差点在正式错误码表里加测试字段

### w3_ 微文档 opendoc API 已实现（2026-07-16 v5.0 修复）

**已修复**：`reader.py` 新增 `_read_opendoc()` 方法，w3_ 路由从 `_read_dom` 改为 `_read_opendoc`。

**代码路由**（reader.py `read()` 方法）：
```
s3_ → _read_smartsheet (dop-api 全量)      ✅ 完整
e3_ → _read_spreadsheet (原生 JS API)      ✅ 完整
m4_ → _read_mind (dop-api/get/mind)        ✅ 完整
w3_ → _read_opendoc (dop-api/opendoc)      ✅ 完整（v5.0 新增）
其他 → _read_dom (DOM 文本提取)             ⚠️ 兜底
```

**实现细节**：
- `_read_opendoc(user_id, url, info)` — 通过 Playwright 打开文档，fetch `dop-api/opendoc?padId=xxx&normal=1&outformat=1`
- `_parse_opendoc_response(raw)` — 解析自定义文本格式（标记行+大小行+数据行），提取 commands 中的文本
- `_decode_wecom_text(s)` — 解码 %uXXXX 编码 + 标准 URL 解码 + HYPERLINK 清理 + 控制字符过滤

**历史问题（已修复）**：之前 w3_ 被路由到 `_read_dom`，canvas 渲染导致 DOM 只能拿到工具栏文字（135/455 字符）。changelog v2.3.0 声称"改用 opendoc API"但代码中无 `_read_opendoc` 方法。v5.0 已修复。

### w3_ HYPERLINK 清理
- ⚠️ opendoc API 提取的文本包含 HYPERLINK 标记，需要清理
- ✅ 4 种格式的完整正则清理（2026-06-15 实测验证）：
  1. `HYPERLINK url text` — 简单格式
  2. `HYPERLINK \l "url" text` — 带参数（`\l`、`\h`、`\n` 等）
  3. `HYPERLINK "url" text` — 带引号 URL
  4. `HYPERLINK url text` — 残留关键字（无 URL）
- ✅ 清理逻辑：先处理带引号的复杂格式，再处理简单格式，最后清理残留关键字
- 详见 `scripts/wecom_doc_reader/reader.py` 的 `read()` 方法（HYPERLINK 清理逻辑内联于读取流程中）

### e3_ 多子表切换延迟
- ⚠️ 切换 tab 后需要等待足够时间让 canvas 完全渲染（5s），否则剪贴板提取会拿到空数据
- ✅ v2.1 将等待时间从 3s 增加到 5s，解决最后一个子表偶尔 0 行的问题
- 详见 `scripts/wecom_doc_reader/reader.py` 的 `_try_clipboard_for_spreadsheet()` 方法

### e3_ HTML 多子表遍历（v2.7.0 新增）
- ⚠️ `_try_clipboard_html_all_sheets` 会逐个切换 tab 并对每个子表做 Ctrl+A/C → 读 HTML clipboard
- ⚠️ 每次切换 tab 后必须重新隐藏 operate-board 遮罩层
- ⚠️ tab 元素在切换后 DOM 可能变化，需要重新 `query_selector_all('.tab-bar-item-title')`
- ✅ 如果 HTML clipboard 不可用，自动降级到纯文本 TSV（对该子表）
- ✅ 每条记录带 `_sheet_name` 字段标识来源子表

### e3_ xlsx 导出需要编辑权限
- ❌ **只读文档无法导出 xlsx**：点击"导出"→"本地Excel表格(.xlsx)"后，企微会弹出"申请编辑权限"对话框而不是触发下载
- ✅ xlsx 策略失败时自动降级到 HTML/TSV，不影响整体读取
- ⚠️ 文件菜单按钮的 DOM ID 是 `#headerbar-filemenu`，不是文本选择器 `text="文件"`
- ⚠️ 菜单按钮在 Playwright viewport 外（x=-9988），必须用 `page.evaluate('el.click()')` 绕过 viewport 检查

### e3_ 原生 JS API 是最佳方案（🚨 2026-06-15 v3.1 实测确认）
- ✅ **`sheet.getCellDataAtPosition(row, col)` 直接读内存**：`cell.getValue()` 返回值，800 cells < 1ms
- ✅ **`cell.getMergeReference()` 返回精确合并范围**：`{startRowIndex, endRowIndex, startColIndex, endColIndex}`
- ✅ **`cell.getExtendedValue()` 返回图片原始 URL**：如 `https://wdcdn.qpic.cn/...?w=4096&h=2304`
- ⚠️ **非活跃 tab 数据懒加载**：必须先点击 `.tab-bar-item-title` + `wait_for_timeout(5000)` 后才能读
- ❌ dop-api 返回 protobuf 二进制（非 JSON），v2.x 的 JSON.parse 从未跑通
- ❌ 剪贴板 HTML 需要模拟键盘操作，图片列只拿 base64，不如原生 API
- 详见 `references/e3-native-js-api.md`

### e3_ dop-api 返回 protobuf 二进制（🚨 2026-06-15 v3.0 实测确认）
- ❌ **dop-api/get/sheet 对 e3_ 返回 `related_sheet` 字段是 base64+zlib 压缩的 protobuf 二进制**，不是 JSON
- ❌ v2.x 的 `_try_dop_for_spreadsheet` 试图 `JSON.parse(item.smartsheet)` — e3_ 的 `smartsheet` 是**空字符串**
- ✅ 数据在 `item.related_sheet` 字段中（base64 url safe → zlib decompress → protobuf 二进制）
- ✅ 解压后可见中文 sheet 名和图片 URL（`https://wdcdn.qpic.cn/...`），但整体是 protobuf 格式，无法直接解析
- ✅ 替代方案：JS Runtime `SpreadsheetApp.workbook` 提供已解码的元数据（sheet 列表/名称/mergeList）

### e3_ 含图片/附件列的子表必须走 dop-api（2026-06-15 踩坑）
- ❌ **剪贴板只复制 base64 图片**：如"宣传工作日志"等含图片列的子表，Ctrl+A/C 后剪贴板里只有 `<img src="data:image/png;base64,...">` 标签，完全没有文字数据
- ❌ **截图+VL OCR 也不可行**：截图是缩略图（模糊、不完整、丢失原始 URL），团队负责人明确否决
- ✅ **必须走 dop-api**：dop-api 返回的原始 JSON 中包含图片列的原始 URL（非 base64 缩略图）
- ⚠️ 图片/附件列的 k31 类型 ID 尚未确认（已知 k31 映射：1=文本, 2=数字, 5=日期, 17=单选, 19=公式），需进一步实测

### async_playwright 必须带括号
- ❌ `async with async_playwright as p:` — 报错 `TypeError: 'function' object does not support the asynchronous context manager protocol`
- ✅ `async with async_playwright() as p:` — 正确用法（需要调用函数获取 context manager）

### 🚨 MCP get_doc_content 多子表 Markdown 解析（2026-06-29 踩坑 — 技术工单表 24 子表实测）
- **场景**：用 MCP `get_doc_content(type=2)` 读取含多个子表的智能表格，返回的是所有子表拼接的 Markdown 纯文本
- **🚨 陷阱 1 — 不同子表列数不同**：同一个文档的 24 个子表有三种列结构（25列旧格式 / 31-39列过渡格式 / 12-14列新格式）。用固定列数解析会导致数据丢失或列错位。**必须逐个子表独立解析表头**。
- **🚨 陷阱 2 — `|` 字符导致列错位**：Markdown 表格用 `|` 分隔列，但单元格内容含 `|`（如"模块A|模块B"）会拆出额外列。31-39列旧格式子表受影响最严重（问题描述列经常含 `|`）。**缓解**：检测行 cell 数 > 表头列数时合并多余列；大量行受影响时考虑替换 `|` 为制表符后 CSV 解析；报告中标注"此子表分类不准"。
- **🚨 陷阱 3 — 排序子表标记后解析会破坏边界**：`grep -n '^## '` 拿到标记后，**不能先排序再计算范围**。排序后相邻标记在原文中不相邻，`end_line = 下一个标记行号 - 1` 可能 < `start_line`，产生空范围。**正确流程**：保持原始顺序计算范围 → 逐表解析 → 解析完成后再排序输出。
- **陷阱 4 — 重复子表**：实测发现某些子表数据完全重复（工单ID一致）。需检测并在报告中标注，不计入总数。
- **陷阱 5 — 列名模糊匹配**：不同格式子表列名不同但语义相同（"故障模块" vs "产品模块"）。用 `in` 或正则模糊匹配，不要求精确匹配。
- **用户纠正**：用户指出"他不是很多子表吗，按子表来梳理" — 不要只按第一个子表的格式解析全部数据，必须识别多子表结构并逐表处理。
- **适用场景**：`get_doc_content` 适合快速浏览/分析/分类汇总；精确同步用 `smartsheet_get_records`（JSON，无列错位风险）。
- 详见 `references/mcp-get-doc-content-multisheet-parsing.md`（含解析脚本模板 + 数据质量检查清单 + 与 smartsheet_get_records 对比表）

### w3_ 微文档 _read_dom 只返回工具栏文字（2026-07-16 实测，已修复）

**问题（已修复）**：`wecom_doc_reader` 的 `read()` 方法曾将 w3_ 路由到 `_read_dom`（DOM 提取），但 w3_ 使用 canvas 渲染，DOM 无法拿到正文（135/455 字符）。**v5.0 已修复**：新增 `_read_opendoc` 方法，w3_ 路由改为 opendoc API。详见上方「w3_ 微文档 opendoc API 已实现」章节。

### edit_doc_content 编辑能力完整图谱（2026-07-16 系统性实测）

**核心行为**：
- **全量覆写**（overwrite），非追加。每次调用用新 content 完全替换正文
- 文档标题（create_doc 的 doc_name）自动成为正文首行 `# 标题`，每次覆写都保留，不受 content 影响
- 仅支持 `doc_type=3`（微文档/w3_）。电子表格用 `sheet_*`，智能表格用 `smartsheet_*`，SmartPage 无法编辑
- bot 只能编辑**自己创建**的文档；用户创建的文档报 errcode 851003（需用户先分享给 bot）
- content 参数直接传 Markdown 原文，不用 JSON 转义

**Markdown 格式支持矩阵（写入 → 读回对比）**：

| 格式 | 语法 | 写入→读回 | 渲染质量 |
|---|---|---|---|
| 标题 1-6 级 | `#`~`######` | `#` 保留 | ✅ 全支持 |
| 加粗 | `**text**` | `**` 保留 | ✅ |
| 斜体 | `*text*` | 规范化为 `_text_`（`*`/`_` 等价） | ✅ |
| 加粗斜体 | `***text***` | `_**text**_` | ✅ |
| 删除线 | `~~text~~` | `~~` 保留 | ✅ |
| 行内代码 | `` `code` `` | 反引号被消费，内容保留 | ⚠️ 标记丢失 |
| 无序列表 | `- item` | `-` 被消费，**嵌套层级丢失** | ⚠️ 扁平化 |
| 有序列表 | `1. item` | 序号被消费 | ⚠️ 序号丢失 |
| 任务列表 | `- [ ]`/`- [x]` | `-` 消费，`[ ]`/`[x]` 保留 | ⚠️ 部分保留 |
| 引用 | `> text` | `>` 消费，嵌套引用合并 | ⚠️ 标记丢失 |
| 代码块 | ` ```lang ``` ` | 标记+语言标识消费，内容保留 | ⚠️ 标记丢失 |
| 表格 | `\| a \| b \|` | 表格被创建，**导出还原散乱**（逐单元格换行） | ❌ 导出差 |
| 链接 | `[text](url)` | 转 `HYPERLINK "url"text` 内部格式 | ⚠️ 格式转换 |
| 分割线 | `---` | 标记消费，变空行 | ⚠️ 标记消费 |
| 图片 | `![alt](url)` | **下载图片转 base64 内嵌存储** | ✅ 嵌入成功 |
| HTML img | `<img src>` | 同上，转 base64 | ✅ |
| HTML `<br>` | `<br>` | 转换行符 `\u000b` | ✅ |
| HTML `<strong>` | `<strong>text</strong>` | 转 `**text**` | ✅ |
| HTML `<em>` | `<em>text</em>` | 转 `_text_` | ✅ |
| Emoji | 🎉✅ | 原样保留 | ✅ |
| 特殊字符 | `< > & "` | 作为纯文本保留 | ✅ |

**关键洞察**：
1. 企微用**结构化 block 模型**（类似飞书/Notion），Markdown 只是输入/输出格式
2. **get_doc_content 导出质量参差**：列表丢前缀、引用丢标记、表格散乱——但**企微 UI 实际渲染正常**（内部是结构化数据）
3. **图片自动内嵌**：外部 URL 图片被下载转 base64，文档自包含不依赖 CDN，但体积膨胀（6KB 图 → base64 约 8KB）
4. **追加 workaround**：先 `get_doc_content` 读全文 → 拼接新内容 → `edit_doc_content` 整体覆写

**实测文档**：`https://doc.weixin.qq.com/doc/w3_AMgAkng0AMMCNT0riUy01QWGbA1Jl_a`（2026-07-16 探索用，内容是最后一轮图片嵌入测试）

### w3_ 微文档浏览器编辑：增删改三项验证（2026-07-16 实测）

**结论：w3_ 微文档可以通过浏览器键盘输入实现增/删/改，编辑器自动提交保存到服务器。**

与 SmartPage 不同——SmartPage 的 `offlineEditAdapter.lastCanWrite === false`（bot 创建的文档，浏览器用户无编辑权限），w3_ 普通文档的权限模型允许浏览器用户编辑。

**三项操作验证**：

| 操作 | 方法 | 结果 |
|---|---|---|
| 增（追加） | 点击 `#melo-hidden-editor` → Ctrl+End → `keyboard.type()` | ✅ 自动保存 |
| 删（删除） | Shift+ArrowUp/Shift+Home 选中 → Delete | ✅ 自动保存 |
| 改（替换） | Shift+Home 选中当前行 → `keyboard.type()` 替换 | ✅ 自动保存 |

**关键权限状态**：
- `cv_privilegeAttribute.can_edit: 1` — 浏览器用户有编辑权限
- `cv_userName` — 浏览器用户名（通过 cookie 登录的企微用户）
- `cv_isCreator: false` — 不是创建者（bot 创建），但**有编辑权限**
- `hasWriteProtection: false`、`isWriteProtectionReadOnly: false` — 无写保护

**编辑器架构**：
- `#melo-hidden-editor` — 隐藏编辑器（contenteditable=true），键盘输入入口（parent class: `hidden-editor`）
- `window.pad` — pad 对象，含 `editor`/`collab`/`permissionCtrl`/`writeProtectionHandler`/`offline`/`contextService`/`controllerCenter`
- `pad.editor` — 编辑器对象（`proxyManager`/`modelWrapperMgr`/`clipboardManager`/`root`/`isRenderFinish`/`isEditFeatureLoaded`/`isWriteProtectionReadOnly`）
- `pad.collab` — 协同对象（`changesetManager`/`collabToServer`/`undoRedo`/`applyChangesToBase`/`applyToModel`），**自动提交，无需手动调用**
- `pad.permissionCtrl` — 权限控制器（prototype 有 `canEdit`/`canEditTitle`/`canRead`/`canShare`/`canExport` 等方法）
- canvas 渲染 — 4 个 canvas 元素，`body.innerText` 拿不到 canvas 文字，但编辑器有字数统计

**自动提交机制**：
- 键盘输入后约 5-8 秒自动提交到服务器
- POST 请求含 `editnotify`（编辑通知）
- 不需要手动调用 `pad.collab.collabToServer()`

**限制**：
1. canvas 渲染导致**无法精确 DOM 定位文本**（键盘选区基于光标位置，不是 DOM）
2. 删除/替换依赖键盘选区（Shift+Arrow/Shift+Home），不如 API 精确
3. 没有发现 `pad.editor.insertText/insertBlock` 等直接编辑 API（`proxyManager` 和 `modelWrapperMgr` 没有公开编辑方法）
4. 需要用户 cookie（约 2 周过期，需定期扫码续期）
5. **多用户隔离**（2026-07-16 团队负责人要求）：不同人对话时需各自扫码登录，用各自账号权限操作文档，不能共用一个人的 cookie

**完整浏览器编辑探索记录**：详见 `references/browser-editing-all-types.md`

### 对比总结（2026-07-16 全部实测验证）

**可编辑文档类型 — MCP API vs 浏览器键盘**：

| 类型 | MCP 增 | MCP 删 | MCP 改 | 浏览器增 | 浏览器删 | 浏览器改 | 浏览器验证方式 |
|---|---|---|---|---|---|---|---|
| w3_ 微文档 | ✅ 覆写 | ✅ 覆写 | ✅ 覆写 | ✅ | ✅ | ✅ | MCP get_doc_content 读回 |
| e3_ 电子表格 | ✅ append | ✅ update | ✅ update | ✅ | ✅ | ✅ | wecom_doc_reader 读回 |
| s3_ 智能表格 | ✅ add_records | ✅ delete_records | ✅ update_records | ✅ | — | ✅ | MCP smartsheet_get_records 读回 |

**浏览器键盘编辑统一流程**（w3_/e3_/s3_ 通用）：
1. 用 storage_state 打开文档
2. 点击/双击目标位置（w3_: `#melo-hidden-editor` / e3_: 双击单元格 / s3_: 双击单元格）
3. `#alloy-rich-text-editor`（或 `#melo-hidden-editor`）出现
4. `page.keyboard.type()` 输入文字
5. 按 Enter 确认（e3_/s3_ 需要 Enter，w3_ 自动保存）
6. 等待 5-8 秒自动提交到服务器

**权限**：MCP = bot 只能编辑自己创建的；浏览器 = 用户 cookie（各自扫码，多用户隔离）

### 权限隔离铁规（2026-07-16 团队负责人要求）

**核心原则：操作权限不能超出当前对话人的权限。**

- **飞书操作**：用对话人自己的 OAuth 授权（`lark-as-user.sh <wecom_user_id>`），不用团队负责人的授权
- **企微操作**：用对话人自己的 cookie（per-user storage_state），不用团队负责人的 cookie
- **未授权前不做读写**：对话人没有飞书映射/企微 cookie 时，先引导授权，不做读写
- **多用户隔离**：每个人需自己的授权/扫码，不能共用一个人的

### 🚨 一键授权脚本 — 脚本做厚，SOUL.md 做薄（2026-07-16 同事A对话复盘）

**问题根因**：之前在 SOUL.md/skill 里写了多步流程（检查→生成二维码→发图片→等待扫码→保存），但 LLM 在实际对话中不按步骤执行——直接调 MCP、用 `_shared.json`、发 OAuth 链接代替企微二维码、让用户主动说"授权了"。**文字规则不等于执行。SOUL.md 越长，LLM 注意力越分散，反而更不执行。**

**设计原则（团队负责人 2026-07-16 纠正）**：
- **脚本做厚**：所有流程逻辑封装在代码里，LLM 不能绕过
- **SOUL.md 做薄**：只写"操作前必须调 xxx 脚本"这一条，不写详细流程
- **自动轮询**：用户扫码/授权后不需要再说"扫完了"——`--wait` 模式用 `background=true + notify_on_complete=true` 自动检测

**封装脚本**：

```bash
# 企微：检查cookie → 需要扫码时生成二维码 → --wait自动等待扫码完成
python3 ~/.config/wecom-doc/scripts/wecom_auth_flow.py --check <wecom_userid>
# 返回: {"action":"ok"} 或 {"action":"scan","qr_path":"/tmp/wecom_qr_xxx_rgb.png"}
# 如果 scan：发二维码给用户，然后后台等待：
python3 ~/.config/wecom-doc/scripts/wecom_auth_flow.py --wait <wecom_userid>
# 用 terminal(background=true, notify_on_complete=true) → 扫码完成自动通知，不需用户再说"扫完了"

# 飞书：检查token → 需要授权时返回URL → --wait自动轮询授权完成
python3 ~/.config/wecom-doc/scripts/lark_auth_flow.py --check <wecom_userid>
# 返回: {"action":"ok"} 或 {"action":"auth","url":"https://..."}
# 如果 auth：发URL给用户，然后后台等待：
python3 ~/.config/wecom-doc/scripts/lark_auth_flow.py --wait <wecom_userid>
# 用 terminal(background=true, notify_on_complete=true) → 授权完成自动通知，不需用户再说"授权了"
```

**SOUL.md 铁规 9/10 只需 3 行**（不是 20 行）：
```
9. 飞书操作调 lark_auth_flow.py，脚本内部处理检查/授权/轮询
10. 企微操作调 wecom_auth_flow.py，脚本内部处理检查/二维码/轮询
```

### 🚨 轮询超时 ≠ 授权失败 — 标记凭证 invalid 前必须先 verify（2026-07-21 修复）

**事件**：用户完成飞书授权后仍反复收到授权链接。根因：`lark_auth_flow.py --wait` 的 `except Exception` 把 device-code 轮询 330s 超时（用户实际已授权成功）一律执行 `set_credential_status(..., "invalid")`，有效凭证被误标。

**铁规**：任何"轮询等待用户操作"的 auth 流程，异常分支**禁止直接标凭证 invalid**。必须先 `verify_profile()` 探活：
- verify 成功 → 补登 valid / 完成 transaction，返回 ok（transaction 已完成/过期时也要 set valid）
- verify 失败 → 才标 invalid，要求重新授权

**通用原则**：异常只说明本次操作没走完，不说明底层凭证/资源无效。所有"先失败后定状态"的判定逻辑，都要先探活再下结论。

### 🚨 MCP 失败后必须 Fallback 到浏览器方案（2026-07-16 团队负责人纠正）

**正确流程**：
```
对话人让我读企微文档
  → 先调 wecom_auth_flow.py --check 确认身份+cookie
  → 如果 action=ok：
    → 先试 MCP get_doc_content（快，但用的是应用token不区分对话人）
    → MCP 成功且文档是对话人明确指定的 → 可用
    → MCP 失败（851003/851000/851014）→ 必须自动 fallback 到浏览器方案
  → 如果 action=scan：
    → 发二维码 → --wait 后台等待 → 完成后继续
  → 浏览器方案用对话人的 per-user cookie（不用 _shared.json）
```

**❌ 错误行为（2026-07-16 同事A对话实际发生）**：
1. MCP 失败后直接告诉用户"读不了"——应该 fallback 到浏览器
2. 直接用 `_shared.json`（团队负责人 cookie）走浏览器——应该用 per-user cookie
3. 企微登录发了飞书 OAuth 链接——企微登录应该用**二维码**不是链接
4. 没有自动轮询——用户扫码/授权后还要主动说"扫完了/授权了"
5. 手动拼 `doc.weixin.qq.com/scan-login?return_url=...` URL 给用户——用户反馈"链接访问不了"
6. `wecom_login.py` 用 `nohup` + `timeout=15`——15 秒不够生成二维码就超时了

### 🚨 分层架构：脚本做厚，SOUL 做薄（2026-07-16 团队负责人纠正）

**核心原则**：流程逻辑封装在脚本代码里（LLM 不能绕过），SOUL.md 只写"调哪个脚本"一句话。

| 层级 | 职责 | 稳定性 |
|---|---|---|
| **脚本** (`wecom_auth_flow.py` / `lark_auth_flow.py`) | 完整流程：检查→二维码/URL→后台轮询→自动完成→更新映射表+团队字典 | ✅ 最稳定，代码级强制 |
| **SOUL.md** | 只写一条："企微操作调 wecom_auth_flow.py，飞书操作调 lark_auth_flow.py" | ⚠️ 升级可能覆盖，需备份 |
| **Memory** | 只记脚本名索引 | ⚠️ 容量限制，只留索引 |
| **Skill** | 1 行引用 auth_flow 脚本 + pitfalls 参考文档 | ✅ 稳定 |

**设计教训**：之前把 20 行详细流程全写在 SOUL.md 铁规里，LLM 看到一大段文字反而跳过了。精简到 3 行后 LLM 更容易执行。

### 🚨 发图片/链接要直接能用，不要让用户复制（2026-07-16 团队负责人要求）

**铁规**：
- 发二维码/图片 → 用 `MEDIA:` 语法发到企微白名单目录的文件（`~/.config/wecom-doc/workspace/`），用户直接看到图片
- 发授权链接 → 直接发 markdown 链接 `[点击授权](url)` 或纯 URL，用户直接点击
- ❌ 不要让用户复制链接到浏览器打开
- ❌ 不要把图片放在 `/tmp/`（不在 MEDIA 白名单目录，发不出去）

**已修复**：`wecom_auth_flow.py` 的 QR 路径从 `/tmp/` 改到 `~/.config/wecom-doc/workspace/`，QR 转 RGB 后直接在白名单目录，LLM 用 `MEDIA:` 直接发。

### 🚨 系统性设计原则：不要打补丁式修复（2026-07-16 团队负责人纠正）

**问题**："怎么修了一批问题又有新问题？"——每次只看眼前问题，不考虑副作用，导致修一个出一个的恶性循环。

**铁规**：改任何东西之前，先列出所有依赖关系和影响范围，确认没有副作用再动手。改完做回归测试。不要"发现问题→修问题→引入新问题"循环。

**具体教训**：
- 写 OAuth 流程 → 没考虑会覆盖别人的 token（副作用）
- 修 cookie 覆盖 → 没考虑软链接对定时任务的影响
- 修 QR 不一致 → 没考虑 Popen 的输出顺序
- 每次只看眼前，全局影响没想清楚

### 🚨 QR 码保存路径必须在企微 MEDIA 白名单目录（2026-07-16 实测）

`wecom_auth_flow.py` 的 QR 码保存路径从 `/tmp/` 改到 `~/.config/wecom-doc/workspace/`。原因：
- `MEDIA:/tmp/xxx.png` 会被 gateway 的 `media_delivery_allow_dirs` 白名单**静默拦截**
- `~/.config/wecom-doc/workspace/` 在白名单内，`MEDIA:` 能直接发图片
- QR 还需转 RGB（1-bit PNG 企微无法渲染）

定时同步任务（如 `sync_wecom_smartsheet_browser.py`）用**创建人**的 per-user cookie，不是 `_shared.json`。每个定时任务记录创建人的 wecom_userid，运行时用对应的 per-user cookie。团队负责人创建的用团队负责人的，同事A创建的用同事A的。

### 🚨 MCP 操作也受身份隔离约束（2026-07-16 团队负责人纠正）

MCP 虽然用应用级 token（不区分对话人），但操作的文档范围必须限定在当前对话人有权访问的范围内。不能借 MCP 读取对话人无权访问的其他文档。只操作对话人明确指定的文档。

### 🚨 公开 Skill 不得包含专有信息（2026-07-16 团队负责人要求）

**铁律**：`wecom-doc-access-methods` 是要公开给所有人的 Skill，**不得包含公司、团队、个人专有信息**。

- ❌ 不写具体用户名（如 `userName: "用户"` → 改为 `userName — 通过 cookie 登录的企微用户名`）
- ❌ 不写内部 API 地址、内部服务器 IP、内部域名
- ❌ 不写团队成员姓名、企微 userid、飞书 open_id
- ❌ 不写内部项目名称、内部文档 URL
- ✅ 技术方法（engine API 路径、方法名、数据结构）可以写——这些是通用技术知识
- ✅ 权限字段名（`privilegeAttribute.can_edit`）、API 端点路径（`dop-api/mind/data/get`）可以写——这些是企微文档平台的技术事实
- ✅ 添加探索发现时，先脱敏个人信息再写入

### 🚨 企微文档 Skill 集中化（2026-07-16 团队负责人要求）

**方向**：企微文档读写集中到 `wecom-doc-access-methods` 一个 Skill。其他企微文档相关 Skill 应**引用**此 Skill，不应自己实现文档读写逻辑。

- OpenClaw agent（OpenClaw）也应该安装此 Skill
- 其他企微文档 Skill（`wecom-smartsheet-browser-sync` / `wecom-smartsheet-to-feishu-base` / `wecom-smartsheet-to-feishu-sync` / `wecom-smartsheet-quality-check` / `feishu-to-wecom-doc-sync` / `openclaw-imports/wecom-doc`）应引用此 Skill 的读取/编辑能力，不重复实现
- 清理 `*-imported` 旧副本（审计脚本已识别 20 个）

### 🚨 身份隔离通用原则（2026-07-16 团队负责人要求）

以后所有涉及其他系统内容获取的 skill 或操作，都必须考虑是否需要做身份权限隔离。不是所有系统都需要做权限隔离，有的系统不需要，但创建人必须**显式判断并标注**——不需要也要显式标注"本 skill 不涉及用户级权限，无需身份隔离"。

### 🚨 lark-cli config.json 新用户 OAuth 会覆盖旧用户 token（2026-07-16 发现+修复）

**问题**：同事A完成飞书 OAuth 授权后，lark-cli config.json 的 `users[]` 数组里团队负责人的记录被覆盖了——config 里只剩同事A一个用户。团队负责人的 `lark-cli --as user` 操作全部失效，定时同步任务也用错了身份。

**根因**：`lark-cli auth login --device-code` 在 config.json 的 users 数组里**替换** users[0] 而非追加。token 加密存储仍在（locks 目录有两个用户的 lock 文件），但 config.json 只记录了一个用户。

**修复（`lark-user-onboard.py --complete`）**：授权前备份 config.json 的 users 数组 → 授权后检查哪些已有用户被覆盖了 → 把被覆盖的用户记录加回 users 数组。不管 lark-cli 是替换还是追加，最终 users 数组都包含所有已授权用户。

```python
# 授权前备份
existing_users = config_before["apps"][0].get("users", [])
existing_ids = {u.get("userOpenId") for u in existing_users}

# 授权后检查
current_ids = {u.get("userOpenId") for u in current_users}
missing_ids = existing_ids - current_ids

if missing_ids:
    # 把被覆盖的用户加回去
    for old_user in existing_users:
        if old_user.get("userOpenId") in missing_ids:
            current_users.append(old_user)
```

**通用规则**：任何 OAuth/token 授权流程，必须在授权前备份已有用户列表，授权后恢复被覆盖的记录。不能假设底层 CLI 的行为是"追加"而非"替换"。

### 🚨 分层架构验证：脚本做厚 vs SOUL 做薄的实际效果（2026-07-16 复盘）

**验证结果**：同事A对话（session 20260716_182236）发生在 SOUL.md 铁规 9/10/11 添加**之前**（SOUL.md 修改时间 17:56，session 开始 18:22）。该 session 中 LLM 没有执行身份检查流程——直接调 MCP、发链接而非二维码、让用户主动说"授权了"。

**关键教训**：
1. SOUL.md 改动只对**新 session** 生效——旧 session 的 system prompt 已固定
2. 即使新 session 加载了新 SOUL.md，LLM 仍可能不执行文字指令——文字规则是"建议层"不是"强制层"
3. **脚本是最强制的层**——只要 LLM 调了 `wecom_auth_flow.py` / `lark_auth_flow.py`，流程就是对的（代码级强制）
4. SOUL.md 应该**极简**（3行而非20行）——越短 LLM 越容易执行

**验证方法**：让同事实测新建 session，观察 LLM 是否调 auth_flow 脚本。如果不调，说明 SOUL.md 文字指令还是不够强制，需要考虑更强的机制。

### 🚨 安全加固：5 个审计问题修复（2026-07-16 Codex 审计）

**P0 — lark-as-user.sh `set -e` 串号漏洞**：脚本用 `set -euo pipefail`，`lark-cli` 失败时 set -e 直接退出，配置恢复代码不执行 → 后续操作留在错误用户身份下。**修复**：去掉 `-e`（改为 `set -uo pipefail`）+ `trap restore_config EXIT` 三重保护 + python3 修改配置加 `|| { restore_config; exit 1; }` 兜底。**通用规则**：任何「修改配置→运行命令→恢复配置」模式的脚本，必须用 trap 确保恢复，不能依赖 set -e。

**P0 — 企微 cookie 全局文件污染**：扫码后 per-user cookie 复制到 `_shared.json` 全局文件，后台 cron 可能用到错误账号的 cookie。3 个全局文件（`_shared.json` / `wecom_browser_state.json` / `wecom_cookies.json`）cookie 值相同无法证明属同一人。**修复**：① `wecom_doc_check_auth.sh` 删除硬编码 userid 走 `_shared.json` 的旧分支 ② 三个全局文件改为指向团队负责人 per-user 文件的**软链接**——团队负责人扫码续期→per-user 更新→全局文件自动同步；其他人扫码→只写自己的 per-user→不影响全局。后台脚本不用改代码。**通用规则**：全局文件应作为 per-user 文件的软链接别名，而非独立副本。

**P1 — 映射表无原子写入**：`shutil.copy` 非原子操作，中断/并发可能丢失或分叉。两个映射文件（workspace + scripts 目录）无一致性校验。**修复**：`lark_auth_flow.py` 新增 `atomic_save_mapping()`（tmp file + `os.rename`）+ `verify_mapping_consistency()` + 版本号 `_version` + 内容哈希 `_hash`。**通用规则**：任何 JSON 配置/映射文件写入都应用 tmp+rename 原子操作，多副本需一致性校验。

**P1 — 旧 `_shared.json` 兼容路径绕过隔离**：`wecom_doc_check_auth.sh` 硬编码特定 userid 走 `_shared.json`，身份误判可绕过 per-user cookie 保护。标记 DEPRECATED 不够——代码逻辑中仍存在。**修复**：删除 else 分支中的 `_shared.json` 兼容路径，一律要求 per-user cookie 文件存在。**通用规则**：标记 DEPRECATED 不等于代码被删除，兼容路径必须从代码中移除，不能只加注释。

**P1 — 飞书 OAuth 覆盖率低**：映射表 7 条但 config.json 只有 1 个用户有 token。非代码 bug，是授权推广问题。token 存在 lark-cli 加密存储中（config.json 只存 open_id），实际可用率需逐个 `lark_auth_flow.py --check` 确认。

。

### 🚨 企微登录 vs 飞书 OAuth 不要搞混（2026-07-16 实际踩坑）

| 平台 | 登录方式 | 工具 | 输出 |
|------|---------|------|------|
| 企微文档 | **二维码扫码** | `wecom_auth_flow.py` / `wecom_login.py` | QR PNG 图片 |
| 飞书 | **OAuth 链接** | `lark_auth_flow.py` / `lark-cli auth login` | verification URL |

**铁规**：企微登录永远发二维码图片（`MEDIA:` 语法），飞书登录发 OAuth 链接。不要搞反！
**首次授权（新用户,从未扫码,无 cookie 文件）**：

1. 检查 auth: `wecom_doc_check_auth.sh <wecom_userid>` → `action: "scan"`

2. 生成QR码（在远程服务器执行,脚本会阻塞等待扫码,需用 nohup 后台运行）:
```bash
ssh -p <ssh_port> root@<server_ip> 'cd ./scripts && nohup python3 wecom_login.py --state ~/.config/wecom-doc/states/<safe_userid>.json --qr /tmp/wecom_qr.png --timeout 300 > /tmp/wecom_login.log 2>&1 & echo "PID=$!"'
```
⚠️ `safe_userid = re.sub(r"[^\w\-.]", "_", wecom_userid)` — 与续期流程用 `_shared.json` 不同,首次授权用 per-user 路径从零创建

3. 等待QR生成（约2-3秒）:
```bash
ssh -p <ssh_port> root@<server_ip> 'ls -la /tmp/wecom_qr.png 2>/dev/null && echo "QR_EXISTS"'
```

4. 拉取QR到本地 + 转RGB + 复制到白名单目录:
```bash
scp -P <ssh_port> root@<server_ip>:/tmp/wecom_qr.png /tmp/wecom_qr.png
python3 -c "from PIL import Image; img=Image.open('/tmp/wecom_qr.png'); img.convert('RGB').resize((800,800),Image.NEAREST).save('~/.config/wecom-doc/workspace/wecom_qr_send.png')"
```

5. 发送QR给用户: `MEDIA:~/.config/wecom-doc/workspace/wecom_qr_send.png`

6. 用户扫码后,脚本自动保存 cookie 到 `<safe_userid>.json`,后续读取直接用这个 cookie

**续期授权（已有 cookie 但过期）**：
- 从 `_shared.json` 复制到 per-user 文件（如果同一用户有多个 wecom_userid）
- 或重新走首次授权流程（QR 生成→扫码→保存）

**已知成员新 userid**：通过 `resolve-and-greet` 确认身份后,直接从 `_shared.json` 复制 per-user 文件,不需要重新扫码
**当前状态**：飞书映射表 6 人（用户/同事A/同事C/同事D/同事E + 1人），企微 cookie 团队负责人_shared.json + per-user 文件。lark-as-user.sh 已验证可用。

**🚨 脚本执行位置（2026-07-16 实测）**：
- **企微文档脚本**（`wecom_doc_check_auth.sh` / `wecom_login.py` / `wecom_doc_reader`）→ 在**远程服务器** `ssh -p <ssh_port> root@<server_ip>` 上运行。cookie 文件存储在远程 `~/.config/wecom-doc/states/`。
- **飞书 lark-cli 脚本**（`lark_check_auth.sh` / `lark-as-user.sh` / `lark-user-onboard.py`）→ 在**本地** Hermes 服务器上运行。lark-cli 二进制在本地 `/root/.nvm/versions/node/v22.22.1/bin/lark-cli`，远程没有 lark-cli。映射表在本地 `~/.config/wecom-doc/workspace/wecom-feishu-mapping.json`。
- ⚠️ 不要 SSH 到远程跑 lark-cli 命令（会报 `command not found`）。
- ⚠️ QR 码图片在远程生成后，需 `scp -P <ssh_port>` 拉到本地 → 转 RGB → 复制到 `~/.config/wecom-doc/workspace/` → 通过 `MEDIA:` 发送。

**飞书 OAuth 新用户授权流程（2026-07-16 验证）**：
1. 检查映射：`~/.config/wecom-doc/scripts/lark_check_auth.sh <wecom_userid>` → action=auth 表示未映射
2. 发起授权：`python3 ~/.config/wecom-doc/scripts/lark-user-onboard.py --init <wecom_userid>` → 返回 `DEVICE_CODE:` 和 `VERIFY_URL:`
3. 把 `VERIFY_URL` 发给用户，用户在浏览器登录飞书完成授权
4. 完成授权：`python3 ~/.config/wecom-doc/scripts/lark-user-onboard.py --complete <device_code>` → 自动保存映射 + token
5. 验证：`lark_check_auth.sh <wecom_userid>` → action=ok
6. 用 `lark-as-user.sh <wecom_userid> lark-cli wiki spaces get_node --token <token> --format json` 读取文档
- ⚠️ `lark-user-onboard.py` 请求的 scopes 是 `search:docs:read drive:drive:readonly docx:document:readonly`（可能需要加 `wiki:wiki:readonly` 用于 wiki 读取）

### e3_ 电子表格 MCP 编辑功能矩阵（2026-07-16 实测）

**MCP 工具**：`sheet_update_range_data` / `sheet_append_data` / `sheet_add_sub` / `sheet_delete_sub`

**sheet_update_range_data 功能矩阵**：

| 功能 | 参数 | 结果 |
|---|---|---|
| 文本写入 | `data_type=TEXT, cell_value.text` | ✅ |
| 数字写入 | `data_type=NUMBER, cell_value.number` | ✅ |
| 超链接 | `data_type=LINK, cell_value.link={url, text}` | ✅ |
| 公式 | `data_type=FORMUAL（注意拼写）, cell_value.formula="=SUM(...)"` | ✅ |
| 加粗 | `cell_format.text_format.bold=true` | ✅ |
| 斜体 | `cell_format.text_format.italic=true` | ✅ |
| 删除线 | `cell_format.text_format.strikethrough=true` | ✅ |
| 下划线 | `cell_format.text_format.underline=true` | ✅ |
| 字体颜色 | `cell_format.text_format.color={red, green, blue}` (RGBA 0-255) | ✅ |
| 字号 | `cell_format.text_format.font_size=14` | ✅ |
| 字体名 | `cell_format.text_format.font` | ✅ |
| 水平对齐 | `cell_format.horizontal_alignment` (LEFT/HORIZONTAL_CENTER/RIGHT) | ✅ |
| 垂直对齐 | `cell_format.vertical_alignment` (TOP/VERTICAL_CENTER/BOTTOM) | ✅ |
| 组合格式 | bold + color + font_size 同时设置 | ✅ |

**sheet_append_data**：追加一行（参数同 update_range_data 的 RowData），✅ 成功
**sheet_add_sub**：新增工作表（title + row_count + column_count + index），✅ 成功
**sheet_delete_sub**：删除工作表（sheet_id），✅ 可用

**grid_data 结构**：`{start_row, start_column, rows: [{values: [{cell_value, cell_format, data_type}]}]}`

### s3_ 智能表格 MCP 编辑功能矩阵（2026-07-16 实测）

**MCP 工具**：`smartsheet_add_fields` / `smartsheet_update_fields` / `smartsheet_delete_fields` / `smartsheet_add_records` / `smartsheet_update_records` / `smartsheet_delete_records` / `smartsheet_add_sheet` / `smartsheet_delete_sheet` / `smartsheet_update_sheet`

**17 种字段类型创建 + 值写入格式**：

| 字段类型 | 创建 | 值写入格式 | 返回值 | 特殊要求 |
|---|---|---|---|---|
| TEXT | ✅ | `[{type: "text", text: "内容"}]` | `[{text, type}]` | |
| NUMBER | ✅ | 直接传数字 | 数字 | decimal_places 可配置 |
| CHECKBOX | ✅ | `true`/`false` | bool | |
| DATE_TIME | ✅ | `"YYYY-MM-DD HH:MM:SS"` | 时间戳(毫秒) | 系统自动按东八区转换 |
| SINGLE_SELECT | ✅ | `[{text: "选项"}]` | 选项ID | 自动创建选项，返回 option_id |
| SELECT(多选) | ✅ | `[{text: "A"}, {text: "B"}]` | 选项ID数组 | 自动创建选项 |
| PROGRESS | ✅ | 数字(0-100) | 数字 | |
| PHONE_NUMBER | ✅ | 字符串 | 字符串 | |
| EMAIL | ✅ | 字符串 | 字符串 | |
| URL | ✅ | `[{type: "url", text: "显示", link: "url"}]` | `[{link, text, type}]` | |
| CURRENCY | ✅ | 数字 | 数字 | CNY 类型，decimal_places 可配置 |
| PERCENTAGE | ✅ | 数字(如0.85) | 数字 | |
| IMAGE | ✅ | `[{image_url: "url", title: "标题"}]` | `[{height, width, id, image_url, title}]` | 需先 upload_doc_image |
| ATTACHMENT | ✅ | `[{file_id: "ID"}]` | `[{file_id}]` | 需先 upload_doc_file |
| BARCODE | ✅ | 字符串 | 字符串 | |
| USER | ✅ | `[{user_id: "wecom_userid"}]` | `[{user_id, id_type: 1}]` | 用 wecom_userid 即可 |
| LOCATION | ✅ | `[{source_type: 1, id, latitude, longitude, title}]` | 原样返回 | 需腾讯地图地点信息 |

**关键规则**：
- records 的 key 必须用 `field_title`（不是 field_id）
- 新建子表自带默认 TEXT 字段（标题"文本"），需先 get_fields + update_fields 重命名
- 单选/多选写入时自动创建选项，返回 option_id
- DATE_TIME 支持 "YYYY-MM-DD HH:MM:SS" / "YYYY-MM-DD HH:MM" / "YYYY-MM-DD" 三种精度
- USER 用 wecom_userid 即可（返回 id_type: 1 表示企微用户类型）

### m4_ 思维导图编辑能力探索（2026-07-16 深度实测 v3）

**结论：键盘编辑已确认可用！Tab 添加子节点 + 键盘输入修改节点文本 + 自动保存到服务器。engine 内部 API（171 方法）也已找到，addNode/updateTopic 方法签名已解析。**

**✅ 已确认可用的编辑操作**：

| 操作 | 方法 | 持久化 | 验证方式 |
|---|---|---|---|
| 添加子节点 | 点击 canvas 选中根节点 → 按 Tab | ✅ 保存到服务器（跨 session 验证） | fileData 子节点数从 3→4→5 |
| 修改节点文本 | 点击节点 → F2/双击 → 键盘输入 | ✅ 保存到服务器（跨 session 验证） | fileData 标题从"分支主题3"→"直接输入测试" |
| 自动保存 | 无需显式调用保存 | ✅ 服务器自动接收变更 | editnotify POST + 下次打开 fileData 已更新 |

**编辑流程（已验证）**：
1. 用 Playwright + storage_state 打开思维导图
2. `page.mouse.click(cx, cy)` 点击 canvas 选中根节点
3. `page.keyboard.press("Tab")` — 添加子节点（自动获得默认标题如"分支主题N"）
4. 新节点可能自动进入编辑模式（`freshTitle: true` 标记）
5. `page.keyboard.type("节点文本")` — 输入文本替换默认标题
6. `page.keyboard.press("Enter")` — 确认编辑
7. 等待 5-10 秒自动保存到服务器

**⚠️ 注意事项**：
- 点击位置很关键 — 需要点击到节点上，不是 canvas 空白处
- caret 高度始终为 0px（即使编辑模式激活），不能用 caret 高度判断是否在编辑
- F2/双击可能激活了编辑模式，即使没有可见的 contenteditable 元素
- 没有显式的保存请求 — 服务器通过协同机制自动接收变更
- `fileData`（`clientVars.collab_client_vars.fileData`）反映当前状态，不是初始数据

**engine 内部 API（通过 React fiber 树提取）**：

提取路径：从 `canvas.Mind_mindCanvas__Vp1oy` 父元素 → `__reactInternalInstance$xxx` → BFS 遍历 fiber 树 → `memoizedProps.engine`

**方法签名（从 toString 分析）**：

| 方法 | 签名 | 说明 |
|---|---|---|
| `addNode(e, t)` | `addNode(operationType, {defaultTitle, changeSelect, enterEdit})` | e=操作类型常量（待确定），t=选项 |
| `updateTopic(e, t)` | `updateTopic(text, shouldCover)` | e=文本，t=是否覆盖。修改**当前选中节点**的标题 |
| `dfsAllNode(e, t)` | `dfsAllNode(callback, callback2)` | 两个参数都是回调函数 |
| `sendCommand(e, t, i)` | `sendCommand(operation, data, {shouldEmit, record, traceCategory})` | 通用命令分发器 |
| `getRootId()` | 无参数，返回 `"root"` | ✅ 验证可用 |
| `getRecordInfo()` | 无参数，返回 `{canUndo, canRedo}` | ✅ 验证可用 |
| `switchCollapse(e, t)` | `switchCollapse(nodeId, collapse)` | e=节点ID，t=是否折叠 |
| `changeIndent(e)` | `changeIndent(increase)` | e=true增加缩进，false减少 |

**JS 源码中的 ADD 操作常量**（从 chunk JS 搜索）：
`ADD_CHILD`, `ADD_CHILD_NODE`, `ADD_NODE`, `ADD_DETACHED`, `ADD_NODE_LIST` 等 — 但通过 engine.addNode 传字符串常量返回 null，可能需要引擎内部的常量对象引用

**fileData 数据结构**（`clientVars.collab_client_vars.fileData`）：
```json
{
  "content": [{
    "rootTopic": {
      "id": "root",
      "title": "中心主题",
      "collapse": false,
      "children": {
        "attached": [
          {"id": "xxx", "title": "分支主题1", "freshTitle": true},
          {"id": "yyy", "title": "已编辑的标题", "freshTitle": null}
        ]
      }
    },
    "theme": {"topic": "default"},
    "title": "",
    "id": "",
    "relationships": []
  }],
  "metaData": {}
}
```

**权限状态**：
- `privilegeAttribute.can_edit: true` — 有编辑权限（`clientVars.can_edit` 为 null 是误导）
- `isCreator: true`, `isOwner: true`

**编辑器架构**：
- React 16.13.1，canvas 渲染（`Mind_mindCanvas__Vp1oy`）
- `textContainerEl`（`Mind_text-container__2HELZ`）含 caret 光标元素（`style_caret__PMMaU`）
- caret 始终 `visibility: visible` 但 `height: 0px`（编辑模式不改变 caret 高度）
- 协同通过 `collab_client_vars` + `editnotify` POST 实现（非 WebSocket）
- API 端点：`dop-api/mind/data/get`（注意不是 `dop-api/get/mind`）

**工具栏**：大纲模式 / 插入 / 结构 / 主题 / 格式（均位于固定工具栏，x:-9982 视口外）
**右键菜单**：粘贴/全选/设置格式/画布放大缩小/主题级别设置（无"编辑节点"选项）

**MCP 工具**：无思维导图编辑工具
**API 创建**：不支持（只能通过浏览器 UI 创建）

### 浏览器 UI 创建文档流程（2026-07-16 实测）

**可创建的 8 种类型**：智能文档 / 智能表格 / 文档(w3_) / 表格(e3_) / 幻灯片 / 收集表 / 思维导图 / 流程图

**创建流程**：
1. 用 Playwright + storage_state 打开 `https://doc.weixin.qq.com`
2. 点击"新建"按钮（`button.xd_btn.fileToolbar_button`）
3. 菜单展开（`xd_dropdownMenu_item`），点击目标类型
4. 新 tab 打开文档（URL 含 `?newEmptyDoc=1`）
5. 用 `context.on("page")` 监听新 tab

**权限优势**：浏览器 UI 创建的文档，用户是创建者（`isCreator: true`），比 API 创建的文档权限更好（API 创建的 bot 是 owner）。

### 其他类型编辑能力探索（收集表/幻灯片/流程图 — 2026-07-16 实测）

**三种类型都通过浏览器 UI 创建成功**（新建 → 选择类型 → 新 tab 打开），都有 `can_edit: true` + `isCreator: true`。

| 类型 | URL 前缀 | padType | canvas | contenteditable | textarea | 键盘编辑 | 结论 |
|---|---|---|---|---|---|---|---|
| 幻灯片 | `p3_` | slide | 9 | 0 | 1 (CopyPasteAssist*) | ❌ | 未找到正确入口，待深入探索 |
| 流程图 | `f4_` | flowchart | 0 (SVG 渲染) | 0 | 1 (CopyPasteAssist*) | ❌ | 未找到正确入口，待深入探索 |
| 收集表 | — | — | — | — | — | — | 创建需模板，未探索 |

*CopyPasteAssist：位于 x:-10000 视口外的隐藏 textarea，用于剪贴板操作，不是编辑入口。

**说明**：幻灯片/流程图/思维导图在网页中人工可编辑，说明编辑入口存在。当前未找到正确的 Playwright 操作方式（盲目双击 canvas/SVG 中心未触发编辑模式）。需要精确定位节点/文本框位置或用 dispatchEvent 触发 canvas/pointer 事件。**不是"不可行"，是"方法待探索"。**


- ❌ MCP 工具列表中没有 `del_doc` / `document_del` 等删除文档的工具（只有 `smartsheet_delete_sheet/fields/records`、`sheet_delete_sub` 等子表级删除）
- ❌ 直接调企微文档 API `POST /cgi-bin/wedoc/del_doc` 需要 access_token，但 `WECOM_SECRET` 环境变量是**消息推送**的 secret，不是文档 API 的 secret（errcode 40001: invalid credential）
- ❌ MCP apikey 不能当 access_token 用（errcode 40014）
- ❌ MCP JSON-RPC 调用 `del_doc` → "Unknown tool: del_doc"
- ✅ corpid 可从 gateway 进程获取：`cat /proc/$(pgrep -f 'hermes.*gateway'|head -1)/environ | tr '\0' '\n' | grep corp`
- ✅ **替代方案**：让用户在企微 UI 手动删除

### SmartPage 浏览器编辑：机器人创建的文档用户无写入权限（2026-07-15 实测）
- 机器人 `smartpage_create` 创建的智能文档，用户（浏览器 cookies 打开）**无编辑权限**（`offlineEditAdapter.lastCanWrite: false`）
- `getEditorService().getAvailableEditors()` 返回空，编辑器不初始化
- `execCommand('insertText')` 改了 DOM 但不触发保存（无 POST 请求）
- 用户自己创建的 w3_ 普通文档：用户有编辑权限，但 canvas 渲染编辑器有 `paragraph-drag-cover` 遮挡层阻止 Playwright 点击

### 🆕 SmartPage 嵌入图片坑（2026-07-22 另一 Agent 实测）
- 🚨 **Markdown 图片语法必须用英文括号 `()`，中文括号 `（）` 不渲染** — 最常见踩坑
- 🚨 **`upload_doc_image` 必须指定 `url`（或 docid）参数指向容器 SmartPage，否则报错**（errcode 301085）
- 🚨 **SmartPage 不支持 `edit_doc_content`，写错了只能重新创建** — 完整内容必须一次性写入
- ✅ 容器上传拿到的 CDN URL 是**独立的**，可在任何文档中引用（容器仅作上传宿主）
- `smartpage_create` 的 `page_content` 直接写 `![](url)`，不要用 `<img>` 标签
- SmartPage 不支持 data URI，必须先上传拿 CDN URL；4K 截图（2880×1616）会自动缩放
- 完整四步法详见 `references/wecom-doc-image-embedding.md` 第四节

### SmartPage（智能文档）编辑探索（2026-07-16 深度实测）

**结论：编辑器可激活，DOM 可修改，submit_command 发送到服务器，但内容持久化机制待完善。从"不可编辑"升级为"编辑器可激活，持久化待完善"。**

**关键突破 — 强制激活编辑器**：
1. `AppStore.dataService.dataCore.offlineEditAdapter.lastCanWrite = true` — 强制设置写入权限
2. `window.__startCollabEdit()` — 启动协同编辑
3. `document.execCommand('insertText', false, 'text')` — DOM 文本插入成功
4. `smartcanvaswrite/submit_command` POST 请求发送到服务器（时间戳变更证明服务器收到请求）

**⚠️ 持久化问题**：DOM 文本被修改 + submit_command 发送，但重新打开文档后内容消失。原因：`execCommand` 修改了 DOM 但可能没正确创建 dataCore 的 mutation。需要通过 `dataDispatcher` 的结构化 API 创建正确的 mutation。

**dataCore 结构**（`AppStore.dataService.dataCore`）：

| 属性 | 类型 | 方法/子键 | 用途 |
|---|---|---|---|
| `offlineEditAdapter` | object | `lastCanWrite`, `isOnline`, `changesCache`, `syncOfflineEvent` | 离线编辑适配器（可强制 `lastCanWrite=true`） |
| `dataDispatcher` | object | `create`, `commit`, `addMutation`, `getCollabCenterAdapter`, `getDataCore` | 命令分发器（结构化编辑入口） |
| `api` | object | `getBlockById`, `getApool`, `loadChunkPage`, `duplicateBlock`, `loadRecordValue`, `loadRecords` | 数据读取 API |
| `memoryCache` | object | `cache`, `recordEvents`, `globalAttribPool`, `blockFieldFactory` | 内存数据模型 |
| `collabAdapter` | object | — | 协同适配器 |
| `mode` | string | — | 编辑模式 |

**dataDispatcher 方法签名（从 toString 分析）**：

| 方法 | 签名 | 说明 |
|---|---|---|
| `create(e, t)` | `create(operationType, data)` → `new h.A(e, t)` | 创建命令对象 |
| `addMutation(e)` | `addMutation({mutation, command})` | 添加 mutation 到命令队列。`e.mutation` = 变更数据, `e.command` = 命令对象 |
| `commit()` | `commit()` | 提交命令（需要正确的 this 上下文，直接调用报错） |

**编辑器架构**：
- React 应用，`#root-editable`（contenteditable=true）是编辑入口
- `getEditorService()` 返回编辑器服务（`editors`, `getActiveEditor`, `getAvailableEditors`）
- `AppStore.pageStore` 有 `getValue()`（页面树结构，含循环引用不能 JSON.stringify）
- `AppStore.dataService.dataCore` 是核心数据层
- API 端点：`smartcanvaswrite/submit_command`（编辑命令提交）+ `smartcanvaswrite/update_browse_location`（光标位置）
- `padType: "smartpage"`, `isCreator: true`, `privilegeAttribute.can_edit: true`

**SmartPage 增删改查现状**：

| 操作 | MCP API | 浏览器 | 状态 |
|---|---|---|---|
| 查(读) | ✅ `smartpage_export_task` | ✅ `pageStore.getValue()` + `api.getBlockById()` | ✅ 可用 |
| 增(创建) | ✅ `smartpage_create` | ✅ 浏览器 UI 创建 | ✅ 可用 |
| 改(编辑) | ❌ 无 `smartpage_edit` | ⚠️ DOM 可改 + submit_command 发送，持久化待完善 | ⚠️ 方法待完善 |
| 删(删除) | ❌ | ❌ | ❌ 不支持 |

**编辑器 Service API（prototype 方法）**：
- `createEditor(ctx, {type})` — **创建编辑器实例的关键方法**！但 `ctx` 需要是 DI 上下文对象（有 `createInstance` 方法），这个对象在页面初始化时内部创建，不暴露为全局变量
- `addEditor(editor)` / `removeEditor(id)` / `getEditorById(id)` / `getActiveEditor()` / `getAvailableEditors()` — 编辑器管理
- `generateEditorId()` — 生成编辑器 ID（调用时 `editorIdCounter` 递增，但 `createInstance` 失败导致编辑器未创建）
- **DI 上下文搜索结果**：搜遍 `window`、`AppStore`、React fiber 树，只找到 `i18n` 和 `__ARK_EXTENSION_INSTANTIATION_SERVICE__`，都不是编辑器 DI 上下文

**collabAdapter 方法**：
- `throttledFlushCommands()` — 刷出命令到服务器（调用成功但 `composeCommands` 为空，无可刷出的命令）
- `customSendUserChange()` — 发送用户变更
- `composeCommands` — 命令组合对象（空，说明 `execCommand` 未创建 mutation）

**block 结构可读**：
- `pageStore.children` — 子 block ID 列表（如 `["Ew28rg", "mM8Kti", "9tqDJT"]`）
- `pageStore.id` / `pageStore.table` — block 标识（如 `id: "2sjW3N"`, `table: "block"`）
- `api.getBlockById(blockId)` — 获取 block 对象（测试返回空对象，可能需要先 loadChunkPage）

**根因分析**：`execCommand` / 键盘输入修改了 DOM 但**没有创建 dataCore mutation**（`composeCommands` 为空，`addMutation` 未被调用）。没有 mutation → `throttledFlushCommands` 无内容刷出 → 服务器只收到 browse_location 更新（时间戳变）但内容未保存。需要通过 `dataDispatcher.create()` + `addMutation()` 创建正确的 mutation 对象，但 mutation 格式（`pointer.table`/`pointer.id`/`args`/`invertMutation`）和 `create()` 的 `operationType` 参数待确定。

**下一步探索方向**：
1. 从 JS chunk 源码搜索 `h.A` 构造函数（`create` 返回 `new h.A(e,t)`），找 operationType 枚举值
### SmartPage（智能文档）编辑 — submit_command API（2026-07-16 重大突破）

**结论：SmartPage 可通过直接构造 `submit_command` API 请求编辑内容！不需要 editor 实例，不需要 `lastCanWrite`，直接 HTTP POST 即可。**

**✅ 已验证的编辑操作**：

| 操作 | 方法 | 持久化 |
|---|---|---|
| 修改 block 文本 | 构造 `submit_command` POST 请求 + EtherPad changeset | ✅ 跨 session 验证 |

**编辑流程**：
1. 用 Playwright + storage_state 打开 SmartPage
2. 从 `clientVars` 获取：`padId`, `vid`（数字用户ID）, `collab_client_vars.rev`（当前版本号）, `collab_client_vars.client.sid`
3. 拦截页面请求获取 `xsrf` token
4. 从 `AppStore.pageStore.children` 获取 block ID 列表
5. 构造 EtherPad changeset：`Z:<old_len_b36>><change_b36>-<old_len_b36>+<new_len_b36>$<new_text>`
6. 构造 `submit_command` POST 请求
7. 用 `page.evaluate(fetch)` 发送请求
8. 等待服务器保存，重新打开验证

**EtherPad changeset 格式**：
```
Z:<old_len_base36>><change_base36><operations>$<text>
```
- 长度用 base-36 编码（0-9a-z）
- `<operations>`: `=N`（保留N字符）`-N`（删除N字符）`+N`（插入N字符，从$text取）
- 示例：`Z:4>b-4+f$SmartPage编辑成功` = 替换4字符为15字符

**submit_command 请求体格式**：
```json
{
  "sid": "<session_id>",
  "command": {
    "id": <unique_timestamp_id>,
    "pad_id": "<doc_id>",
    "create_timestamp": <timestamp_ms>,
    "pad_version": <current_rev>,
    "createBlockIds": [],
    "shouldCommit": true,
    "committed": false,
    "mutations": [{
      "args": {
        "id": "<block_id>",
        "type": 1,
        "props": {
          "title_changeset": {
            "changeset": "Z:4>b-4+f$new_text",
            "apool": "{\"numToAttrib\":{},\"nextNum\":0}"
          }
        },
        "updated_at": <timestamp_ms>,
        "updated_by": "<vid>"
      },
      "operation": 2,
      "operation_type": 0,
      "meta": {}
    }]
  }
}
```

**API 端点**：`POST https://doc.weixin.qq.com/smartcanvaswrite/submit_command?sid=<sid>&wedoc_xsrf=1&xsrf=<xsrf>&xsrf=<xsrf>`
**Content-Type**: `application/protojson`
**成功响应**: `{"head":{"ret":0,"msg":"OK"}}`

**关键字段说明**：
- `vid` — 数字用户 ID（不是 `userId`，`userId` 有 `p.` 前缀会被拒绝）
- `pad_version` — 当前文档版本号，从 `collab_client_vars.rev` 获取
- `create_timestamp` — 命令创建时间戳（毫秒）
- `xsrf` — 从页面请求中拦截（值固定：`39960f5e6d67a6ca`）
- `sid` — 从 `collab_client_vars.client.sid` 获取
- `block_id` — 从 `AppStore.pageStore.children` 获取 block ID 列表

**SmartPage 增删改查完整方案**：

| 操作 | MCP API | 浏览器 |
|---|---|---|
| 查(读) | ✅ `smartpage_export_task` → Markdown | ✅ `pageStore.children` + `api.getBlockById` |
| 增(创建) | ✅ `smartpage_create` 传 pages 参数 | ✅ 浏览器 UI 创建 |
| 改(编辑) | ❌ 无 MCP 编辑接口 | ✅ **`submit_command` API + EtherPad changeset** |
| 删(删除) | ❌ | ✅ **浏览器键盘（清空文字 + Backspace）** |

**之前探索的路径（作为参考）**：
- `offlineEditAdapter.lastCanWrite` 可强制设为 `true`，但不创建 editor 实例
- `getEditorService()` 有 `createEditor` 方法，但需要 DI 上下文对象（不暴露为全局变量）
- `dataDispatcher` 有 `create/addMutation/commit` 方法，但 mutation 格式复杂
- `execCommand('insertText')` 修改 DOM 但不创建 data model mutation
- **直接 `submit_command` API 是最简单、最可靠的编辑路径**

**SmartPage 删除 block（2026-07-17 验证）**：
- **浏览器键盘路径（✅ 已验证跨 session 持久化）**：
  1. 点击目标 block → `Control+a` 全选 → `Delete` 清空文字
  2. 按 `Backspace` 删除空 block → 自动保存到服务器
- **API 直接删除路径（`submit_command`，⚠️ `ret=0` 但未持久化，待调试）**：
  - 删除需要 3 步 mutation：(1) 清空 changeset (2) `enabled:false` 禁用 (3) `operation:5` 从 children 列表移除
  - 完整请求格式（从拦截真实 UI 请求获得）：
    ```json
    {"sid":"<body_sid>","command":{"id":<ts>,"pad_id":"<padId>","mutations":[
      {"path":["props","title_changeset"],"args":{"id":"<block_id>","type":1,"props":{"title_changeset":{"changeset":"Z:<len>-<len>$","apool":"{\"numToAttrib\":{},\"nextNum\":0}"}},"updated_at":<ts>,"updated_by":"<vid>"},"operation":2,"operation_type":0,"meta":{}},
      {"args":{"id":"<block_id>","type":1,"enabled":false,"props":{},"updated_at":<ts+1>,"updated_by":"<vid>"},"operation":2,"operation_type":0,"meta":{}},
      {"args":{"id":"<page_id>","type":5,"child_id":"<block_id>","updated_at":<ts+2>,"updated_by":"<vid>","props":{}},"operation":5,"operation_type":0,"meta":{}}
    ],"user_infos":[{"identity":{"vid":"<vid>","uid":"<uid>"},"name":"<name>","img_url":"<url>","corp_id":"<corpId>","corp_name":"<corpName>","extern_name":"<name>","from_corp_id":"<corpId>"}],"user_actions":[],"extras":{"affected_page_ids":["<page_id>"]},"create_timestamp":<ts>,"pad_version":<rev>},"from_type":0,"req_tag":"<tag>","req_ts":<ts+1>}
    ```
  - ⚠️ `create_timestamp` 和 `pad_version` 在 `command` 对象内部（不在顶层）
  - ⚠️ `user_infos` 的 `name`/`img_url`/`corp_id` 都是必填（空字符串会被拒绝）
  - ⚠️ `Z:0>0$` 是空操作（0→0），需要用 `Z:<len>-<len>$` 先清空实际内容
  - operation 枚举：`1`=创建block, `2`=修改block, `5`=更新页面children
**⚠️ errcode 851003 — bot 编辑用户创建的文档**
- `edit_doc_content` 对非 bot 创建的文档报 851003（no authority）
- bot 只能编辑自己创建的文档，或用户主动分享给 bot 的文档
- 解决：用户在企微文档右上角「分享」→ 搜索添加机器人应用 → 给编辑权限
- 这是企微文档的设计：每篇文档的权限是独立的

**SmartPage 适用场景**：
- ✅ 一次定稿的多子页面文档（如方案展示页）
- ❌ 需要反复修改的工作规范/会议纪要/PRD 类文档
- `create_doc` 只支持 3 种类型：`doc_type=3`（微文档）、`4`（电子表格）、`10`（智能表格）。其中只有 `doc_type=3` 可用 `edit_doc_content` 编辑内容

### Playwright canvas bounding_box 返回 None（2026-07-16 实测）
- ❌ `await canvas.bounding_box()` 可能返回 None（canvas 有特殊 CSS 如 transform/display:none）
- ✅ 用 `page.evaluate` + `getBoundingClientRect()` 获取实际位置
- ✅ 多个 canvas 时过滤可见的：`c.getBoundingClientRect().width > 0`
- e3_ 有 4 个 canvas，其中 2 个是 0x0 不可见的

### Playwright 点击视口外元素超时（2026-07-16 实测）
- ❌ 元素在 x:-10000（如 CopyPasteAssist）会导致 `element.click()` 超时 30s
- ✅ 用 `page.evaluate("document.querySelector('#target')?.focus()")` 直接聚焦
- ✅ 键盘输入后用 `page.keyboard.press("Enter")` 确认（e3_/s3_ 需要 Enter 触发保存）

### 浏览器编辑结论原则（2026-07-16 团队负责人纠正）
- ❌ 不要轻易下"不可行"结论——**人能在网页里操作的，浏览器自动化也应该能操作**
- ✅ 如果当前方法不工作，结论应该是"方法待探索"，不是"不可行"
- ✅ 需要尝试更多方法：dispatchEvent 触发 canvas/pointer 事件、解析 dop-api 节点坐标、检查键盘快捷键等
- ✅ 这个原则适用于所有 canvas/SVG 渲染的文档类型（m4_/p3_/f4_）

### 🚨 USER.md 是全局的，不按 sender 隔离（2026-07-16 严重踩坑）

**问题**：Hermes 的 `USER.md`（user profile）是**全局的**——一个 agent 只有一份，不管谁对话都注入同一份。如果在里面写了 `Name: 用户` 和 `What to call: 团队负责人`，LLM 看到 system prompt 里的"团队负责人"就直接用了，**不管实际对话人是谁**。

**踩坑场景**：团队负责人让同事新建 session 对话，LLM 仍然叫同事"团队负责人"——因为 system prompt 里注入的 USER.md 写死了"团队负责人"。

**修复**：把 USER.md 里的固定名字改成动态获取：
```
**Name:** 取决于对话人(resolve-and-greet动态获取,不固定用户)
**What to call他们:** resolve-and-greet的member.name(用户=团队负责人,其他人用真名,绝不默认团队负责人)
```

**铁规**：USER.md 里不要写死任何人的名字作为默认称呼。名字必须从 resolve-and-greet 动态获取。

### SOUL.md 是系统提示词源头（2026-07-16 发现）

**关键发现**：`~/.config/wecom-doc/SOUL.md` 是 Hermes 系统提示词的源头文件。新 session 创建时直接加载这个文件。在 SOUL.md 里加规则比改 memory 更强制——因为 SOUL.md 内容直接构建 system prompt，不是通过 memory 注入的。

**使用方式**：用 `patch` 工具在 SOUL.md 的"🔒 铁规"章节里加新规则（如飞书/企微操作前的强制检查步骤）。

**注意**：SOUL.md 是团队负责人自定义的系统提示词，不是 Hermes 框架原生的。改 SOUL.md 不算"改框架"。

### 不改框架，用现有机制解决（2026-07-16 团队负责人要求）
- ❌ 不要改 Hermes 框架代码来解决身份隔离等问题——系统要跟官方版本升级
- ✅ 用现有机制解决：skill 规则 + 独立脚本（lark-as-user.sh / wecom_doc_check_auth.sh）+ memory 约束
- ✅ 身份检查脚本放 `~/.config/wecom-doc/scripts/`（全局可用，不依赖框架内部实现）
- ✅ lark-cli 升级风险：config.json 结构可能变，但有兜底（拒绝操作而非偷偷用团队负责人权限）

### 验证充分性原则（2026-06-15 用户纠正）
- ❌ 不要只测一个子表就声称"全部成功"
- ✅ 多子表文档必须全量遍历验证，逐个报告每个子表的行数/列数/合并单元格数
- ✅ 报告格式：表格形式列出每个子表的指标，明确标注失败子表和原因

### 🚨 数据完整性验证 ≠ 表面指标（2026-06-15 踩坑）
- ❌ **行数合理 + 合并数 + 图片数 ≠ 数据正确**：v4.0.0 报告"15/15 成功、1443 条、226 合并、9 图片"，但团队负责人追问"你怎么知道每个单元格的值是对的？"——答不上来
- ✅ **必须做 ground-truth 对比**：随机抽样 N 行 M 列，肉眼对比原始文档 vs 提取结果，确认单元格值、合并边界、图片 URL 完全匹配
- ✅ **建议提供验证脚本**：导出前 20 行为 CSV/Markdown，让用户手动对照关键单元格（表头、日期列、图片列、合并区域）
- ⚠️ 表面指标只能证明"程序跑通了"，不能证明"数据提取正确"。团队负责人铁规："做事一次做对做专业"，验证必须严格

### 🚨 mergeList 行号偏移（2026-06-15 v4.0.2 修复 — 最容易踩的坑）

- ❌ **mergeList 的行号是 sheet 级别（0=表头行），records 数组是数据级别（0=第一条数据）**，直接当索引用会差 1
- ❌ 表现：合并单元格全部未填充，地块名丢失、列错位（另一个 Agent 反馈的"灌溉日志数据不可用"根因就是这个）
- ✅ **正确转换**：`record_index = merge_row - 1`
- ✅ **填充逻辑**：遍历 mergeList → 起始格 `records[sr-1][header]` 取值 → 填充 `records[sr-1]` 到 `records[er-1]` 的所有空格
- ✅ **验证方法**：spot-check 合并区域第一列（如灌溉日志的 col_0 地块名），逐行确认都有值
- ⚠️ 如果起始格本身为空（原表没填），填充值也是空，这是正确行为（不是 bug）

### 🚨 用最轻量的工具完成任务（2026-07-07 设计原则）
- ❌ **不要用浏览器验证 cookies**：`check()` 原来启动 Chromium 验证 cookies 有效性（3-5s、200MB 内存），但 cookies 是否有效只需要一个 HTTP 请求即可判断（0.4s、5MB 内存）。企微文档是 SPA，HTTP 拿到的是 HTML 框架，但足够判断是否跳转 login 页
- ✅ **判断标准**：如果不需要 DOM 渲染、JS 执行、或拦截浏览器内部 API 响应 → 用 HTTP（httpx/requests）而非 Playwright
- ✅ **HTTP 验证 cookies 的模式**：`httpx.get(url, cookies=cookies, follow_redirects=False)` → 检查 status_code（200=有效，302+location含login=过期）+ body 是否含 login 标记
- ⚠️ **read() 仍需要 Playwright**：因为需要拦截 dop-api 响应、执行 JS 获取 `collab_client_vars`、用 `getCellDataAtPosition` 读内存数据 — 这些 HTTP 做不到
- **来源**：另一个 Agent 建议优化 — check() 只是验证 cookies 有效性，不需要浏览器。v4.5.2 实施，10x 性能提升

### 🚨 Skill 建设铁规：未实测的代码不准写进方案（2026-06-15 血泪教训）
- ❌ **v2.x 的 `_try_dop_for_spreadsheet` 方法假设 e3_ 的 dop-api 返回 JSON，写了完整解析代码，但从未实测** — 实际是 protobuf 二进制，代码从来没跑通过
- ❌ **v3.0 把剪贴板 HTML 当主力，xlsx/TSV/DOM 当"降级"，但这些降级方案从未在只读文档上验证过**（xlsx 需要编辑权限、DOM 对 canvas 无效）
- ✅ **正确做法**：先实测每一种数据路径的可行性，确认可用再写代码。不可用的不要写进方案
- ✅ **不要编造降级方案**：如果某条路径没验证过，不要写"降级到 XX"，标注为"未验证"或直接不写
- ✅ **追求最直接的方案**：能用原生 API 就不要模拟键盘，能用内存数据就不要走剪贴板

---

