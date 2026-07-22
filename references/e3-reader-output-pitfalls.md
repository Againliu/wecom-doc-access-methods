# e3 电子表格读取：运行与解析 Pitfall（2026-07-20 实测）

## 模块找不到

`python3 -m wecom_doc_reader read <user_id> <url>` 报 `No module named wecom_doc_reader`。包在 `./scripts/wecom_doc_reader/`，但默认 `sys.path` 不含该目录。

```bash
PYTHONPATH=./scripts python3 -m wecom_doc_reader read <user_id> <url> > /tmp/wecom_sheet_e3.json
```

## 输出前缀有日志行，JSON 不在文件开头

输出文件开头是 `JS Runtime: 2 sheets\n  [1/2] 工作排期 (BB08J2)\n ...`，后面才是 JSON。直接 `json.load(open(p))` 报 `Expecting value: line 1 column 3`。

```python
s = open(p, encoding='utf-8').read()
data = json.loads(s[s.find('{'):])
```

## headers ≠ 实际表头；空行多

`headers` 来自第一行，可能是合并长标题（如「P系列文档排期：一轮优化…」）。实际表头常是第一个非空数据行（如「类型阶段, 内容范围, 预估人时+0.5冗余, DDL（暂定）」）。

插入飞书表格前应：
1. 过滤全空行（`any(v.strip() for v in row.values())`）。
2. 用第一个非空行作为表头，其余非空行作为数据行。
3. 单元格内 `\n` 换成 `<br>`，转义 `|`，避免破坏 Markdown 表格。

## tab 参数未必切到目标子表

URL 带 `&tab=BB08J2` 时，reader 仍可能读到所有子表，最终 `url` 字段里的 tab 可能是最后一个子表。按 `sheetId` 在 `sheets` dict 里定位目标子表，不要依赖 `url` 字段。
