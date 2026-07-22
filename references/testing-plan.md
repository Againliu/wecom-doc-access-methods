# wecom-doc-access-methods Skill 测试方案（2026-07-22 · 长期维护）

> 供所有主流 AI coding agent 执行的自动化测试方案。
> 从 GitHub clone 后逐步执行，每步记录实际结果与预期对比。
> 测试完成后通过 GitHub Issues 或飞书提交结果（见文末「结果提交」）。

## 目标 AI 工具

本方案面向以下 AI coding 工具，任何能执行 shell 命令和 Python 脚本的工具均可参与：

| 工具 | 特点 |
|------|------|
| GPT Cowork | GPT 驱动，擅长 Web 交互 |
| OpenAI Codex CLI | 代码生成 + 终端执行 |
| Claude Code | Anthropic 驱动，擅长代码分析 |
| Cursor | IDE 集成，内嵌 agent |
| GitHub Copilot CLI | GitHub 生态，`gh` 原生支持 |
| Trea | 国产 AI IDE |
| Windsurf | Codeium 驱动 |
| Augment | 代码补全 + agent |
| Cline / 其他 | 任何能跑 shell + Python 的 AI agent |

## 前置条件

1. Python 3.8+
2. `pip install playwright requests beautifulsoup4 pyyaml`
3. `playwright install chromium`
4. 企微扫码 cookie（用于浏览器方案测试）：`python3 scripts/wecom_login.py --state /tmp/state.json --qr /tmp/qr.png`
5. MCP apikey（用于 MCP 方案测试）：设置环境变量 `WECOM_MCP_APIKEY=<key>`
6. **测试用临时文档**：在企微里创建测试文档（s3_/e3_/w3_/SmartPage 各一个），用完删除

## 一、环境安装测试

```bash
git clone https://github.com/Againliu/wecom-doc-access-methods.git /tmp/wecom-test
cd /tmp/wecom-test
pip install -r requirements.txt
playwright install chromium
python3 -m pytest scripts/test_wecom_doc_reader.py -v
```

**预期**：3 passed, 0 errors（v5.2.0 已修复 fixture 问题）。import 成功。

## 二、读能力测试（各文档类型）

### 2.1 s3_ 智能表格（MCP）
```python
import requests, json
MCP_URL = "https://qyapi.weixin.qq.com/mcp/robot-doc?apikey=" + KEY
payload = {"jsonrpc":"2.0","method":"tools/call","params":{"name":"smartsheet_get_sheet","arguments":{"url":DOC_URL}},"id":1}
r = requests.post(MCP_URL, json=payload, headers={"Accept":"application/json"}, timeout=30)
print(json.loads(r.json()["result"]["content"][0]["text"]))
```
**预期**：返回 sheet_id + 字段列表，errcode=0

### 2.2 s3_ 智能表格（浏览器 dop-api，无 2000 限制）
```bash
PYTHONPATH=./scripts python3 -m wecom_doc_reader read <user_id> <s3_url> --state /tmp/state.json
```
**预期**：返回完整 JSON（records 数组 + 字段映射），行数 > MCP 的 2000 限制时仍完整

### 2.3 e3_ 电子表格（浏览器原生 JS API）
```bash
PYTHONPATH=./scripts python3 -m wecom_doc_reader read <user_id> <e3_url> --state /tmp/state.json
```
**预期**：返回 sheets dict，rows 含合并单元格 + 图片 URL

### 2.4 w3_ 微文档（MCP 异步轮询）
```python
# 第一次调用拿 task_id，复调拿内容
payload = {"jsonrpc":"2.0","method":"tools/call","params":{"name":"get_doc_content","arguments":{"url":W3_URL,"type":2}},"id":1}
# ... 轮询直到 task_done=true
```
**预期**：返回 Markdown 格式正文

### 2.5 SmartPage（MCP 导出）
```python
payload = {"jsonrpc":"2.0","method":"tools/call","params":{"name":"smartpage_export_task","arguments":{"url":SP_URL,"content_type":1}},"id":1}
# 轮询 smartpage_get_export_result 直到 task_done=true
```
**预期**：返回 Markdown 格式内容

## 三、写能力测试

### 3.1 s3_ 智能表格 — 增删改记录（MCP）
```python
# 增：smartsheet_add_records
# 改：smartsheet_update_records（需先 get_records 拿 record_id）
# 删：smartsheet_delete_records
```
**预期**：每步 errcode=0，get_records 验证数据变更

### 3.2 e3_ 电子表格 — 写入范围（MCP）
```python
# sheet_update_range_data + sheet_append_data
```
**预期**：打开企微 UI 确认数据写入

### 3.3 w3_ 微文档 — 编辑内容（MCP）
```python
# edit_doc_content（只改 bot 创建的文档，成员文档报 851003）
```
**预期**：get_doc_content 读回确认内容变更

### 3.4 SmartPage — 创建带图四步法
```python
# Step 1: smartpage_create 创建容器 → 拿 docid
# Step 2: upload_doc_image 上传图片到容器（url 参数 = SmartPage 访问链接）
# Step 3: 内容中用 ![](cdn_url) 嵌入（⚠️ 英文括号 ()，不是中文括号）
# Step 4: smartpage_create 创建正式 SmartPage，完整内容一次性写入
```
**预期**：打开 SmartPage 确认图片渲染。⚠️ 写错只能重建（不支持 edit_doc_content）

### 3.5 图片上传（直调 MCP JSON-RPC）
```bash
python3 scripts/upload_image.py /tmp/test.png <docid>
```
**预期**：返回 `{"ok": true, "url": "https://wdcdn.qpic.cn/..."}`

## 四、安全测试

