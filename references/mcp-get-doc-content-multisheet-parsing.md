# MCP get_doc_content 多子表 Markdown 解析参考

## 适用场景

当使用 MCP `get_doc_content(type=2, url=...)` 读取企微智能表格时，API 返回的是**整个文档的 Markdown 纯文本**，包含所有子表拼接在一起。与 `smartsheet_get_records`（结构化 JSON，单子表）不同，此路径需要自己解析 Markdown 表格。

**何时用此路径**：
- 需要一次性拿到所有子表数据（`smartsheet_get_records` 需要逐个子表查询）
- 只需要快速浏览/分析内容，不需要精确字段类型
- MCP 授权有效但不需要写操作

## 核心发现（2026-06-29 实测）

### 1. 子表标记格式

`get_doc_content` 返回的 Markdown 中，每个子表以标题行开头：

```markdown
## 子表名称
| 列1 | 列2 | 列3 |
| --- | --- | --- |
| 数据1 | 数据2 | 数据3 |
```

- 子表名称通常包含日期段（如"2026年1月23日-1月29日"）
- 用 `grep -n '^## '` 可以定位所有子表的起始行号

### 2. 不同子表列数不同（🚨 最大陷阱）

**同一个智能表格文档的不同子表，列数和列名可能完全不同。**

实测案例（技术工单表，24个子表）：

| 子表日期段 | 列数 | 格式特征 |
|---|---|---|
| 2025年12月 | 25列 | 旧格式：工单系统状态/编号/来源/处理员工/创建时间/产品线一级~五级/设备序列号/问题描述/故障类型/是否升级研发 |
| 2026年1月30日-4月16日 | 31-39列 | 过渡格式：旧格式 + 工单处理总时长等新增列 |
| 2026年4月17日-6月25日 | 12-14列 | 新格式：工单ID/主题/状态/提单人/来源/产品线/故障类型/故障模块或产品模块/序列号/处理人/创建时间/故障分析和解决方案 |

**错误做法**：假设所有子表列数相同，用固定列数解析 → 数据丢失或列错位

**正确做法**：逐个子表独立解析表头，按该子表的表头映射列索引

### 3. 单元格内 `|` 字符导致列错位（🚨 第二大陷阱）

Markdown 表格用 `|` 分隔列，但单元格内容中如果包含 `|` 字符（如"模块A|模块B"），会导致该行被拆分成额外的列。

**影响范围**：31-39列的旧格式子表受影响最严重（问题描述列经常含 `|`），12-14列的新格式子表基本不受影响（故障分析列多为纯文本）。

**表现**：解析后该行列数 > 表头列数，按表头映射时多余列被丢弃，但关键字段（如"来源"在 col[4]）可能被挤到错误位置。

**缓解方案**：
- 检测每行列数是否 = 表头列数 + 1（多了1个分隔符 = 单元格内含1个 `|`）
- 对受影响的行，尝试合并末尾的多余列（`" | ".join(extra_cols)`）
- 如果大量行受影响（>30%），考虑用 CSV 解析替代 Markdown 管道符解析（先替换 `|` 为制表符）
- 在报告中标注"此子表分类可能不准"

### 4. 排序子表标记后再解析会破坏边界计算（🚨 第三大陷阱）

**错误流程**：
1. `grep -n '^## '` 拿到所有子表标记的行号
2. 按日期排序标记
3. 用排序后的相邻标记计算每个子表的范围（start_line = 当前标记行号, end_line = 下一个标记行号 - 1）

**为什么错**：排序后相邻的标记在原文中可能不相邻。例如排序后"1月23日"后面跟"1月30日"，但在原文中"1月23日"后面跟的是"2月5日"。`end_line` = "1月30日"的行号 - 1，但"1月30日"在原文中的位置可能在"1月23日"之前 → `end_line < start_line` → 该子表范围为空或负。

**正确流程**：
1. `grep -n '^## '` 拿到所有子表标记的行号（**保持原始顺序**）
2. 按原始顺序计算每个子表的范围
3. 解析每个子表的数据
4. 解析完成后再按日期排序输出结果

### 5. 重复子表

实测发现某些子表数据完全重复（工单ID、内容完全一致）。可能是表格维护者在新建子表时复制了上一个子表的数据但忘记更新。

**处理方式**：检测重复（按工单ID或首列唯一键），在报告中标注"与X子表数据重复"，不计入总数。

### 6. 列名模糊匹配

不同格式子表的列名可能不同但语义相同：

