# dop-api 数据结构完整参考

## 三种响应格式（2026-06-14 实测更新）

### 格式 A: startrow=0 主动 fetch（✅ 推荐方式）
**来源**: `page.evaluate(fetch('dop-api/get/sheet?...startrow=0&endrow=99999...'))` 
**外层结构**: `response.data.initialAttributedText.text[0]` 是一个包装对象：
```json
{
  "smartsheet": "[[{\"t\":3005,...},{\"t\":3028,...}]]",  // ← JSON 字符串，需 JSON.parse()
  "workbook": "[{\"id\":\"q979lj\",\"name\":\"表1\",\"hidden\":false},...]",  // JSON 字符串
  "total_record_count": 2932,
  "max_row": 2932,
  "start_row_index": 0,
  "end_row_index": 2932
}
```
**⚠️ 关键**: `smartsheet` 字段是 **JSON 字符串**（不是 base64），需要 `JSON.parse()`。解析后得到 `[[{t:3005,...}, {t:3028,...}]]`（双层数组，取 `[0]`）。

```python
# JS 端解析
parsed = JSON.parse(item.smartsheet)  // [[items...]]
items = parsed[0] if isinstance(parsed[0], list) else parsed
# items = [{t:3005, c:{...}}, {t:3028, c:{...}}]
```

解析后内部结构（数字键）：
```json
{
  "t": 3028, "v": 5,
  "c": {
    "1": "sheet_id",
    "2": {
      "1": { ... },      // 行数据（record_id → cell data）
      "2": { ... },      // 元数据
      "3": { ... },      // 视图
      "5": { ... }       // 字段顺序
    }
  }
}
```

### 格式 B: base64+zlib 压缩（k 前缀键）
**来源**: `dop-api/opendoc` 响应 + 页面自动加载的 `get/sheet` 响应
```python
# 解码步骤
padded = raw + '=' * (4 - len(raw) % 4)
decoded = base64.urlsafe_b64decode(padded)  # ⚠️ 必须 urlsafe
decompressed = zlib.decompress(decoded)      # ⚠️ 默认参数，不传 wbits
data = json.loads(decompressed)
```

## 行数据提取路径

| 格式 | 来源 | 行数据位置 | 列选项映射来源 | 需要解压 |
|------|------|-----------|---------------|---------|
| **startrow=0 JSON** | 主动 fetch | `JSON.parse(text[0].smartsheet)[0]` → 找 t=3028 → `.c.2.1` | t=3005 项的 `.c.3.3` | ❌ JSON.parse 即可 |
| startrow=61+ 纯 JSON | 拦截（旧方式） | `parsed[0][1].c.2.1` | t=3005 项的 `c.3.3` | ❌ |
| base64+zlib | opendoc 拦截 | `parsed[0][0].c.k2.k1` | t=3005 项的 `c.k3.k3` | ✅ urlsafe_b64decode + zlib |

**⚠️ 推荐**: 始终使用 startrow=0 主动 fetch 方式。返回纯 JSON 字符串，无需解压，全量数据。

## 列类型 ID（k31）— 2026-06-15 实测验证

| k31 值 | 类型 | 值提取方式 | 验证状态 |
|--------|------|-----------|---------|
| 1 | 文本 | `cell.1` → list of {1:"text",2:"value"} | ✅ 2932条实测 |
| 2 | 数字 | `cell.2` → 数值 | ✅ 测试表验证 |
| 5 | 日期 | `cell.5` → 毫秒时间戳 | ✅ 测试表验证 |
| 6 | 复选框 | `cell.6` → boolean | ⚠️ 待验证 |
| 10 | 创建人 | `cell.10` → list of user_ids → 用 user_map 映射 | ✅ 测试表验证 |
| 11 | 最后编辑人 | `cell.11` → list of user_ids | ✅ 测试表验证 |
| 12 | 创建时间 | `cell.12` → 毫秒时间戳 → `datetime.fromtimestamp(ts/1000)` | ✅ 测试表验证 |
| 13 | 最后编辑时间 | `cell.13` → 毫秒时间戳 | ✅ 测试表验证 |
| 17 | 单选 | `cell.17` → list of option_ids → 用 select_options 映射 | ✅ 2932条实测 |
| 19 | 公式/引用 | `cell.19` → k36 → JSON string → parse → data[].text | ✅ 2932条实测 |
| ? | 图片 | 待确认 k31 值，预计含原始 URL | ⚠️ 待实测（"宣传工作日志"等含图片列的子表） |
| ? | 附件 | 待确认 k31 值 | ⚠️ 待实测 |

