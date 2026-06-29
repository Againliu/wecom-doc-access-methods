# e3_ 电子表格读取方案（v3.0 实测重构）

> 2026-06-15 v3.0 重大更新。基于 Super 棉田第六季 15 子表全量实测。
> 核心发现：e3_ 的 dop-api 返回 **protobuf 二进制**（非 JSON），v2.x 的 `_try_dop_for_spreadsheet` 从未真正跑通过。
> 新方案：JS Runtime 元数据（SpreadsheetApp.workbook）+ 剪贴板 HTML（colspan/rowspan）。

## 降级策略（v3.0）

```
Phase 0: JS Runtime 元数据（SpreadsheetApp.workbook → sheet 列表/名称/mergeList/图片URL）
  ↓ (总是执行，不阻塞)
Phase 1: 剪贴板 HTML 多子表遍历（Ctrl+A/C → read text/html → colspan/rowspan 解析）
  ↓ (失败时)
Phase 2: xlsx 导出（文件→导出为→xlsx → openpyxl merged_cells 解析）
  ↓ (失败时，需编辑权限)
Phase 3: 剪贴板 TSV（Ctrl+A/C → readText → 合并单元格丢失）
  ↓ (失败时)
Phase 4: DOM 文本兜底
```

## 策略选择决策树

| 文档特征 | 推荐策略 | 原因 |
|---------|---------|------|
| 任何 e3_ 文档 | **Phase 1（HTML）** | 15/15 测试通过，最稳定 |
| 大量合并单元格 | **Phase 1（HTML）** | colspan/rowspan 完整保留 |
| 多子表 + 复杂布局 | **Phase 1（HTML）** | 自动遍历 tab 栏 |
| 需要编辑权限导出 | **Phase 2（xlsx）** | 一个文件含所有 sheet |
| 含图片/附件列 | **Phase 1（HTML）+ Phase 0（JS Runtime）** | HTML 获取文字，JS Runtime 获取图片 URL |
| 最后兜底 | Phase 3/4 | 数据质量差，仅做参考 |

## Phase 0: JS Runtime 元数据（v3.0 新增）

**原理**: 从 `window.SpreadsheetApp.workbook` JS 运行时提取已解码的元数据。

**能获取什么**:
- 所有 sheet 的 ID 和名称（`worksheetManager.sheetList` + `getSheetNameBySheetId`）
- 合并单元格列表（`mergeManager.mergeList`，仅当前活跃 sheet）
- 图片 URL（`drawingManager.drawingMap`，递归搜索 `https://` 前缀）
- usedRange（startRow/endRow/startCol/endCol）

**不能获取什么**:
- Cell 数据（懒加载，只有当前活跃 sheet 有数据）
- 其他 sheet 的 mergeList（切换后才加载）

**实现要点**:
```javascript
const wb = window.SpreadsheetApp?.workbook;
const wm = wb.worksheetManager;
for (const sheet of wm.sheetList) {
    const sid = sheet.cellDataGrid?.usedRange?.sheetId;
    const name = wm.getSheetNameBySheetId(sid);
    const merges = sheet.mergeManager?.mergeList || [];
    // ...
}
```

**⚠️ 限制**: 需要页面完全加载后（8s+），等待 `SpreadsheetApp` 初始化。`SpreadsheetAppInitComplete` 全局变量可作就绪信号。

## Phase 1: 剪贴板 HTML（主力方案）

**原理**: Ctrl+A 全选 → Ctrl+C 复制 → `navigator.clipboard.read()` 读 `text/html` MIME → 解析 `<td colspan="N" rowspan="M">`。

**为什么是主力**:
- 15/15 子表测试全部通过（684 条记录）
- 合并单元格通过 colspan/rowspan 完整保留
- 多行文本通过 `<br>` 标签保留
- 不依赖 API 格式变化

**实现流程**:
```python
# 1. 获取 tab 列表
tab_names = [el.text for el in page.query_selector_all('.tab-bar-item-title')]

# 2. 逐个切换 + 提取
for name in tab_names:
    click_tab(name)
    await page.wait_for_timeout(5000)  # 等待 canvas 渲染
    await self._do_ctrl_a_c(page)      # 隐藏遮罩 + Ctrl+A/C
    html = await page.evaluate("navigator.clipboard.read()...")
    parsed = self._parse_html_table(html)  # HTML table → 二维 grid
```

**前置条件**:
- context 创建时授予 `permissions=["clipboard-read", "clipboard-write"]`
- 每次切换 tab 后重新隐藏 `.operate-board` 遮罩层
- 切换 tab 后等待 5s 确保 canvas 完全渲染

## Phase 2: xlsx 导出

