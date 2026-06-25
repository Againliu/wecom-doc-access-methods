# m4_ 思维导图读取指南

## 关键发现（2026-06-14 → 2026-06-16 实测修正）

m4_ 思维导图 DOM 只能拿到工具栏文字，无法获取节点内容。
数据在 `dop-api/get/mind` 返回的 `initialAttributedText.text` 中。
**⚠️ 实测发现：`text` 是 JSON 字符串（非数组），结构为 `{content: [{rootTopic: {...}}]}`**

## URL 前缀映射

```python
_URL_PREFIX_TO_TYPE = {
    "s3": "smartsheet",   # 智能表格
    "w3": "doc",          # 微文档
    "e3": "sheet",        # 电子表格
    "m4": "mind",         # 思维导图 ← 新增
}
```

## API 调用（实测修正版）

```javascript
const apiUrl = 'https://doc.weixin.qq.com/dop-api/get/mind?padId=' + docId + '&normal=1';
const r = await fetch(apiUrl, {credentials: 'include'});
const j = await r.json();
// ⚠️ initialAttributedText.text 是 JSON 字符串，不是数组！
const rawText = j?.data?.initialAttributedText?.text;
if (!rawText) return {error: 'no initialAttributedText.text'};
const parsed = JSON.parse(rawText);
// 结构: { content: [{ rootTopic: {...} }] }
const rootTopic = parsed?.content?.[0]?.rootTopic;
```

## 节点树结构（实测真实结构）

```json
{
  "content": [
    {
      "rootTopic": {
        "id": "root",
        "title": "根节点标题",
        "collapse": false,
        "children": {
          "attached": [
            {
              "id": "xxx",
              "title": "一级节点",
              "children": {
                "attached": [
                  {
                    "id": "yyy",
                    "title": "二级节点",
                    "children": {
                      "attached": [
                        {"id": "zzz", "title": "三级节点", "children": {"attached": []}}
                      ]
                    }
                  }
                ],
                "detached": []
              }
            }
          ],
          "detached": []
        }
      },
      "theme": {...},
      "title": "画布1",
      "id": "BB08J2",
      "relationships": []
    }
  ]
}
```

**关键点**：
- 子节点在 `children.attached` 数组中（不是直接在 `children` 下）
- `detached` 数组存放浮动主题（未连接到主树的节点）
- 每个 `content` 条目代表一个画布（canvas）

## 递归提取（适配 children.attached）

```python
def _extract_mind_nodes(node, depth=0, result=None):
    """递归提取思维导图全部节点（适配 children.attached 结构）"""
    if result is None:
        result = []
    title = node.get('title', '')
    if title:
        result.append({'depth': depth, 'title': title})
    children_container = node.get('children', {})
    attached = children_container.get('attached', []) if isinstance(children_container, dict) else []
    for child in attached:
        _extract_mind_nodes(child, depth + 1, result)
    return result
```

## 输出格式

```
根节点
  一级节点
    二级节点
      三级节点
  一级节点2
```

## Pitfalls

- ❌ DOM 提取无效（只能拿到工具栏）
- ✅ 必须用 `dop-api/get/mind` API
- ❌ **旧假设错误**：`initialAttributedText.text` 不是数组，是 JSON 字符串
- ❌ **旧假设错误**：子节点不在 `children` 数组，在 `children.attached` 数组
- ✅ `initialAttributedText.text` 本身就是 JSON 字符串，直接 `JSON.parse`
- ✅ 递归提取可获取完整节点树（包括子节点层级）
- ⚠️ 某些文档可能没有 `initialAttributedText`（文档不存在/无权限时返回空 data）

## 实测验证

测试文档：`m4_AYEAJgaYADQCNgZiZmX5kQT6WQNNZ`（超级棉田设备关联情况）
- 提取 68 个节点
- 最大深度 6 层
- 包含完整层级结构：根 → 服务器 → 首部控制柜 → 设备类型 → 具体设备 → 轮灌组 → 阀体编号