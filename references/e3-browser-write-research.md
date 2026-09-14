# e3_ 电子表格浏览器写入 API（2026-07-23 实测闭环）(索引)

> 原文件 5408 字符超 5000 门禁,已拆为 2 个分片(2026-09-08,只搬不删,备份 `references/e3-browser-write-research.md.bak-20260908`)。
> 新增坑:追加到对应分片,不要往本索引写正文。

## 分片索引

- `references/e3-browser-write-research/p1.md` — 状态：✅ 已闭环（纯 API 写入 + 服务端持久化验证通过）;核心发现;关键 API 入口;Mutation 格式（type=17 = SetCellValue）;🚨 关键 Pitfall：不能替换 cell/gridRangeData 对象;获取 Mutation 实例的方法…
- `references/e3-browser-write-research/p2.md` — commitMutation 返回 Promise（重要）;WS 协议;替代方案：键盘模拟写入（已验证可用）;实测验证记录（2026-07-23）;探索历程;测试文档
