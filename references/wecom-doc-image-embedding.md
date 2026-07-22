# 企微文档图片嵌入与上传（2026-07-22 更新）

## 一、文档类型与图片支持

| 类型 | 编辑方式 | 图片嵌入方式 | 支持 data URI |
|:------|:------|:------|:----:|
| w3_ 普通文档 | `edit_doc_content` | `![](cdn_url)` 或 `![](data:image/png;base64,...)` | ✅ |
| e3_ 电子表格 | `sheet_update_range_data` | ❌ 不支持图片内嵌 | ❌ |
| s3_ 智能表格 | `smartsheet_add_records` IMAGE 字段 | `[{image_url: "cdn_url", title: "标题"}]` | ❌ 用 CDN URL |
| SmartPage 智能文档 | `smartpage_create` | `![](cdn_url)`（三步法） | ❌ 会被删除 |

## 二、图片上传方式对比（2026-07-16 实测验证）

### 方式 1：Hermes MCP `upload_doc_image` 工具 — 有 8KB 限制

| 问题 | 详情 |
|------|------|
| ~8KB base64 限制 | Hermes 客户端层限制，超出报 errcode 640027 |
| 超时太短 | 大图传不完 |

### 方式 2：直调 MCP JSON-RPC（推荐） — 无限制

**关键发现（2026-07-16 实测）**：8KB 限制是 Hermes **客户端层**的，不是 MCP server 端的。直接用 Python `requests.post` 调 MCP URL，可上传任意大小图片。

```python
import requests, base64, json, os

MCP_URL = "https://qyapi.weixin.qq.com/mcp/robot-doc?apikey=YOUR_KEY"
DOCID = "your_doc_id"

with open("image.png", "rb") as f:
    b64 = base64.b64encode(f.read()).decode()

payload = {
    "jsonrpc": "2.0", "method": "tools/call",
    "params": {"name": "upload_doc_image", "arguments": {"base64_content": b64, "docid": DOCID}},
    "id": 1
}
resp = requests.post(MCP_URL, json=payload,
    headers={"Content-Type": "application/json", "Accept": "application/json"}, timeout=120)
inner = json.loads(resp.json()["result"]["content"][0]["text"])
# 返回: {errcode: 0, url: "https://wdcdn.qpic.cn/...", width, height, size}
```

**实测结果**：
- 35.3KB 图片（base64 47KB）上传成功
- CDN 返回尺寸 = 原图尺寸（1920x1080，未缩放）
- CDN 下载大小 vs 原图：99.3%（几乎无损）
- 需要传 `docid` 参数（不传报 errcode 301085）
- **必须加 `Accept: application/json` header**（否则报 `Not Acceptable`）

### 方式 3：upload_doc_file — 上传任意文件（非图片）

```python
# 同样直调 MCP JSON-RPC
payload = {
    "jsonrpc": "2.0", "method": "tools/call",
    "params": {"name": "upload_doc_file", "arguments": {"file_name": "test.txt", "file_base64_content": b64}},
    "id": 1
}
# 返回 file_id，可用于 smartsheet ATTACHMENT 字段
```

## 三、质量与压缩

| 环节 | 压缩情况 |
|------|---------|
| upload_doc_image 直调 | ✅ 几乎无损（99.3%） |
| CDN 二次压缩 | ⚠️ 有压缩，但源图质量越高效果越好 |
| w3_ edit_doc_content `![](url)` | 企微自动下载转 base64 内嵌（可能二次压缩） |
| s3_ IMAGE 字段 | 存储 CDN URL（不内嵌） |

**建议**：
- 示意图（含线条文字）尽量用高分辨率源图，减轻 CDN 压缩模糊
- 照片天然比示意图耐 JPEG 压缩
- 优先用直调 MCP JSON-RPC 上传，不用 Hermes 客户端工具

## 四、各文档类型图片嵌入流程

### w3_ 普通文档
1. 直调 MCP upload_doc_image → 拿 CDN URL
2. `edit_doc_content` 写入 `![标题](cdn_url)`
3. 企微自动下载转 base64 内嵌（文档自包含）

### s3_ 智能表格
1. 直调 MCP upload_doc_image → 拿 CDN URL
2. `smartsheet_add_records` IMAGE 字段写入 `[{image_url: cdn_url, title: "标题"}]`
3. 返回 {height, width, id, image_url, title}

### SmartPage 嵌入图片 — 正确四步法（2026-07-22 另一 Agent 实测验证）

**正确流程**：
1. **创建容器 SmartPage**（`smartpage_create`）→ 获取 docid
2. **用 `upload_doc_image` 上传图片到容器** → 拿 CDN URL
3. **在 SmartPage 内容中用 Markdown 图片语法嵌入**：`![](cdn_url)`
   - 🚨 **必须用英文括号 `()`，不能用中文括号 `（）`**（中文括号不渲染）
4. **创建正式的 SmartPage**，把带图片 URL 的**完整内容一次性写入**

**关键命令参数**：
- `upload_doc_image` 的 `url` 参数：**必须指定**，填容器 SmartPage 的**完整访问链接**（或 docid，二选一），否则报错（errcode 301085）
- `smartpage_create` 的 `page_content`：直接写 `![](url)`，**不需要 `<img>` 标签**
- **图片尺寸**：原始 2880×1616（4K 截图）上传后 SmartPage 会**自动缩放**，无需预先压缩尺寸

**⚠️ 注意**：
- SmartPage 不支持 data URI（`![](data:image/...)` 会被删除），必须先上传拿 CDN URL。
- 🚨 **SmartPage 不支持 `edit_doc_content` 编辑，写错了只能重新创建** — 所以第 4 步务必把完整内容一次性写入，别指望后续修补。
- ✅ 图片上传到容器后获取的 CDN URL 是**独立的**，可以在**任何文档中引用**（容器 SmartPage 仅作上传宿主，用完后保留或删除均可）。

### e3_ 电子表格
- ❌ 不支持图片内嵌