**⚠️ 重要纠正（2026-06-15）**：
- 旧版文档写的 `SELECT=3` 是**错误的**，实测发现 k31=17 才是单选
- 数字、日期、URL 等类型的 k31 值与键名**一致**（k31=2 对应 key "2"）
- 代码中应使用 k31=17 作为单选字段

## ⚠️ e3_ 电子表格 dop-api 数据结构（🚨 v3.0 实测确认：protobuf 二进制）

**🚨 2026-06-15 v3.0 实测确认：e3_ 的 dop-api 返回 protobuf 二进制格式，不是 JSON。**

| 特征 | s3_ 智能表格 | e3_ 电子表格 |
|------|------------|-------------|
| 数据格式 | JSON 字符串（`smartsheet` 字段） | **protobuf 二进制**（`related_sheet` 字段，base64+zlib） |
| `smartsheet` 字段 | 有值（JSON 字符串） | **空字符串** |
| `related_sheet` 字段 | 通常不存在 | **有值**（base64+zlib → protobuf） |
| 解压后 | JSON.parse 即可 | protobuf 二进制，需逆向 schema |
| 列定义 | t=3005 项含字段名、类型、选项映射 | 无独立列定义 |
| 合并单元格 | 无（s3_ 不支持） | 有独立数据结构 |

**实测证据**（超级棉田第六季 `e3_AH0A9AZPAMsCNH7Cx5zluT9e1qOKP`）:
```json
{
  "data": {
    "initialAttributedText": {
      "text": [{
        "workbook": "eAGklN1PHF...",        // base64+zlib → protobuf (1428 chars)
        "related_sheet": "eAGc2+t3G9d...",  // base64+zlib → protobuf (9092 chars)
        "max_row": 200, "max_col": 27,
        "smartsheet": ""                      // ← 空！v2.x 代码在这里 JSON.parse("") → 失败
      }]
    }
  }
}
```

**解压后可见**:
- 中文 sheet 名（"宣传工作日志"、"春播日志"等）
- 图片原始 URL（`https://wdcdn.qpic.cn/MTY4ODg1NTAzNzYxNzc5Mw_644504_xZ2ae4mzAc_eWi2A_1780378457`）
- 版本号（"3.0.0"）
- 但整体是 protobuf 二进制格式，无法直接 json.loads

**替代方案（v3.0）**:
- JS Runtime `SpreadsheetApp.workbook` 提供浏览器端已解码的元数据
- 剪贴板 HTML 提供完整 cell 数据（含 colspan/rowspan 合并单元格）
- 详见 `references/e3-spreadsheet-fallback.md`

## 列定义结构（t=3005 项）

```json
{
  "field_id_example": {
    "30": "列名",
    "31": 1              // 列类型 ID
  },
  "select_field_id": {
    "30": "模块",
    "31": 17,            // 17 = 单选
    "17": {              // 选项列表
      "1": false,
      "2": true,
      "3": [
        {"1": "option_id_1", "2": "选项文本1", "3": 10},
        {"1": "option_id_2", "2": "选项文本2", "3": 10}
      ]
    }
  }
}
```

### 选项映射提取

```python
def extract_select_options(parsed_data):
    """从 t=3005 列定义项提取所有 select 选项映射"""
    select_options = {}  # {field_id: {option_id: option_text}}
    col_meta = None
    for item in parsed_data[0] if isinstance(parsed_data, list) else parsed_data.get('0', []):
        if isinstance(item, dict) and item.get('t') == 3005:
            col_meta = item
            break
    if not col_meta:
        return select_options
    c = col_meta.get('c', {})
    field_defs = c.get('3', c.get('k3', {})).get('3', c.get('3', c.get('k3', {})))
    for fid, fmeta in field_defs.items():
        k17 = fmeta.get('17', fmeta.get('k17'))
        if k17 and isinstance(k17, dict):
            k3 = k17.get('3', k17.get('k3'))
            if k3 and isinstance(k3, list):
                select_options[fid] = {
                    opt.get('1', opt.get('k1', '')): opt.get('2', opt.get('k2', ''))
                    for opt in k3
                }
    return select_options
```

## 用户映射（t=3005 项 → c.3.5）

