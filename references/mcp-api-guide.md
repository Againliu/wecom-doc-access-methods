# 方案二(fallback):MCP API — 详细指南

> 本文件由 SKILL.md 拆分而来(2026-07-21,原 SKILL.md 152KB 超 skill_manage 100KB 上限)。

## 方案二（fallback）：MCP API

> ⚠️ 仅用于快速浏览/简单场景。返回 Markdown 纯文本，多子表时有 `|` 列错位风险（详见 Pitfalls）。需要写操作时也可用 MCP（浏览器方案只读）。

```yaml
mcp_servers:
  企业微信文档:
    url: "https://qyapi.weixin.qq.com/mcp/robot-doc?apikey=YOUR_KEY"
```

### 能力范围

- ✅ `s3_` 智能表格：可读写
- ✅ `w3_` 微文档：可读（异步轮询）
- ❌ `e3_` 旧格式：不支持（errcode 851000）
- ❌ `w3_` blankpage：不支持（errcode 851003）

### 调用方式

```python
import requests, json

def mcp_call(mcp_url, tool_name, arguments):
    """直接调 MCP Server JSON-RPC"""
    payload = {
        "jsonrpc": "2.0", "method": "tools/call",
        "params": {"name": tool_name, "arguments": arguments}, "id": 1
    }
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    resp = requests.post(mcp_url, json=payload, headers=headers, timeout=60)
    data = resp.json()
    if "error" in data:
        raise Exception(f"MCP error: {data['error']}")
    inner = json.loads(data["result"]["content"][0]["text"])
    if inner.get("errcode", 0) != 0:
        raise Exception(f"API error: {inner.get('errmsg')} (errcode={inner.get('errcode')})")
    return inner

# 读智能表格
sheets = mcp_call(URL, "smartsheet_get_sheet", {"url": doc_url})
records = mcp_call(URL, "smartsheet_get_records", {"url": doc_url, "sheet_id": sheet_id})

# 读微文档（异步轮询）
result = mcp_call(URL, "get_doc_content", {"url": doc_url, "type": 2})
if result.get("task_id") and not result.get("task_done"):
    import time; time.sleep(2)
    result = mcp_call(URL, "get_doc_content", {"task_id": result["task_id"], "type": 2})
```

### 已知限制

1. **2000 条硬限制**：`smartsheet_get_records` 最多返回 2000 条，`has_more: true` 但分页参数（offset/cursor/start）**全部无效**
2. **授权过期**：errcode 851014 / 2200063，需文档所有者重新分享给机器人
3. **应用隔离**：只能读写应用自己创建的文档，或成员主动分享的文档

### 授权流程

文档所有者在企微打开文档 → 右上角「分享」→ 搜索并添加机器人应用 → 给阅读权限

### Pitfalls

- ❌ 不要尝试分页，始终返回前 2000 条
- ❌ 授权不是永久的，会过期
- ✅ 增量同步不受 2000 条限制（新增/修改都能拿到）
- ✅ 写操作（upsert/delete）没有数量限制

---

