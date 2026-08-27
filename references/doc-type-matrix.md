# 企微文档完整类型列表（从 SKILL.md 外移，2026-08-27 分层改造）


| 类型 | API doc_type | URL 前缀 | MCP 支持 | 浏览器读取方式 | 数据质量 |
|------|-------------|---------|---------|-------------|---------|
| 微文档 | DOC (3) | `w3_` → `/doc/w3_xxx` | ⚠️ | **opendoc API**（canvas 渲染，DOM 无效） | ✅ opendoc API 完整正文提取（v5.0 实现） |
| 电子表格 | SHEET (4) | `e3_` → `/sheet/e3_xxx` | ❌ | **SpreadsheetApp 原生 JS API**（v3.1 实测）。`getCellDataAtPosition` 直接读值+合并范围+图片URL | ✅ 内存直读，合并精确，图片原始URL |
| 智能表格 | SMARTSHEET (10) | `s3_` → `/smartsheet/s3_xxx` | ✅(2000条限制) | dop-api 全量结构化 | ✅ 完整字段+选项 |
| 思维导图 | MIND | `m4_` → `/mind/m4_xxx` | ❌ | **dop-api/get/mind**（JSON 节点树） | ✅ 完整节点 |
| 收集表 | FORM | `/form/...` | ❌ | DOM 文本提取 | ✅ |
| 幻灯片 | SLIDE | `/slide/...` | ❌ | DOM 文本提取 | ✅ |
| 流程图 | FLOWCHART | `/flowchart/...` | ❌ | DOM 文本提取 | ✅ |
| 汇报 | REPORT | `/report/...` | ❌ | DOM 文本提取 | ⏸️ 待测试 |
| 智能文档 | SMARTDOC | `/smartdoc/...` | ❌ | DOM 文本提取 | ⏸️ 待测试 |

**⚠️ API 创建限制**：官方 API（`create_doc`）仅支持创建 3 种类型：`doc_type=3`（微文档）、`4`（电子表格）、`10`（智能表格）。其他类型（幻灯片、汇报、智能文档等）只能通过企微 UI 创建。

### e3_ 电子表格 wecom_doc_reader 输出格式（2026-07-16 实测）

`wecom_doc_reader` 读取 e3_ 表格后返回的 JSON 结构与 s3_ 智能表格**不同**，消费者需注意：

```
{
  "success": true,
  "doc_type": "sheet",
  "sheets": {                          # ⚠️ dict（按 sheet 名索引），不是 list
    "工作排期": {
      "sheetId": "BB08J2",
      "headers": ["P系列文档排期", "col_1"],  # col_1 是自动生成的列名（无名列）
      "rows": [                         # ⚠️ 是 rows，不是 records
        {"_row": 1, "P系列文档排期": "阶段1:\n主流程相关文档优化", "col_1": "自主作业\n测地", "_sheet_name": "工作排期"},
        ...
      ],
      "row_count": 4,
      "mergeList": [...],
      "mergeCount": 0,
      "method": "native-js-api",
      "usedRange": "...",
      "readRange": "..."
    },
    "知识库目录结构": { ... }
  },
  "sheet_names": ["工作排期", "知识库目录结构"],  # 顺序列表
  "sheet_count": 2,
  "total": 203,
  "records": [...],                     # ⚠️ 兼容字段：所有 sheet 的 rows 合并（带 _sheet_name）
  "failed_sheets": [],
  "title": "P系列清单",
  "method": "native-js-api"
}
```

**关键差异（e3_ vs s3_）**：

| 字段 | e3_ 电子表格 | s3_ 智能表格 |
|---|---|---|
| `sheets` | dict，key=sheet 名，value={rows, headers, ...} | dict，同结构 |
| 行数据字段 | `rows` 数组，每行用 header 名做 key | `records` 数组（兼容字段），同结构 |
| 列名 | `headers` 数组，无名列为 `col_1`/`col_2`... | `field_names`（从 dop-api 列定义提取） |
| 单元格值 | 直接字符串/数字，含 `\n` 换行 | 按 k30 字段类型提取，select 需选项映射 |
| 合并单元格 | `mergeList` + `mergeCount` | 同 |

**消费 e3_ 数据的正确方式**：
```python
sheets = data["sheets"]  # dict
for sheet_name, sheet_data in sheets.items():
    headers = sheet_data["headers"]  # 列名列表
    rows = sheet_data["rows"]        # 行数据列表
    for row in rows:
        val = row.get(headers[0], "")  # 用 header 名取值
```

**⚠️ 完整性验证 Pitfall（2026-06-15 踩坑）**：
- 不要凭记忆列出文档类型清单 → 必须交叉验证：① 查官方 API 文档的 doc_type 参数 ② 实际打开企微 UI 创建菜单截图对比
- 2026-06-15 只列了 7 种类型，用户指出还有"汇报"和"智能文档"未覆盖

**说明**: e3_ 电子表格 v3.1.0 实测重构（2026-06-15）：
1. **SpreadsheetApp 原生 JS API**（主力，最稳定）：`sheet.getCellDataAtPosition(row, col)` 直接读单元格值、合并范围、图片原始 URL。**800 cells < 1ms**
2. **剪贴板 HTML**（降级）：当原生 API 不可用时，Ctrl+A/C → clipboard.read() → 解析 colspan/rowspan
3. **xlsx 导出**（降级）：需编辑权限
4. **剪贴板 TSV / DOM**（最终兜底）

**🚨 实测关键发现（2026-06-15 v3.1）**：
- **`getCellDataAtPosition(row, col)`** 是企微表格引擎的原生 JS API，直接读取内存中的 cell 数据
- `cell.getValue()` 返回值（字符串/数字），`cell.getMergeReference()` 返回精确合并范围
- `cell.getExtendedValue()` 返回图片原始 URL（如 `https://wdcdn.qpic.cn/...?w=4096&h=2304`）
- **非活跃 tab 数据懒加载**：必须先点击 tab + 等待 5 秒数据加载后才能读取
- dop-api 对 e3_ 返回 protobuf 二进制（非 JSON），v2.x 的 JSON.parse 代码从未真正跑通过
- 详见 `references/e3-native-js-api.md`

**⚠️ 历史教训（v2.x → v3.1 的演进）**：
- v2.x：假设 dop-api 返回 JSON → 代码从未跑通（protobuf 格式）
- v3.0：用剪贴板 HTML → 14/15 成功但图片列丢失、合并边界不精确
- v3.1：发现原生 JS API → 直接读内存，最稳定最完整

**⚠️ 合并单元格处理（2026-06-15 v2.7.0 关键改进）**：
- 灌溉日志、日历、分组表头等大量使用合并单元格的子表，用纯文本 TSV 提取后列名丢失、数据错位
- 策略2（HTML）通过解析 `<td colspan="N" rowspan="M">` 还原合并结构
- 策略3（xlsx）通过 openpyxl 的 `merged_cells.ranges` 精确获取合并范围
- 两者都将合并区域内的所有单元格填充为左上角的值
