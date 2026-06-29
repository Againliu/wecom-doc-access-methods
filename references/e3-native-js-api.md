# e3_ 电子表格原生 JS API 读取（2026-06-15 实测发现）

## 核心发现

企微 e3_ 电子表格页面内嵌了完整的 `SpreadsheetApp` JS 运行时，提供原生 API 直接读取单元格数据。**比剪贴板 HTML 更直接、更稳定、数据更完整。**

## API 入口

```javascript
const wb = window.SpreadsheetApp?.workbook;
const wm = wb.worksheetManager;
const sheetList = wm.sheetList;  // Array of sheet objects
```

## Sheet 对象结构

每个 sheet 对象关键属性：
- `sheet.cellDataGrid.usedRange.sheetId` — sheet ID（如 "myx250"）
- `sheet.cellDataGrid.usedRange.startRowIndex / endRowIndex / startColIndex / endColIndex` — 数据范围
- `sheet.mergeManager.mergeList` — 合并单元格列表
- `wm.getSheetNameBySheetId(sid)` — 获取 sheet 名称

## 核心读取 API

### `sheet.getCellDataAtPosition(row, col)` → cell object

**直接读取任意单元格的值，无需剪贴板操作。**

返回 cell 对象，关键方法/属性：

| 方法/属性 | 返回值 | 说明 |
|-----------|--------|------|
| `cell.getValue()` | string/number/null | **主方法**：获取单元格值 |
| `cell.getType()` | number | 单元格类型（4=字符串, 2=数字, 等） |
| `cell.isEmpty()` | boolean | 是否为空 |
| `cell.getFormattedValue()` | `{key, value}` | 格式化后的值 |
| `cell.getMergeReference()` | `{sheetId, startRowIndex, endRowIndex, startColIndex, endColIndex}` | **合并单元格精确范围** |
| `cell.getExtendedType()` | number | 扩展类型（5=图片） |
| `cell.getExtendedValue()` | JSON string | **图片列原始 URL**（如 `["https://wdcdn.qpic.cn/...", w, h]`） |
| `cell.getHyperlinks()` | array | 超链接列表 |
| `cell.getSourceValue()` | any | 原始值 |
| `cell.hasLink()` | boolean | 是否有链接 |
| `cell.getAuthor()` | string | 作者 |

### 实测数据样例

**宣传工作日志（myx250）**：
```javascript
// Row 0: 表头
getCellDataAtPosition(0, 0).getValue() → "序号"
getCellDataAtPosition(0, 1).getValue() → "日期"
getCellDataAtPosition(0, 5).getValue() → "接待照片"

// Row 1: 数据
getCellDataAtPosition(1, 0).getValue() → 1
getCellDataAtPosition(1, 1).getValue() → 46030  // Excel serial number
getCellDataAtPosition(1, 2).getValue() → "新疆经销商"

// 图片列（row 1, col 5）
getCellDataAtPosition(1, 5).getExtendedType() → 5
getCellDataAtPosition(1, 5).getExtendedValue() → '["https://wdcdn.qpic.cn/MTY4ODg1MzI3MTI3ODcxNw_198618_djETrf6vsLZhdeyy_1768800700?w=4096&h=2304",400,225]'
```

**灌溉日志（a6hcp3）— 含合并单元格**：
```javascript
// 合并单元格范围
getCellDataAtPosition(0, 1).getMergeReference() → {
  sheetId: "a6hcp3",
  startRowIndex: 0, startColIndex: 1,
  endRowIndex: 0, endColIndex: 2
}
getCellDataAtPosition(1, 0).getMergeReference() → {
  sheetId: "a6hcp3",
  startRowIndex: 1, startColIndex: 0,
  endRowIndex: 7, endColIndex: 0  // 纵向合并 7 行
}

// mergeManager
sheet.mergeManager.mergeList.length → 103  // 灌溉日志有 103 个合并区域
```

## 性能

800 个单元格（100行 × 8列）读取：**<1ms**（纯 JS 内存操作，无 IO）

## ⚠️ 关键限制：懒加载

**非活跃 tab 的 cell 数据是懒加载的。** 必须先切换到对应 tab 并等待数据加载完成，否则 `getCellDataAtPosition` 返回空。

