# SmartPage (a1_) 纯 HTTP 读取协议

> 2026-08-27 实测验证。零浏览器依赖，cookie 即可。

## 何时用

读取 a1_ SmartPage 文档内容。`doctor` 浏览器诊断失败也不影响此路径。

## API 端点

### 1. sp_opendoc — 首页 + 元数据

```
POST https://doc.weixin.qq.com/smartcanvasread/opendoc
body: { globalPadId: "a1_xxx", pad_ver: 0, type: 3, page_id: "0" }
```

返回：
- `body.meta`: author/created_at/updated_at/pad_ver（**无 title 字段**）
- `body.top_blocks`: 顶层块数组（第 0 个是根容器，第 1 个起是页面）
- `body.cur_blocks`: 首页的 blocks（初始 ~100 块）

### 2. get_block_filter_by_type — 翻页拉全量块

```
POST https://doc.weixin.qq.com/smartcanvasread/get_block_filter_by_type
body: { globalPadId, pad_ver, type: 3, cursor: <prev_cursor> }
```

- `cursor` 是字典，透传上一页返回的 `body.cursor`。首次用 sp_opendoc 返回的。
- 每页 ~100 块。`has_more=true` 时继续翻。
- **API 上限 10000 块**：到达后继续翻返回同页。设置 `has_more_remaining=true` 如实报告，不要重试。

### 3. publish_info — 发布状态（可选）

```
POST https://doc.weixin.qq.com/diskshare/get_publish_info
body: { task_id: <from gen_publish_url> }
```

轮询约 30 秒。`pb_doc_id` 非空 = 已发布。

## 数据结构

### Block 类型

| type | 含义 | props 里的文本键 |
|---|---|---|
| 1 | 文本块 | `title.text` |
| 2 | 图片块 | `media_props.image_props.display_source`（CDN URL） |
| 5 | 页面块 | `title.text`（页面标题） |
| 12-17 | 标题块 | `title.text` |
| 26/27/28 | 表格块 | 无文本 |

### 页面树组装

- `type=5` 的块是页面。`parent_id` 指向父页面。
- 顶层页：`parent_id` 不在 pages 字典里的 type=5 块。
- 子块归属：按 `parent_id` 分组。
- 排序：有 `children` 数组时以其为准（block id 顺序），否则按原始顺序。
- `children` 顺序无法用 API 重排（operation 6/7/remove+add 全假成功）。

## 完整性指标

```python
{
    "page_count": _count_leaves(page_tree),  # 递归计数
    "block_count": len(seen),                # 去重后的唯一块数
    "text_length": len(all_text),            # type 1/12-13 的 title.text 拼接
    "image_count": sum(type==2),             # 图片块数
    "orphan_block_count": 非页面块 parent_id 不在 seen 中的数量,
    "api_calls": 翻页请求总数,
    "has_more_remaining": truncated,         # 是否因 10k 上限截断
}
```

## title 字段

文档标题 = `page_tree[0]["title"]`（第一个顶层页面的标题）。
- `meta` 无 title 键。
- `top_blocks[1].props.text` 可行但索引脆弱（假设第 0 个是根容器）。
- 根页面标题最稳。

## 实测数据

| 文档 | 页数 | 块数 | 字数 | 图片 | 孤儿 | 翻页 |
|---|---|---|---|---|---|---|
| 农服App介绍 | 89 | 10,000 | 206,598 | 720 | 0 | 50 次（触 10k 上限） |

## 不依赖此协议的场景

- 写入 SmartPage → 见 `references/smartpage-http-api-write.md`
- 删除 block → 见 `references/smartpage-delete-block.md`
- 浏览器编辑探索 → 见 `references/smartpage-editing-exploration.md`