### 4.1 脱敏扫描
```bash
# 扫描发布文件不含敏感信息
cd /tmp/wecom-test
find . -type f ! -path './.git/*' | xargs grep -lE 'apikey=[A-Za-z0-9]{20,}|<wecom_userid_prefix>|106\.53\.' 2>/dev/null
```
**预期**：无输出（0 拋留）

### 4.2 敏感文件排除
```bash
ls references/identity-resolution-pitfalls.md references/851003-diagnostic.md 2>/dev/null
```
**预期**：文件不存在（被 .gitignore 排除）

### 4.3 publish_skill.sh 脱敏关卡
```bash
# 故意在文件里加一个假 key，验证 publish_skill.sh 是否拦截
python3 -c "open('scripts/test_sens.py','a').write('api'+'key='+'X'*30+'\n')"
publish_skill.sh wecom-doc-access-methods
# 预期：🚨 敏感信息检测到，拒绝发布
rm scripts/test_sens.py
```

## 五、可移植性测试

### 5.1 干净环境安装
```bash
python3 -m venv /tmp/wecom-venv
source /tmp/wecom-venv/bin/activate
pip install playwright requests beautifulsoup4 pyyaml
git clone https://github.com/Againliu/wecom-doc-access-methods.git /tmp/wecom-portable
cd /tmp/wecom-portable
python3 -c "from scripts.wecom_doc_reader import reader; print('import OK')"
PYTHONPATH=./scripts python3 -m wecom_doc_reader --help
```
**预期**：import 成功，CLI 可用

### 5.2 MCP JSON-RPC 直调（无 MCP client 的 AI 工具也能用）
```python
# 参见 references/mcp-api-guide.md 的 mcp_call() 函数
# 不依赖任何 MCP client 框架，纯 requests + json
```

## 六、测试结果模板

| 测试项 | 预期 | 实际 | 通过 |
|--------|------|------|------|
| 环境 import | ✅ | | |
| s3_ MCP 读 | sheet_id+字段 | | |
| s3_ 浏览器读 | 全量 JSON | | |
| e3_ 浏览器读 | sheets+合并 | | |
| w3_ MCP 读 | Markdown 正文 | | |
| SmartPage 导出 | Markdown | | |
| s3_ 增记录 | errcode=0 | | |
| e3_ 写范围 | UI 确认 | | |
| w3_ 编辑 | 读回确认 | | |
| SmartPage 带图 | 图片渲染 | | |
| 图片上传 | CDN URL | | |
| 脱敏扫描 | 0 拋留 | | |
| 敏感文件排除 | 不存在 | | |
| publish 关卡 | 拦截 | | |
| 干净环境 | import OK | | |


## 七、结果提交

测试完成后，请将结果通过以下方式之一提交：

### 方式 A：GitHub Issues（推荐）

```bash
# 生成标准化结果 JSON
cat > /tmp/test-result.json << 'EOF'
{
  "tool": "Claude Code",
  "version": "1.0.0",
  "date": "2026-07-22",
  "environment": {"python": "3.11", "os": "macOS 14.5"},
  "results": {
    "T1_import": {"status": "pass", "note": ""},
    "T2_cli": {"status": "pass", "note": ""},
    "T3_syntax": {"status": "pass", "note": ""},
    "T4_s3_mcp_read": {"status": "pass", "note": "5 records"},
    "T5_s3_browser_read": {"status": "skip", "note": "no browser cookie"},
    "T6_w3_mcp_read": {"status": "pass", "note": ""},
    "T7_smartpage_export": {"status": "pass", "note": ""},
    "T8_e3_browser_read": {"status": "skip", "note": "no browser cookie"},
    "T9_s3_add": {"status": "pass", "note": ""},
    "T10_w3_edit": {"status": "pass", "note": ""},
    "T11_smartpage_images": {"status": "pass", "note": "4-step method verified"},
    "T12_upload_image": {"status": "pass", "note": ""},
    "T13_desensitize": {"status": "pass", "note": "0 hits"},
    "T14_sensitive_exclude": {"status": "pass", "note": ""},
    "T15_no_hardcode_key": {"status": "pass", "note": ""},
    "T16_auth_check": {"status": "pass", "note": ""},
    "T17_clean_install": {"status": "pass", "note": ""},
    "T18_mcp_direct": {"status": "pass", "note": ""}
  },
  "summary": {"total": 18, "pass": 14, "skip": 2, "fail": 0},
  "pitfalls": {"P1_smartpage_edit": "confirmed", "P2_chinese_parens": "confirmed"},
  "notes": "浏览器路径需要企微 cookie，CI 环境跳过"
}
EOF

# 提交 GitHub Issue
gh issue create --repo Againliu/wecom-doc-access-methods \
  --title "Test Results: <tool-name> <date>" \
  --body "$(cat /tmp/test-result.json)"
```

### 方式 B：飞书文档结果汇总表

测试结果会汇总到飞书文档：<your_feishu_test_doc_url>

AI 工具可将自己的结果行追加到下方表格（如有飞书 API 权限），或由 AI 助手从 GitHub Issues 收集后统一更新。

### 结果汇总

| 工具 | 日期 | 通过/总数 | 跳过 | 失败 | 备注 |
|------|------|----------|------|------|------|
| _（等待提交）_ | | | | | |

### 标准结果 JSON 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `tool` | string | AI 工具名称（如 "Claude Code"） |
| `version` | string | 工具版本 |
| `date` | string | 测试日期 YYYY-MM-DD |
| `environment` | object | Python 版本、OS 等 |
| `results` | object | 每个测试项的 status + note |
| `summary` | object | total/pass/skip/fail 统计 |
| `pitfalls` | object | 已知坑点验证结果 |
| `notes` | string | 补充说明 |