```python
# 切换 tab 的正确做法
tab_els = await page.query_selector_all('.tab-bar-item-title')
for el in tab_els:
    text = await el.text_content()
    if '灌溉日志' in (text or '').strip():
        await el.click()
        break
await page.wait_for_timeout(5000)  # 等待数据加载
# 现在才能用 getCellDataAtPosition 读灌溉日志的数据
```

**估算时间**：15 个子表，每个 ~5 秒加载 ≈ 75 秒总时间。

## 日期转换

`getValue()` 返回 Excel serial number（如 46030 = 2026-01-14）。转换公式：
```python
from datetime import datetime, timedelta
def excel_serial_to_date(serial):
    if isinstance(serial, (int, float)) and serial > 40000:
        return (datetime(1899, 12, 30) + timedelta(days=serial)).strftime("%Y-%m-%d")
    return str(serial)
```

## 完整读取流程（伪代码）

```python
async def read_e3_via_native_api(page, doc_url):
    # 1. 打开文档
    await page.goto(doc_url, wait_until="networkidle", timeout=60000)
    await page.wait_for_timeout(8000)  # 等 JS runtime 初始化
    
    # 2. 获取所有 sheet 元数据
    sheets_meta = await page.evaluate("""() => {
        const wb = window.SpreadsheetApp?.workbook;
        const wm = wb.worksheetManager;
        const result = {};
        for (const s of wm.sheetList) {
            const sid = s.cellDataGrid?.usedRange?.sheetId;
            if (!sid) continue;
            result[sid] = {
                name: wm.getSheetNameBySheetId(sid),
                usedRange: s.cellDataGrid.usedRange,
            };
        }
        return result;
    }""")
    
    # 3. 逐 tab 读取
    all_data = {}
    for sid, meta in sheets_meta.items():
        # 切换到该 tab
        tab_els = await page.query_selector_all('.tab-bar-item-title')
        for el in tab_els:
            t = await el.text_content()
            if t and t.strip() == meta['name']:
                await el.click()
                break
        await page.wait_for_timeout(5000)
        
        # 读取所有单元格
        ur = meta['usedRange']
        rows = await page.evaluate("""(range) => {
            const wb = window.SpreadsheetApp?.workbook;
            let target = null;
            for (const s of wb.worksheetManager.sheetList) {
                if (s.cellDataGrid?.usedRange?.sheetId === range.sheetId) {
                    target = s; break;
                }
            }
            if (!target) return [];
            const rows = [];
            for (let r = range.startRow; r <= range.endRow; r++) {
                const row = [];
                for (let c = range.startCol; c <= range.endCol; c++) {
                    const cell = target.getCellDataAtPosition(r, c);
                    if (cell && !cell.isEmpty()) {
                        const v = cell.getValue();
                        // 检查图片
                        const extType = cell.getExtendedType?.();
                        if (extType === 5) {
                            row.push({value: v, imageUrl: cell.getExtendedValue()});
                        } else {
                            row.push(v);
                        }
                    } else {
                        row.push(null);
                    }
                }
                rows.push(row);
            }
            return rows;
        }""", {
            "sheetId": sid,
            "startRow": ur['startRowIndex'],
            "endRow": ur['endRowIndex'],
            "startCol": ur['startColIndex'],
            "endCol": ur['endColIndex'],
        })
        
        all_data[meta['name']] = rows
    
    return all_data
```

## 与剪贴板 HTML 方案对比

| 维度 | getCellDataAtPosition | 剪贴板 HTML |
|------|----------------------|-------------|
| **数据源** | 内存直接读取 | 模拟键盘操作 |
| **稳定性** | ✅ 高（无 UI 交互） | ⚠️ 中（遮罩层、焦点、渲染时序） |
| **合并单元格** | ✅ 精确范围（getMergeReference） | ⚠️ colspan/rowspan 推断 |
| **图片 URL** | ✅ 原始大图 URL | ❌ 仅 base64 缩略图 |
| **性能** | ✅ <1ms/800 cells | ⚠️ ~5s/子表（Ctrl+A/C + 渲染） |
| **多子表** | 需逐 tab 切换（~5s/tab） | 需逐 tab 切换（~5s/tab） |
| **依赖** | 页面 JS runtime 已加载 | clipboard API 权限 |

## 结论

**`getCellDataAtPosition` 是 e3_ 电子表格读取的最佳方案**，替代剪贴板 HTML 作为主路径。
