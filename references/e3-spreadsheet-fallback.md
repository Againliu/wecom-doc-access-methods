# e3_ 电子表格五级降级读取方案

> 2026-06-15 v2 更新。新增剪贴板 HTML 和 xlsx 导出两个策略，解决合并单元格解析问题。
> e3_ 旧格式电子表格的单元格在 canvas 中渲染，无法直接从 DOM 提取单元格数据。
> 解决方案：五级降级策略，逐级尝试直到成功。

## 降级策略

```
策略1: dop-api 尝试（大多数 e3_ 文档返回 protobuf，无法解析）
  ↓ (失败时)
策略2: 剪贴板 HTML（Ctrl+A/C → read text/html → 解析 table 的 colspan/rowspan）
  ↓ (失败时)
策略3: xlsx 导出（触发文件→导出为→xlsx → openpyxl 解析，含 merged_cells）
  ↓ (失败时)
策略4: 剪贴板纯文本 TSV（Ctrl+A/C → readText → 解析 TSV，合并单元格信息丢失）
  ↓ (失败时)
策略5: DOM 文本兜底
```

## 策略选择决策树

| 文档特征 | 推荐策略 | 原因 |
|---------|---------|------|
| 简单表格（无合并单元格） | 策略2 或 4 即可 | TSV 就够用 |
| 大量合并单元格（日历/分组表头） | **策略2（HTML）或 3（xlsx）** | 需要 colspan/rowspan 信息 |
| 多子表 + 复杂布局 | **策略3（xlsx）** | 一个 xlsx 包含所有 sheet + 完整合并信息 |
| dop-api 可用（极少） | 策略1 | 结构化数据最好 |

**⚠️ 2026-06-15 踩坑反馈**：灌溉日志、施肥数据等使用大量合并单元格的子表，用纯文本 TSV（策略4）提取后列名/表头丢失、列错位严重。**必须**用策略2 或策略3 才能保留合并单元格结构。

## 策略1: dop-api 尝试

**原理**: 部分 e3_ 文档也支持 dop-api（和 s3_ 智能表格共享后端）。尝试用同样的 `dop-api/get/sheet` 接口读取。

**⚠️ 实测结论**: e3_ 的 dop-api 返回的 `related_sheet` 字段是 **zlib 压缩的 protobuf 二进制**（不是 JSON），无法直接解析。逆向 protobuf schema 成本极高，已放弃。
- 如果返回 `text[0].smartsheet` 且可 JSON.parse → 成功（极少数情况）
- 如果返回 `text[0].related_sheet`（base64 二进制）→ **放弃**，直接降级到策略2

## 策略2: 剪贴板 HTML 提取（新增 v2 — 解决合并单元格问题）

**原理**: Ctrl+A 全选 → Ctrl+C 复制 → `navigator.clipboard.read()` 读 `text/html` MIME 类型 → 解析 HTML `<table>` 中的 `colspan`/`rowspan` 属性。

**为什么能解决合并单元格问题**：
- 企微电子表格在复制时，剪贴板同时包含 `text/plain`（TSV）和 `text/html`（HTML table）两种格式
- HTML 格式中，合并单元格表示为 `<td colspan="3" rowspan="2">值</td>`
- 解析 colspan/rowspan 后可以还原完整的二维矩阵，每个合并区域内的单元格都填充相同的值

**实现要点**：

```python
# 1. Ctrl+A + Ctrl+C（公共方法 _do_ctrl_a_c）
await self._do_ctrl_a_c(page)

# 2. 读剪贴板 HTML 格式（需要 clipboard-read 权限）
html_content = await page.evaluate("""async () => {
    const items = await navigator.clipboard.read();
    for (const item of items) {
        if (item.types.includes('text/html')) {
            const blob = await item.getType('text/html');
            return await blob.text();
        }
    }
    return null;
}""")

# 3. 用 Python html.parser 解析 table
# 4. 展开 colspan/rowspan 为二维 grid: {(row, col): value}
# 5. 第 0 行作为表头，后续行作为数据
# 6. 输出 merged_cells 列表（供下游感知合并结构）
```

**成功条件**: 剪贴板有 `text/html` MIME 类型且内容包含 `<table>` 标签。

**失败场景**：
- 企微电子表格可能不输出 HTML 格式（只输出纯文本）→ 降级到策略3
- `navigator.clipboard.read()` API 在 headless Chromium 中可能受限 → 降级到策略3

## 策略3: xlsx 导出（新增 v2 — 最完整的方案）

**原理**: 通过 Playwright 触发"文件 → 导出为 → Excel (.xlsx)"菜单，下载 xlsx 文件，用 openpyxl 解析。

**优势**：
- **完整保留合并单元格**：openpyxl 的 `ws.merged_cells.ranges` 给出精确的合并范围
- **所有子表在一个文件中**：不需要逐个 tab 切换
- **公式值**：`data_only=True` 获取计算后的值
- **格式信息**：可以获取字体、对齐、边框等（如果下游需要）

**实现要点**：

