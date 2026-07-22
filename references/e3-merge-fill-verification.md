# e3_ 合并单元格填充验证方法论

## 背景

v4.0.0 报告"15/15 成功、1443 条、226 合并、9 图片"，但团队负责人追问"你怎么知道每个单元格的值是对的？"——答不上来。表面指标只能证明程序跑通，不能证明数据正确。

## 根因：mergeList 行号偏移

- mergeList 从 `sheet.mergeManager.mergeList` 获取，行号是 **sheet 级别**（0 = 表头行）
- records 数组是 **数据级别**（0 = 第一条数据 = sheet row 1）
- 直接当索引用会差 1 → 合并单元格全部未填充

## 验证方法：三层递进

### 1. 表面指标（快速筛查，不证明正确）

```
子表数、总行数、总合并数、总图片数、None/dict/空表头数
```

### 2. Spot-check 合并填充（核心验证）

选取合并密集的子表（如灌溉日志），检查第一列（通常是被合并的列，如"地块名"）：

```python
for m in merge_list:
    sr, er, sc = m['startRow'], m['endRow'], m['startCol']
    fill_val = records[sr - 1][headers[sc]]  # sheet row → data index
    for sheet_r in range(sr, er + 1):
        actual = records[sheet_r - 1][headers[sc]]
        assert actual == fill_val, f"row {sheet_r}: expected '{fill_val}', got '{actual}'"
```

### 3. Ground-truth 对照（终极验证）

- 导出前 20 行 CSV
- 肉眼/程序对比原始文档的对应单元格
- 检查项：表头日期、合并区域边界、图片 URL 可访问性、公式计算结果

## 典型误判

| 表现 | 是否 bug | 原因 |
|------|---------|------|
| col_0 在某些行是空 | 否 | 原表该合并起始格就是空的（用户没填） |
| 表格末尾很多空行 | 否 | usedRange 包含未使用的底部行 |
| 100 列但只有 50 列有数据 | 否 | 原表列宽设得大，很多列是空的 |

## 验证脚本模板

参见 `scripts/validate_extraction.py`（通用版）和本次会话中使用的 `/tmp/spot_check.py`（合并填充专项）。