**原理**: 触发"文件 → 导出为 → Excel (.xlsx)" → 下载 → openpyxl 解析。

**限制**: 需要编辑权限。只读文档会弹出权限申请弹窗，自动降级。

## Phase 3/4: TSV / DOM 兜底

**仅应急使用**。TSV 丢失合并单元格信息，DOM 只能获取可见区域文本。

## 🚨 实测关键发现（v3.0）

### e3_ dop-api 返回 protobuf 二进制

**2026-06-15 实测验证**（超级棉田第六季 `e3_AH0A9AZPAMsCNH7Cx5zluT9e1qOKP`）:

```
dop-api/get/sheet 响应:
{
  "data": {
    "initialAttributedText": {
      "text": [{
        "workbook": "eAGklN1PHF...",        // base64+zlib → protobuf
        "related_sheet": "eAGc2+t3G9d...",  // base64+zlib → protobuf (9092 chars)
        "max_row": 200, "max_col": 27,
        "smartsheet": ""                      // ← 空字符串！
      }]
    }
  }
}
```

**解压流程**:
```python
padded = raw + '=' * (4 - len(raw) % 4)
decoded = base64.urlsafe_b64decode(padded)
decompressed = zlib.decompress(decoded)  # 21470 bytes
# → protobuf 二进制，不是 JSON！
# 可见片段: "3.0.0", "宣传工作日志", "https://wdcdn.qpic.cn/..."
```

**结论**: v2.x 的 `_try_dop_for_spreadsheet` 试图 `JSON.parse(item.smartsheet)` → `smartsheet` 是空字符串 → 永远返回失败。这个代码路径从未真正跑通过。

### JS Runtime 替代方案

`SpreadsheetApp.workbook` 是浏览器端已经解码 protobuf 后的 JS 对象。用它获取元数据，用剪贴板 HTML 获取 cell 数据，是目前最稳定可靠的方案。

## 全量实测验证（v3.0）

### 测试文档：超级棉田第六季（15 子表）

**v3.0 实测结果（2026-06-15）**：

| 子表名 | sheetId | 行数 | 合并 | 方法 |
|--------|---------|------|------|------|
| 春播日志 | l3q67e | 186 | 1 | html |
| 灌溉日志 | a6hcp3 | 175 | 103 | html |
| 水肥计划 | qcjmbs | 26 | 1 | html |
| 植保记录 | pwdmmc | 13 | 5 | html |
| 植保计划 | lg9pwc | 14 | 26 | html |
| 农事服务清单 | p3w9or | 35 | 4 | html |
| 春播计划及日程 | yctqh6 | 8 | 0 | html |
| 小麦方案 | yghnuf | 26 | 0 | html |
| 肥料配送 | 8bfsrd | 9 | 9 | html |
| 生产资料运送清单 | zgsa2v | 21 | 10 | html |
| 采购清单 | 959h0w | 9 | 1 | html |
| 预算使用 | 9yhn08 | 24 | 0 | html |
| 用户服务日志 | ntkfgz | 95 | 0 | html |
| 灌溉压力表 | riqo5x | 27 | 4 | html |
| 宣传工作日志 | myx250 | 16 | 0 | vl-ocr |

**总计**: 15/15 子表成功，684 条记录，JS Runtime 正确匹配所有 sheetId。

## Pitfalls

1. **dop-api 对 e3_ 返回 protobuf，不是 JSON** — 不要试图 JSON.parse，直接走 JS Runtime 或剪贴板
2. **smartsheet 字段在 e3_ 中是空字符串** — 数据在 `related_sheet` 字段中
3. **JS Runtime 的 cell 数据是懒加载的** — 只有当前活跃 sheet 有完整 cell 数据，其他 sheet 的 usedRange 显示 `startRow=2147483647`（未加载）
4. **mergeList 也是懒加载的** — 切换 tab 后才会加载对应 sheet 的 mergeList
5. **剪贴板 HTML 的 colspan/rowspan 展开必须跳过已被占据的位置** — 用 `while (r, col_offset) in grid: col_offset += 1`
6. **tab 切换后遮罩会重新显示** — 每次切换后必须重新隐藏 `.operate-board`
7. **canvas 渲染需要时间** — 切换 tab 后等待 5s，否则剪贴板可能拿到空数据
8. **图片列的子表剪贴板只拿到 base64** — 需要原始 URL 时从 JS Runtime 的 drawingManager 获取
9. **`async_playwright()` 必须带括号** — 不是 `async_playwright`，是 `async_playwright()`
10. **`SpreadsheetApp` 初始化需要时间** — 页面加载后等 8s 再访问，或检查 `SpreadsheetAppInitComplete` 全局变量