```python
# 1. Playwright expect_download + 点击导出菜单
async with page.expect_download(timeout=60000) as download_info:
    # 尝试多种选择器: "文件" → "导出为" → "Excel"/"xlsx"
    # 或: "..." → "导出" → "xlsx"

download = await download_info.value
tmp_path = await download.path()

# 2. openpyxl 解析
import openpyxl
wb = openpyxl.load_workbook(tmp_path, data_only=True)
for sheet_name in wb.sheetnames:
    ws = wb[sheet_name]
    # 合并单元格映射
    merged_map = {}
    for mr in ws.merged_cells.ranges:
        top_left_val = ws.cell(mr.min_row, mr.min_col).value
        for r in range(mr.min_row, mr.max_row + 1):
            for c in range(mr.min_col, mr.max_col + 1):
                merged_map[(r, c)] = top_left_val
    # 逐行提取，合并区域内的空值用 merged_map 填充
```

**成功条件**: 成功触发下载 + xlsx 文件有效。

**失败场景**：
- 导出菜单 UI 变化（选择器失效）→ 降级到策略4
- 下载超时（60s）→ 降级到策略4
- xlsx 文件损坏 → 降级到策略4

## 策略4: 剪贴板纯文本 TSV 兜底

**原理**: Ctrl+A 全选 → Ctrl+C 复制 → `navigator.clipboard.readText()` → 解析 TSV。

**⚠️ 已知问题**：
- **合并单元格丢失**：TSV 中合并区域只有左上角有值，其余为空
- **列名混入数据行**：合并的表头展开后变成了数据行的值
- **多行文本截断**：TSV 用换行分隔行，单元格内换行会被当作新行

**成功条件**: 剪贴板内容非空且可解析为 TSV 格式。

## 策略5: DOM 文本兜底

**原理**: 用通用 DOM 选择器提取页面可见文本。

**限制**: 无法提取单元格结构化数据。返回 `warning` 字段建议用户导出 CSV。

## 返回值格式

```json
{
    "success": true,
    "doc_type": "e3",
    "method": "dop-api" | "clipboard-html" | "xlsx-export" | "clipboard-tsv" | "dom-fallback",
    "title": "文档标题",
    "url": "https://...",
    "total": 228,
    "records": [{"_record_id": "...", "字段名": "值", ...}],
    "merged_cells": [{"start_row": 0, "start_col": 0, "colspan": 3, "rowspan": 1, "value": "合并值"}],
    "sheets": {"子表名": {"rows": [...], "merged_ranges": ["A1:C3"], ...}},
    "warning": "仅在使用低优先级策略时出现"
}
```

## 前置条件（所有剪贴板策略共用）

1. **授予剪贴板权限**: context 创建时加 `permissions=['clipboard-read', 'clipboard-write']`
2. **隐藏遮罩层**: 用 JS 隐藏 `.operate-board`
3. **用 mouse.click 点击视口中心**: 不要用 `canvas.click()`

```python
ctx = await browser.new_context(
    storage_state=state_file,
    viewport={"width": 1920, "height": 1080},
    permissions=["clipboard-read", "clipboard-write"],
)
```

## Pitfalls

1. **e3_ dop-api 返回 protobuf** — 不是 JSON，无法直接解析，不要浪费精力逆向
2. **剪贴板 HTML 可能不存在** — 不是所有 web 表格都会输出 HTML 格式到剪贴板
3. **xlsx 导出的菜单选择器可能变化** — 需要用多种选择器尝试
4. **合并单元格展开后的列对齐** — HTML 的 colspan/rowspan 展开必须跳过已被 rowspan 占据的位置
5. **多行文本单元格** — TSV 会把它当新行，HTML 中用 `<br>` 表示
6. **tab 切换后遮罩会重新显示** — 每次切换子表后必须重新隐藏 operate-board
7. **最后一个子表可能 0 行** — 如果 tab 栏有横向滚动

## 验证方法

### 测试文档：超级棉田第六季（e3_AH0A9AZPAMsCNH7Cx5zluT9e1qOKP，15 子表）

**v2.7.0 实测验证（2026-06-15）**：
- **HTML 策略命中** ✅ — clipboard-html 作为主力方案成功
- 灌溉日志（合并单元格最复杂的子表）：
  - 175 行（vs TSV 的 570 行，大量空行）
  - 100 个有效表头（日期列完整：3月24日、3月25日、4月8日...）
  - 103 个合并单元格正确还原（colspan/rowspan）
  - 24 个地块正确识别（1-1地块、1-3西、1-4中...）
  - 0 空行（TSV 有大量空行）
  - 多行文本完整保留（"灌溉时长5小时\n维修跑冒滴漏"）
  - 每个地块 7 行子结构保留（时间 + N/P/K/G/水方量/备注）
- 总耗时 ~32s（页面加载 14s + 提取解析 18s）
- xlsx 导出路径需要编辑权限，只读文档会自动降级到 HTML/TSV

**v1（纯 TSV）的问题（已被 v2.7.0 解决）**：
- ❌ 列名/表头丢失 → ✅ HTML colspan 保留表头
- ❌ 数据错位/张冠李戴 → ✅ grid 展开后列对齐正确
- ❌ 子表内嵌子结构丢失 → ✅ rowspan 保留地块分组
- ❌ 大量空列/空行 → ✅ 0 空行
