# e3_ 电子表格浏览器写入 API 调研（2026-07-22）

## 状态：进行中

浏览器写入路径的关键 API 已发现，但值格式 + 服务端保存机制仍需探测。

## 已发现的写入 API

通过 Playwright 打开测试电子表格，探测 `SpreadsheetApp` JS 运行时，发现以下写入方法：

### Sheet 对象写入方法

| 方法 | 参数 | 说明 |
|------|------|------|
| `setCellDataAtPosition(row, col, value)` | (int, int, cellObj) | 写入单元格值（对应读取的 `getCellDataAtPosition`） |
| `insertDimension(...)` | 待测 | 插入行/列 |
| `deleteDimension(...)` | 待测 | 删除行/列 |
| `setRowProperty(...)` | 待测 | 设置行属性 |
| `setColProperty(...)` | 待测 | 设置列属性 |
| `setSheetName(name)` | (string) | 重命名子表 |
| `resetRowCount(n)` | (int) | 设置行数 |
| `resetColCount(n)` | (int) | 设置列数 |
| `setPicture(...)` | 待测 | 插入图片 |

### `setCellDataAtPosition` 函数签名

```javascript
function(e, t, n) { this.cellDataGrid.set(e, t, n) }
```

- 3 个参数：row(int), col(int), value(cellObj)
- 内部调用 `cellDataGrid.set(row, col, value)`
- **值格式不是原始字符串**——传 `"hello"` 后 `getCellDataAtPosition().getValue()` 报 `not a function`，说明值需要是特定 cell 对象结构

### Cell 对象

Cell 对象**没有写入方法**（`getValue`, `getType`, `getMergeReference` 等全部只读）。写入操作在 Sheet 层级。

## 待解决问题

1. **值格式**：`setCellDataAtPosition` 的第三个参数需要什么结构？可能是 `{v: "value", t: 4}`（type 4=string）或完整的 cell 对象。需要检查 `cellDataGrid.set` 的实现。
2. **服务端保存**：调用 `setCellDataAtPosition` 后**没有触发 POST 请求**。数据只写入本地内存。需要找到 save/commit/flush 机制：
   - 可能是 workbook 级的 `save()` 方法（未在探测中发现）
   - 可能是通过 changeset/delta 机制（拦截手动编辑时的网络请求来发现）
   - 可能需要触发 UI 事件（如切换 tab、关闭页面）来触发保存
3. **insertDimension / deleteDimension 的参数格式**：用于插入/删除行列，需要探测。

## 下一步

1. 拦截手动编辑（在浏览器里输入一个字符）时的网络请求，发现保存 API
2. 检查 `cellDataGrid.set` 的完整实现，确定值格式
3. 测试 `insertDimension` / `deleteDimension` 的参数
4. 实现浏览器写入函数并测试端到端

## 测试文档

- 测试电子表格（可删）：`https://doc.weixin.qq.com/sheet/e3_AMgAkng0AMMCN8zGRYGZ1StqUJZMn_a`