```json
{
  "user_id_1": {"2": "姓名", "6": "公司名"},
  "user_id_2": {"2": "姓名", "6": "公司名"}
}
```

## endrow 实测

| endrow 参数 | 实际返回 | 结论 |
|-------------|---------|------|
| 5000 | 4.80 MB | ✅ |
| 10000 | 4.80 MB | ✅ 一样 |
| 50000 | 4.80 MB | ✅ 一样 |

**结论**: endrow 只是上限，API 自动返回实际全量。设 99999 覆盖到 5 万条没问题。

## API URL 模板

```
https://doc.weixin.qq.com/dop-api/get/sheet?padId={doc_id}&subId={sheet_id}&startrow=0&endrow=99999&outformat=1&normal=1
https://doc.weixin.qq.com/dop-api/opendoc?padId={doc_id}&normal=1&outformat=1
https://doc.weixin.qq.com/dop-api/get/mind?padId={doc_id}&normal=1
```

- `padId`: 从 URL 提取，如 `s3_AGIAUQZXAMsNWHo29sdQP61ssahQL`
- `subId`: 子表 ID（仅 get/sheet 需要）
- `startrow=0`: **必须**（仅 get/sheet），否则只拿部分数据
- 需要通过 `page.evaluate(fetch(..., {credentials: 'include'}))` 调用，自动带 cookies

## 新建子表延迟问题（2026-06-14）

通过 MCP `smartsheet_add_sheet` 新建的子表，dop-api 可能需要几分钟才能索引。
- 新建后立刻 fetch 会返回 `"no text item"` 或 `"invalid sheet id"`
- 等 2-5 分钟后重试即可

## 多子表遍历模式（v2.0，2026-06-15）

### 完整流程

```python
# 1. 第一次 fetch（用 current_tab，即页面默认 tab）
#    获取 workbook 列表 + 第一个子表的数据
api_url = f"...dop-api/get/sheet?padId={doc_id}&subId={current_tab}&startrow=0&endrow=99999..."
first_result = await page.evaluate(fetch_js, api_url)

# 2. 解析 workbook
workbook = json.loads(first_result['workbook_json'])
# [{"id": "q979lj", "name": "表1", "hidden": false}, ...]

# 3. 决定读取哪些子表
if user_specified_sheet_id:
    sheets_to_read = [user_specified_sheet_id]  # 用户指定了，只读一个
else:
    sheets_to_read = [wb['id'] for wb in workbook if not wb.get('hidden')]

# 4. 遍历所有子表
for sid in sheets_to_read:
    if sid == current_tab:
        # 已经 fetch 过了，直接用 first_result
        parsed = first_result['parsed']
    else:
        # 单独 fetch 这个子表
        api_url = f"...&subId={sid}..."
        result = await page.evaluate(fetch_js, api_url)
        parsed = result['parsed']
    # 解析数据...
```

### ⚠️ `current_tab` vs `sheet_id` 区分

```python
# 页面加载后 URL 可能自动追加 &tab=xxx
current_tab = sheet_id  # 用户指定的（可能为 None）
if not current_tab:
    # 从页面 URL 提取自动追加的 tab
    page_query = parse_qs(urlparse(page.url).query)
    current_tab = page_query.get("tab", [None])[0]

# current_tab: 用于第一次 fetch（必须有值）
# sheet_id: 用于判断用户意图（None = 读所有，非 None = 读指定）
```

**错误做法**：把页面自动追加的 tab 赋值给 `sheet_id` → 导致只读一个子表
**正确做法**：`current_tab` 和 `sheet_id` 是两个独立变量

### ⚠️ `async with` 作用域

多子表遍历循环**必须**在 `async with async_playwright()` 块内部。常见错误：

```python
# ❌ 错误：循环在 async with 外面
async with async_playwright() as p:
    browser = ...
    first_result = await page.evaluate(...)
    await browser.close()  # browser 关闭了

# 循环在 async with 外面 → TargetClosedError
for sid in sheets_to_read:
    result = await page.evaluate(...)  # 💥 page 已关闭
```

```python
# ✅ 正确：所有操作在 async with 内部
async with async_playwright() as p:
    browser = ...
    first_result = await page.evaluate(...)
    
    for sid in sheets_to_read:
        if sid != current_tab:
            result = await page.evaluate(...)
    
    await browser.close()  # 最后才关闭
```
