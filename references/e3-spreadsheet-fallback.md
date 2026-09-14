# e3_ 电子表格读取方案（v3.0 实测重构）(索引)

> 原文件 5256 字符超 5000 门禁,已拆为 2 个分片(2026-09-08,只搬不删,备份 `references/e3-spreadsheet-fallback.md.bak-20260908`)。
> 新增坑:追加到对应分片,不要往本索引写正文。

## 分片索引

- `references/e3-spreadsheet-fallback/p1.md` — 降级策略（v3.0）;策略选择决策树;Phase 0: JS Runtime 元数据（v3.0 新增）;Phase 1: 剪贴板 HTML（主力方案）;Phase 2: xlsx 导出;Phase 3/4: TSV / DOM 兜底…
- `references/e3-spreadsheet-fallback/p2.md` — 全量实测验证（v3.0）;测试文档：超级棉田第六季（15 子表）;Pitfalls
