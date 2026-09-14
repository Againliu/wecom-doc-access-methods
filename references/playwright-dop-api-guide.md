# 方案一(首选):Playwright + dop-api — 全量读取详细指南(索引)

> 原文件 14956 字符超 5000 门禁,已拆为 6 个分片(2026-09-08,只搬不删,备份 `references/playwright-dop-api-guide.md.bak-20260908`)。
> 新增坑:追加到对应分片,不要往本索引写正文。

## 分片索引

- `references/playwright-dop-api-guide/p1.md` — 方案一（首选）：Playwright + dop-api（全量读取，生产验证）;原理;前置条件;步骤 1：扫码登录获取 storage_state;步骤 2：检查 cookie 有效性
- `references/playwright-dop-api-guide/p2.md` — 主动提醒：cookie 到期前 4 天通知用户（2026-06-26 团队负责人要求，2026-07-15 提前到 4 天）
- `references/playwright-dop-api-guide/p3.md` — 步骤 3：获取全量数据（两种方式）;方式 A：拦截页面自动加载的响应;方式 B：主动 fetch（推荐，需拦截 xsrf + 完整参数 + base64+zlib 解码）
- `references/playwright-dop-api-guide/p4.md` — 微文档 w3_ 读取（opendoc API）;思维导图 m4_ 读取（dop-api/get/mind）
- `references/playwright-dop-api-guide/p5.md` — 步骤 4：解析数据;步骤 5：select 选项映射（从 sheet 数据列定义提取）
- `references/playwright-dop-api-guide/p6.md` — 多子表处理（v2.1 默认读取所有子表）
