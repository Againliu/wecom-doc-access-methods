# dop-api 数据结构完整参考(索引)

> 原文件 10187 字符超 5000 门禁,已拆为 3 个分片(2026-09-08,只搬不删,备份 `references/dop-api-data-structure.md.bak-20260908`)。
> 新增坑:追加到对应分片,不要往本索引写正文。

## 分片索引

- `references/dop-api-data-structure/p1.md` — 三种响应格式（2026-06-14 实测更新）;格式 A: startrow=0 主动 fetch（✅ 推荐方式）;格式 B: base64+zlib 压缩（k 前缀键）;行数据提取路径
- `references/dop-api-data-structure/p2.md` — 列类型 ID（k31）— 2026-06-15 实测验证;⚠️ e3_ 电子表格 dop-api 数据结构（🚨 v3.0 实测确认：protobuf 二进制）;列定义结构（t=3005 项）;选项映射提取;用户映射（t=3005 项 → c.3.5）
- `references/dop-api-data-structure/p3.md` — endrow 实测;API URL 模板;新建子表延迟问题（2026-06-14）;多子表遍历模式（v2.0，2026-06-15）;⚠️ v4.2.0 改进（2026-06-29 实测）;完整流程（v4.2.0）…
