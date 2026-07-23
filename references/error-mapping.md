# 错误映射表 — 原始报错 → 人话 → 修复步骤

> 所有路径（MCP / 浏览器 / Cookie）常见错误对照表。AI Agent 遇到以下报错时直接查表。

## 1. MCP 路径错误

| 原始报错 | 人话 | 修复 |
|----------|------|------|
| `errcode 850001` | MCP API Key 无效（缺字符/复制错） | 从企微后台 AI Helper → MCP 配置重新复制完整 key。注意 key 很长（100+ 字符），容易漏 |
| `errcode 851003` | 机器人无权访问此文档 | 在企微里把文档分享给机器人；或用 `w3 create` 新建（机器人自动有权限） |
| `errcode 851014` | MCP 授权已过期 | 重新从企微后台获取 API Key。读取可用浏览器路径替代（无需 MCP） |
| `errcode 301085` | 上传图片缺 `url` 参数 | 加 `--doc-url`（目标文档 URL） |
| `Not Acceptable: Client must accept application/json` | HTTP Accept header 缺失 | 用 `wecom_doc_writer.py` 统一入口（已处理），不要手写 raw HTTP |
| `Invalid request parameters` | MCP 参数格式不对 | 检查参数是否为 JSON 字符串格式。writer 的 auto-wrap 会处理大部分类型，但复杂嵌套需手动构造 |
| `coroutine object was never awaited` | 混用了 async 代码 | skill 脚本全是同步的（`requests` 库）。如果你的代码有 `async`/`await`，检查是否误 copy 了其他库 |

## 2. 浏览器路径错误（Playwright）

| 原始报错 | 人话 | 修复 |
|----------|------|------|
| `Execution context was destroyed` | Cookie 过期或页面刷新 | 重新扫码登录：`python3 scripts/wecom_login.py --state /tmp/state.json --qr /tmp/qr.png` |
| `Timeout 45000ms exceeded` (goto) | 页面加载慢或网络问题 | 增大 timeout 或检查网络。企微文档页面较重，建议 45000ms+ |
| `Timeout 300000ms exceeded` (wecom_login) | 二维码等待超时 | 增大 `--timeout`。二维码有效期约 2 分钟，超时需重新生成 |
| `waiting for locator("canvas")` | 文档页面还没加载完 | 增加 `page.wait_for_timeout()` 等待时间，或用 `wait_for_selector("canvas")` |
| `playwright._impl._errors.Error: Page.goto: net::ERR_*` | 网络不通 | 检查网络连接。企微文档域名 `doc.weixin.qq.com` 需要能访问 |

## 3. Cookie / 状态管理错误

| 原始报错 | 人话 | 修复 |
|----------|------|------|
| `FileNotFoundError: .../wecom_states/xxx.json` | Cookie 文件不存在 | 先运行 `wecom_login.py` 扫码登录 |
| `json.JSONDecodeError` (cookie file) | Cookie 文件损坏 | 删除后重新登录 |
| Cookie 有效但读不到数据 | 登录的账号没有文档权限 | 确认扫码的企微账号能访问目标文档 |
| 多用户 cookie 混乱 | `--user` 参数指定了错误的 user_id | 每个用户独立的 `wecom_states/<user_id>.json` 文件。确认 `--user` 参数与扫码账号一致 |

## 4. SmartPage / 图片错误

| 原始报错 | 人话 | 修复 |
|----------|------|------|
| 图片不渲染 | Markdown 用了中文括号 `（）` | 必须英文括号 `()`：`![](url)` 不是 `![]（url）` |
| `smartpage_create` 返回空 | 内容格式问题 | 检查 Markdown 语法。SmartPage 只支持 content_type=0(纯文本) 或 1(Markdown) |
| 上传图片成功但页面看不到 | CDN URL 有效期 | SmartPage 创建的 CDN URL 有时效。及时使用 |

## 5. 通用集成错误

| 原始报错 | 人话 | 修复 |
|----------|------|------|
| `ModuleNotFoundError: No module named 'wecom_doc_reader'` | PYTHONPATH 未设置 | 设置 `PYTHONPATH=./scripts` 或用绝对路径 |
| `fixture 'reader' not found` | pytest 收集了集成测试 | 用 `python3 -m pytest scripts/test_wecom_doc_reader.py -v` 只跑单元测试 |
| `PermissionError: [Errno 13]` (cookie file) | 文件权限不足 | `chmod 600 /tmp/state.json` 或换路径 |
