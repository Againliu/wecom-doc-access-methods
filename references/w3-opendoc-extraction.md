# w3_ 微文档 opendoc API 提取指南

## 关键发现（2026-06-14）

w3_ 微文档使用 **canvas 渲染**，DOM 提取只能拿到工具栏和导航文字，无法获取正文。
必须通过 `dop-api/opendoc` API 获取完整文档内容。

## API 调用

```javascript
const apiUrl = 'https://doc.weixin.qq.com/dop-api/opendoc?padId=' + docId + '&normal=1&outformat=1';
const r = await fetch(apiUrl, {credentials: 'include'});
const text = await r.text();
```

## 返回格式（自定义文本，非 JSON）

```
head
json
6138
{JSON1}
text
text
1083355
{URL-encoded JSON2}
```

每段由 **标记行** 组成：
- `head` — 段类型（head/text/json）
- `json` — 子类型
- `<size>` — 数字，表示后续数据大小
- `{data}` — JSON 字符串或 URL 编码的 JSON

## 解析步骤

1. 按 `\n` 分割文本
2. 找到所有 `<数字>\n{JSON}` 对
3. 对 JSON 段直接 `JSON.parse`
4. 对文本段先 `urllib.parse.unquote` 再解析
5. 提取 commands 数组中的文本内容

## %uXXXX 编码

企微文档使用自定义编码：
- `%uXXXX` → Unicode 字符（如 `%u6D4B` → 测）
- `%XX` → 标准 URL 编码
- `\r` → 换行
- 控制字符（`\x08, \x13, \x14, \x15` 等）→ 清除

### 解码函数

```python
import re
from urllib.parse import unquote

def _decode_wecom_text(s: str) -> str:
    """解码企微文档的 %uXXXX 编码文本"""
    # %uXXXX → Unicode
    s = re.sub(r'%u([0-9a-fA-F]{4})', lambda m: chr(int(m.group(1), 16)), s)
    # 标准 URL 编码
    s = unquote(s)
    # \r → 换行
    s = s.replace('\\r', '\n')
    # 清除控制字符
    s = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', s)
    # 清除 HYPERLINK 标记（保留链接文本）
    s = re.sub(r'[\x13\x08]?\s*HYPERLINK\s+\S+\s+[\x14]?(.*?)[\x15]', r'\1', s)
    s = re.sub(r'HYPERLINK\s+\S+\s*', '', s)
    return s.strip()
```

## Pro 版格式（isPro: true，2026-08-11 修复）

新版 Pro 微文档返回**纯 JSON**（非自定义文本分段），`padHTML` 为空，正文在：
`clientVars.collab_client_vars.initialAttributedText`（OT 结构，text[].commands[].mutations[]）

- mutations 的 `s` 字段为编码文本（同样需 `_decode_wecom_text` 解码），拼接即全文
- mutation `ty` 值：`mp`（文本主体）、`ir`（批注 commentRange，跳过）、`ms`/`is`（结构操作）
- 图片/附件如存在，位于 mutations 或 attribs 中；当前提取器只取正文文本，不含图片 URL 和批注内容

识别方式：`json.loads` 成功且含 `clientVars` → 走 OT 分支；否则走经典分段格式。

## Pitfalls

- ❌ DOM 提取无效（canvas 渲染）
- ❌ 不能直接 `JSON.parse` 整个响应（经典格式是自定义文本；Pro 格式可以直接 parse）
- ⚠️ HYPERLINK 标记会残留，需要正则清理
- ✅ 解码后文本通常 5000-15000 字符，包含完整正文
- ⚠️ Pro 文档 `padHTML` 为空，只走 padHTML 路径会返回"无法解析"

## 验证方法

测试文档（示例）：
- 解码后 10524 字符
- 关键词命中率：文档标题 ✅、章节标题 ✅、正文段落 ✅
