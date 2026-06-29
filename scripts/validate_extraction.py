#!/usr/bin/env python3
"""
e3_ 电子表格提取结果 vs 原始文档 ground-truth 验证脚本。
用法：
  1. 先跑 wecom_doc_reader.py 的 read() 拿到全量数据
  2. 用本脚本导出指定子表的前 N 行为 CSV
  3. 人工对照原始企微文档中对应位置的值，确认一致性

用法示例：
  python3 validate_extraction.py --data result.json --sheet "灌溉日志" --rows 20
  python3 validate_extraction.py --data result.json --sheet "春播日志" --rows 10 --csv /tmp/spring_log.csv
"""
import json, csv, sys, argparse

def main():
    parser = argparse.ArgumentParser(description="验证 e3_ 表格提取结果")
    parser.add_argument("--data", required=True, help="wecom_doc_reader.py read 输出的 JSON 文件路径")
    parser.add_argument("--sheet", required=True, help="要验证的子表名称")
    parser.add_argument("--rows", type=int, default=20, help="导出前 N 行（默认 20）")
    parser.add_argument("--csv", default=None, help="CSV 输出路径（默认 stdout）")
    args = parser.parse_args()

    with open(args.data, "r") as f:
        data = json.load(f)

    sheets = data.get("sheets", [])
    target = None
    for s in sheets:
        if s.get("sheet_name") == args.sheet:
            target = s
            break
    if not target:
        print(f"未找到子表: {args.sheet}", file=sys.stderr)
        print(f"可用子表: {[s.get('sheet_name') for s in sheets]}", file=sys.stderr)
        sys.exit(1)

    records = target.get("records", [])[:args.rows]
    if not records:
        print(f"子表 '{args.sheet}' 无数据", file=sys.stderr)
        sys.exit(1)

    # 收集所有字段名
    all_keys = []
    seen = set()
    for r in records:
        for k in r.keys():
            if k not in seen:
                all_keys.append(k)
                seen.add(k)

    out = open(args.csv, "w", newline="") if args.csv else sys.stdout
    writer = csv.DictWriter(out, fieldnames=all_keys, extrasaction="ignore")
    writer.writeheader()
    for r in records:
        # 把 list/dict 值展平成字符串
        flat = {}
        for k, v in r.items():
            if isinstance(v, list):
                flat[k] = ", ".join(str(x) for x in v)
            elif isinstance(v, dict):
                flat[k] = json.dumps(v, ensure_ascii=False)
            else:
                flat[k] = v
        writer.writerow(flat)

    if args.csv:
        out.close()
        print(f"已导出 {len(records)} 行到 {args.csv}", file=sys.stderr)
    else:
        # 额外输出验证清单
        print(f"\n=== 验证清单 ===", file=sys.stderr)
        print(f"子表: {args.sheet}", file=sys.stderr)
        print(f"总行数: {len(target.get('records', []))}", file=sys.stderr)
        print(f"导出行数: {len(records)}", file=sys.stderr)
        print(f"字段数: {len(all_keys)}", file=sys.stderr)
        print(f"合并单元格数: {len(target.get('merges', []))}", file=sys.stderr)
        print(f"\n⚠️ 请对照原始文档中前 {args.rows} 行，逐列检查：", file=sys.stderr)
        print(f"  1. 表头行是否完整（无缺失列名、无 None）", file=sys.stderr)
        print(f"  2. 日期列格式是否正确（%-m月%-d日 或 ISO）", file=sys.stderr)
        print(f"  3. 合并区域是否所有子格都填了值", file=sys.stderr)
        print(f"  4. 图片列是否有完整 URL（非 base64）", file=sys.stderr)
        print(f"  5. 公式列是否返回了计算结果（非 {formula:...}）", file=sys.stderr)

if __name__ == "__main__":
    main()
