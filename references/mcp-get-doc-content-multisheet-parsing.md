# MCP get_doc_content 多子表 Markdown 解析参考(索引)

> 原文件 5233 字符超 5000 门禁,已拆为 2 个分片(2026-09-08,只搬不删,备份 `references/mcp-get-doc-content-multisheet-parsing.md.bak-20260908`)。
> 新增坑:追加到对应分片,不要往本索引写正文。

## 分片索引

- `references/mcp-get-doc-content-multisheet-parsing/p1.md` — 适用场景;核心发现（2026-06-29 实测）;1. 子表标记格式;子表名称;2. 不同子表列数不同（🚨 最大陷阱）;3. 单元格内 `|` 字符导致列错位（🚨 第二大陷阱）…
- `references/mcp-get-doc-content-multisheet-parsing/p2.md` — 解析脚本模板;数据质量检查清单;与 smartsheet_get_records 的对比