| 新格式列名 | 旧格式列名 | 语义 |
|---|---|---|
| 故障模块 | 产品模块 | 故障所属模块 |
| 工单ID | 编号 | 工单编号 |
| 主题 | (无) | 工单标题 |
| 处理人 | 处理员工 | 处理人 |

**做法**：用模糊匹配（`in` 或正则）匹配列名，不要求精确匹配。例如 `"模块" in header` 可同时匹配"故障模块"和"产品模块"。

## 解析脚本模板

```python
import re

def parse_multisheet_markdown(markdown_text):
    """解析 get_doc_content 返回的多子表 Markdown"""
    lines = markdown_text.split('\n')
    
    # 1. 找所有子表标记（保持原始顺序）
    sheet_markers = []
    for i, line in enumerate(lines):
        if line.startswith('## '):
            sheet_markers.append((i, line.strip('# ').strip()))
    
    # 2. 按原始顺序计算每个子表范围
    sheets = []
    for idx, (start, name) in enumerate(sheet_markers):
        end = sheet_markers[idx + 1][0] if idx + 1 < len(sheet_markers) else len(lines)
        sheet_lines = lines[start + 1 : end]  # 跳过标记行
        sheets.append((name, sheet_lines))
    
    # 3. 逐个子表解析
    results = []
    for sheet_name, sheet_lines in sheets:
        records = parse_single_sheet(sheet_lines, sheet_name)
        results.append({
            'sheet_name': sheet_name,
            'record_count': len(records),
            'records': records
        })
    
    # 4. 解析完成后再排序输出
    results.sort(key=lambda x: extract_date_from_name(x['sheet_name']))
    return results

def parse_single_sheet(sheet_lines, sheet_name):
    """解析单个子表的 Markdown 表格"""
    # 找表头行（第一个 | 开头的行）
    header_idx = None
    for i, line in enumerate(sheet_lines):
        if line.strip().startswith('|'):
            header_idx = i
            break
    
    if header_idx is None:
        return []
    
    headers = [h.strip() for h in sheet_lines[header_idx].split('|')][1:-1]
    # 跳过分隔行 (| --- | --- |)
    data_start = header_idx + 2
    
    records = []
    for line in sheet_lines[data_start:]:
        if not line.strip().startswith('|'):
            continue
        cells = [c.strip() for c in line.split('|')][1:-1]
        
        # 检测列错位
        if len(cells) > len(headers):
            # 合并多余的列到最后一列
            extra = cells[len(headers) - 1:]
            cells = cells[:len(headers) - 1] + [' | '.join(extra)]
        elif len(cells) < len(headers):
            cells.extend([''] * (len(headers) - len(cells)))
        
        record = dict(zip(headers, cells))
        record['_sheet_name'] = sheet_name
        records.append(record)
    
    return records

def extract_date_from_name(name):
    """从子表名提取日期用于排序"""
    # 匹配 "2026年1月23日-1月29日" 或 "2026年1月23日"
    dates = re.findall(r'(\d{4})年(\d{1,2})月(\d{1,2})日', name)
    if dates:
        y, m, d = dates[0]
        return f"{y}{int(m):02d}{int(d):02d}"
    return "99999999"  # 无日期的排到最后
```

## 数据质量检查清单

解析多子表 Markdown 后，必须检查：

1. **行数合理性**：各子表行数是否在合理范围（0-500行/子表）
2. **列数一致性**：同一格式子表的列数是否一致
3. **列错位检测**：有多少行的列数 > 表头列数（`|` 字符导致）
4. **重复检测**：不同子表间是否有完全重复的记录
5. **空值检测**：关键字段（如工单ID、来源）是否有大量空值
6. **分类准确性**：如果用于分类，检查"其他"类别占比是否异常高（可能是列错位导致分类字段读不到）

## 与 smartsheet_get_records 的对比

| 维度 | get_doc_content (Markdown) | smartsheet_get_records (JSON) |
|---|---|---|
| 数据格式 | Markdown 纯文本 | 结构化 JSON |
| 多子表 | 一次返回所有子表拼接 | 需要逐个子表查询（sheet_id） |
| 字段类型 | 全部为字符串 | 保留原始类型（数字/日期/单选等） |
| 列错位风险 | 高（`|` 字符） | 无 |
| 数据完整性 | 中（依赖 Markdown 解析质量） | 高（API 保证） |
| 适用场景 | 快速浏览/分析/分类汇总 | 精确同步/写操作 |
| 条数限制 | 无（返回全文） | 2000条/子表 |
