# e3_ vs s3_ dop-api 数据结构差异

> 2026-06-15 v3.0 更新。v3.0 实测确认 e3_ dop-api 返回 protobuf 二进制（非 JSON），废弃 dop-api 解析路径。

## 问题背景

企微的 `dop-api/get/sheet` 接口对 s3_（智能表格）和 e3_（传统电子表格）**行为完全不同**。v2.x 的代码试图用 s3_ 的 JSON 解析逻辑读取 e3_，**从未真正成功过**。

## s3_ 智能表格的 dop-api 结构（已实现，生产验证）

```
JSON.parse(text[0].smartsheet) → [[items...]]
items = [
  {t: 3005, c: {...}},   // 列定义：字段名、类型、选项映射
  {t: 3028, c: {...}},   // 行数据：record_id → field_id → cell value
]
```

**关键特征**：
- 使用 `t` 字段区分数据类型（3005=列定义, 3028=行数据）
- 行数据按 `field_id`（UUID 格式）索引
- 有完整的字段类型定义（k31）和选项映射
- 不支持合并单元格

## e3_ 电子表格的 dop-api 结构（v3.0 实测确认 — protobuf，不可解析）

**🚨 v3.0.0 关键实测结论**：

| 特征 | s3_ 智能表格 | e3_ 电子表格 |
|------|------------|-------------|
| `smartsheet` 字段 | JSON 字符串（可解析） | **空字符串** |
| `related_sheet` 字段 | 不存在 | **base64+zlib → protobuf 二进制** |
| 可解析性 | ✅ JSON.parse 即可 | ❌ protobuf 无法直接解析 |
| 合并单元格 | 无（s3_ 不支持） | protobuf 中可能有，但无法提取 |
| 图片 URL | 在 k31 类型值中 | protobuf 中可见 `wdcdn.qpic.cn` URL，但无法结构化提取 |

**实测证据**：
1. e3_ 文档 dop-api 返回 `text[0]` 中 `smartsheet` 是空字符串 `""`
2. 数据在 `related_sheet` 字段（base64 url safe → zlib decompress → protobuf 二进制）
3. 解压后可见中文 sheet 名和图片 URL，但整体是 protobuf 格式
4. 没有 protobuf schema 定义，无法结构化解析

**v2.x 为什么一直失败**：`_try_dop_for_spreadsheet` 试图 `JSON.parse(item.smartsheet)` — 但 e3_ 的 `smartsheet` 是空字符串 → parse 失败 → 返回空数据 → 降级到剪贴板

## v3.0 替代方案：JS Runtime + 剪贴板 HTML

### JS Runtime 元数据（v3.0 新增）

```javascript
// 从 SpreadsheetApp.workbook JS 运行时提取元数据
SpreadsheetApp.workbook 提供:
- sheet 列表（id, name）
- mergeList（合并单元格范围）
- 图片 URL（已解码）
// ⚠️ cell 数据是懒加载的，不能直接获取
```

### 剪贴板 HTML（主力数据源）

Ctrl+A/C → `navigator.clipboard.read()` → `text/html` MIME → 解析 `<table>` 的 `colspan`/`rowspan`

**实测验证**：15 子表全量读取，684 条记录，164 个合并单元格正确还原。

## 修复 dop-api 的潜在方向（如果未来需要）

### 方案 A：protobuf schema 逆向（高难度）
1. 用 protobuf 反编译工具分析 `related_sheet` 二进制
2. 逆向出 schema 定义
3. 实现 e3_ 专用解析器
4. **风险**：企微内部 protobuf schema 可能随时变更

### 方案 B：opendoc 拦截（中等难度）
1. 页面加载时拦截 `dop-api/opendoc` 响应
2. opendoc 可能包含更易解析的格式
3. **风险**：opendoc 也可能使用 protobuf

### 方案 C：继续使用 JS Runtime + HTML（当前最佳）
1. JS Runtime 提供元数据（sheet 列表、合并区域、图片 URL）
2. 剪贴板 HTML 提供完整 cell 数据
3. **优势**：已验证稳定，无需逆向 protobuf
