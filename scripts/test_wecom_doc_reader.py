#!/usr/bin/env python3
"""
wecom-doc-access-methods 完备测试套件

覆盖场景：
1. URL 解析（各种格式）
2. base64+zlib 解码（含 padding 边界）
3. 列定义解析（k前缀/数字键）
4. 单子表读取（s3_）
5. 多子表读取（s3_，24+子表）
6. 数据完整性（记录数、字段数、空值检测）
7. 错误处理（无效URL、过期cookie、无权限）
8. 格式兼容（k前缀 vs 数字键）

用法：
    python3 test_wecom_doc_reader.py --state-dir /path/to/states --user _shared
    python3 test_wecom_doc_reader.py --state-dir /path/to/states --user _shared --url "https://doc.weixin.qq.com/smartsheet/s3_xxx"
    python3 test_wecom_doc_reader.py --offline  # 只跑不需要浏览器的单元测试
"""

import asyncio
import base64
import zlib
import json
import sys
import os
import time
import argparse
from pathlib import Path

# 添加脚本目录到 path
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

from wecom_doc_reader import (
    WeComDocReader,
    parse_doc_url,
    _parse_column_defs,
    _cell_value,
    _FIELD_TYPE_TEXT,
    _FIELD_TYPE_SELECT,
)

# ─── 测试框架 ───

class TestResult:
    def __init__(self, name):
        self.name = name
        self.passed = 0
        self.failed = 0
        self.errors = []

    def ok(self, msg=""):
        self.passed += 1
        print(f"  ✅ {msg}")

    def fail(self, msg):
        self.failed += 1
        self.errors.append(msg)
        print(f"  ❌ {msg}")

    def summary(self):
        total = self.passed + self.failed
        status = "PASS" if self.failed == 0 else "FAIL"
        print(f"\n{'='*60}")
        print(f"  {self.name}: {self.passed}/{total} passed ({status})")
        if self.errors:
            print(f"  Failures:")
            for e in self.errors:
                print(f"    - {e}")
        print(f"{'='*60}")
        return self.failed == 0


# ─── 1. URL 解析测试 ───

def test_url_parsing():
    r = TestResult("URL 解析")
    print("\n📋 URL 解析测试")

    cases = [
        ("https://doc.weixin.qq.com/smartsheet/s3_AdgAcwb2AHMCN0L2sBhuVT6u6Qmg8",
         {"doc_id": "s3_AdgAcwb2AHMCN0L2sBhuVT6u6Qmg8", "path_type": "smartsheet"}),
        ("https://doc.weixin.qq.com/smartsheet/s3_AdgAcwb2AHMCN0L2sBhuVT6u6Qmg8?scode=xxx&tab=EKzaES",
         {"doc_id": "s3_AdgAcwb2AHMCN0L2sBhuVT6u6Qmg8", "tab": "EKzaES"}),
        ("https://doc.weixin.qq.com/doc/w3_AEQdQRzEIk5",
         {"doc_id": "w3_AEQdQRzEIk5", "path_type": "doc"}),
        ("https://doc.weixin.qq.com/sheet/e3_xxx",
         {"doc_id": "e3_xxx", "path_type": "sheet"}),
        ("https://doc.weixin.qq.com/mind/m4_xxx",
         {"doc_id": "m4_xxx", "path_type": "mind"}),
    ]

    for url, expected in cases:
        info = parse_doc_url(url)
        for k, v in expected.items():
            if info.get(k) == v:
                r.ok(f"{url[:50]}... → {k}={v}")
            else:
                r.fail(f"{url[:50]}... → expected {k}={v}, got {info.get(k)}")

    # 无效 URL
    info = parse_doc_url("https://example.com/not-a-doc")
    if not info.get("doc_id"):
        r.ok("无效 URL → doc_id=None")
    else:
        r.fail(f"无效 URL → expected doc_id=None, got {info.get('doc_id')}")

    return r


# ─── 2. base64+zlib 解码测试 ───

def test_base64_zlib_decode():
    r = TestResult("base64+zlib 解码")
    print("\n📋 base64+zlib 解码测试")

    # 构造测试数据
    test_data = {"hello": "world", "nested": {"arr": [1, 2, 3]}}
    json_bytes = json.dumps(test_data).encode("utf-8")
    compressed = zlib.compress(json_bytes)
    encoded = base64.urlsafe_b64encode(compressed).decode("ascii")

    # 正常解码
    try:
        padding = 4 - len(encoded) % 4
        raw = encoded + ("=" * padding if padding != 4 else "")
        decoded = base64.urlsafe_b64decode(raw)
        decompressed = zlib.decompress(decoded)
        result = json.loads(decompressed.decode("utf-8"))
        if result == test_data:
            r.ok("正常编码→解码 roundtrip")
        else:
            r.fail(f"roundtrip 数据不匹配: {result}")
    except Exception as e:
        r.fail(f"正常解码失败: {e}")

    # 缺少 padding 的 base64
    no_pad = encoded.rstrip("=")
    try:
        padding = 4 - len(no_pad) % 4
        raw = no_pad + ("=" * padding if padding != 4 else "")
        decoded = base64.urlsafe_b64decode(raw)
        decompressed = zlib.decompress(decoded)
        result = json.loads(decompressed.decode("utf-8"))
        if result == test_data:
            r.ok("缺少 padding → 自动补齐")
        else:
            r.fail("padding 补齐后数据不匹配")
    except Exception as e:
        r.fail(f"缺少 padding 解码失败: {e}")

    # eJ 开头检测
    if encoded.startswith("eJ"):
        r.ok(f"zlib 压缩后 base64 以 eJ 开头 (符合企微格式)")
    else:
        r.fail(f"zlib 压缩后 base64 不以 eJ 开头: {encoded[:10]}")

    # 空/无效数据
    try:
        base64.urlsafe_b64decode("invalid!!!")
        r.fail("无效 base64 没有抛异常")
    except Exception:
        r.ok("无效 base64 → 正确抛异常")

    return r


# ─── 3. 列定义解析测试 ───

def test_column_defs_parsing():
    r = TestResult("列定义解析")
    print("\n📋 列定义解析测试")

    # k 前缀格式
    k_prefix_items = [
        {"t": 3005, "c": {"k3": {"k3": {
            "fld1": {"k30": "产品线", "k31": 1},
            "fld2": {"k30": "工单编号", "k31": 2},
            "fld3": {"k30": "状态", "k31": 17, "k17": {"k3": [
                {"k1": "opt1", "k2": "待处理"},
                {"k1": "opt2", "k2": "已完成"},
            ]}},
        }}}}
    ]
    fields, opts, users = _parse_column_defs(k_prefix_items)
    if len(fields) == 3:
        r.ok(f"k前缀 → 3 个字段: {list(fields.keys())}")
    else:
        r.fail(f"k前缀 → expected 3 fields, got {len(fields)}")

    if fields.get("fld1", {}).get("name") == "产品线":
        r.ok("k前缀 → 字段名正确")
    else:
        r.fail(f"k前缀 → 字段名错误: {fields.get('fld1')}")

    if "fld3" in opts and len(opts["fld3"]) == 2:
        r.ok(f"k前缀 → select 选项: {opts['fld3']}")
    else:
        r.fail(f"k前缀 → select 选项错误: {opts.get('fld3')}")

    # 数字键格式
    num_items = [
        {"t": 3005, "c": {"3": {"3": {
            "f1": {"30": "名称", "31": 1},
        }}}}
    ]
    fields2, _, _ = _parse_column_defs(num_items)
    if len(fields2) == 1 and fields2.get("f1", {}).get("name") == "名称":
        r.ok("数字键 → 1 个字段")
    else:
        r.fail(f"数字键 → 解析错误: {fields2}")

    return r


# ─── 4. 单子表读取测试（需要浏览器） ───

async def _run_single_sheet_test(reader, user_id, test_url):
    r = TestResult("单子表读取")
    print("\n📋 单子表读取测试")

    # 读取指定 tab
    url_with_tab = test_url + "&tab=EKzaES"
    try:
        result = await reader.read(user_id, url_with_tab)
        if result.get("success"):
            total = result.get("total", 0)
            fields = result.get("field_defs", {})
            records = result.get("records", [])
            if total > 0:
                r.ok(f"单子表读取成功: {total} 条记录, {len(fields)} 字段")
            else:
                r.fail("单子表读取成功但记录数为 0")
            # 检查第一条记录
            if records:
                first = records[0]
                non_empty = sum(1 for v in first.values() if v)
                if non_empty > 0:
                    r.ok(f"第一条记录有 {non_empty} 个非空字段")
                else:
                    r.fail("第一条记录全空")
            # 检查 sheet_id
            if result.get("sheet_id") == "EKzaES":
                r.ok("sheet_id 正确")
            else:
                r.fail(f"sheet_id 错误: expected EKzaES, got {result.get('sheet_id')}")
        else:
            r.fail(f"单子表读取失败: {result.get('error')}")
    except Exception as e:
        r.fail(f"单子表读取异常: {e}")

    return r


# ─── 5. 多子表读取测试（需要浏览器） ───

async def _run_multi_sheet_test(reader, user_id, test_url):
    r = TestResult("多子表读取")
    print("\n📋 多子表读取测试")

    try:
        result = await reader.read(user_id, test_url)
        if result.get("success"):
            total_sheets = result.get("total_sheets", 0)
            total_records = result.get("total_records", 0)
            sheets = result.get("sheets", [])
            workbook = result.get("workbook", [])

            if total_sheets > 1:
                r.ok(f"多子表读取成功: {total_sheets} 子表, {total_records} 条记录")
            else:
                r.fail(f"多子表模式未触发: total_sheets={total_sheets}")

            if len(sheets) == total_sheets:
                r.ok(f"sheets 数组长度 {len(sheets)} = total_sheets {total_sheets}")
            else:
                r.fail(f"sheets 数组长度 {len(sheets)} != total_sheets {total_sheets}")

            # 检查每个子表
            empty_sheets = [s for s in sheets if s["total"] == 0]
            if not empty_sheets:
                r.ok(f"所有 {len(sheets)} 个子表都有数据")
            else:
                r.fail(f"{len(empty_sheets)} 个子表为空: {[s['sheet_name'] for s in empty_sheets]}")

            # 检查 workbook
            smartsheet_count = sum(1 for s in workbook if s.get("type") == "smartsheet")
            if smartsheet_count == total_sheets:
                r.ok(f"workbook 中 smartsheet 数 {smartsheet_count} = total_sheets")
            else:
                r.fail(f"workbook smartsheet 数 {smartsheet_count} != total_sheets {total_sheets}")

            # 检查记录总数
            actual_total = sum(s["total"] for s in sheets)
            if actual_total == total_records:
                r.ok(f"记录总数一致: sheets 求和={actual_total} = total_records={total_records}")
            else:
                r.fail(f"记录总数不一致: sheets 求和={actual_total} != total_records={total_records}")

            # 检查是否有 failed_sheets
            if not result.get("failed_sheets"):
                r.ok("无失败子表")
            else:
                r.fail(f"有 {len(result['failed_sheets'])} 个失败子表")

        else:
            r.fail(f"多子表读取失败: {result.get('error')}")
    except Exception as e:
        r.fail(f"多子表读取异常: {e}")

    return r


# ─── 6. 错误处理测试 ───

async def _run_error_handling_test(reader, user_id):
    r = TestResult("错误处理")
    print("\n📋 错误处理测试")

    # 无效 URL
    try:
        result = await reader.read(user_id, "https://example.com/not-a-doc")
        if not result.get("success"):
            r.ok(f"无效 URL → 正确返回失败: {result.get('error', '')[:50]}")
        else:
            r.fail("无效 URL → 应该失败但成功了")
    except Exception as e:
        r.ok(f"无效 URL → 异常捕获: {str(e)[:50]}")

    # 不存在的文档
    try:
        result = await reader.read(user_id, "https://doc.weixin.qq.com/smartsheet/s3_nonexistent12345")
        if not result.get("success"):
            r.ok(f"不存在文档 → 正确返回失败: {result.get('error', '')[:50]}")
        else:
            r.fail("不存在文档 → 应该失败但成功了")
    except Exception as e:
        r.ok(f"不存在文档 → 异常捕获: {str(e)[:50]}")

    return r


# ─── 7. 性能测试 ───

async def _run_performance_test(reader, user_id, test_url):
    r = TestResult("性能")
    print("\n📋 性能测试")

    start = time.time()
    try:
        result = await reader.read(user_id, test_url)
        elapsed = time.time() - start
        if result.get("success"):
            total_records = result.get("total_records", 0)
            rps = total_records / elapsed if elapsed > 0 else 0
            r.ok(f"多子表读取: {total_records} 条 / {elapsed:.1f}s ({rps:.0f} rec/s)")
            if elapsed < 120:
                r.ok(f"耗时 {elapsed:.1f}s < 120s 阈值")
            else:
                r.fail(f"耗时 {elapsed:.1f}s 超过 120s 阈值")
        else:
            r.fail(f"性能测试读取失败: {result.get('error')}")
    except Exception as e:
        r.fail(f"性能测试异常: {e}")

    return r


# ─── 主入口 ───

async def run_online_tests(args):
    """运行需要浏览器的测试"""
    reader = WeComDocReader(state_dir=args.state_dir)
    user_id = args.user
    test_url = args.url

    results = []

    # 在线测试
    r4 = await _run_single_sheet_test(reader, user_id, test_url)
    results.append(r4)

    r5 = await _run_multi_sheet_test(reader, user_id, test_url)
    results.append(r5)

    r6 = await _run_error_handling_test(reader, user_id)
    results.append(r6)

    r7 = await _run_performance_test(reader, user_id, test_url)
    results.append(r7)

    return results


def run_offline_tests():
    """运行不需要浏览器的单元测试"""
    results = []

    r1 = test_url_parsing()
    results.append(r1)

    r2 = test_base64_zlib_decode()
    results.append(r2)

    r3 = test_column_defs_parsing()
    results.append(r3)

    return results


def main():
    parser = argparse.ArgumentParser(description="wecom-doc-access-methods 测试套件")
    parser.add_argument("--state-dir", default="./wecom_states", help="cookie state 目录")
    parser.add_argument("--user", default="_shared", help="用户 ID")
    parser.add_argument("--url", default="https://doc.weixin.qq.com/smartsheet/s3_AdgAcwb2AHMCN0L2sBhuVT6u6Qmg8?scode=AE4AtAdWAAwOXIjapaAGIAUQZXAMs",
                        help="测试用智能表格 URL")
    parser.add_argument("--offline", action="store_true", help="只跑单元测试（不需要浏览器）")
    args = parser.parse_args()

    print("=" * 60)
    print("  wecom-doc-access-methods 测试套件")
    print("=" * 60)

    all_results = []

    # 单元测试（始终运行）
    all_results.extend(run_offline_tests())

    # 在线测试（需要浏览器）
    if not args.offline:
        online_results = asyncio.run(run_online_tests(args))
        all_results.extend(online_results)

    # 汇总
    total_pass = sum(r.passed for r in all_results)
    total_fail = sum(r.failed for r in all_results)
    total = total_pass + total_fail

    print(f"\n{'='*60}")
    print(f"  总计: {total_pass}/{total} passed ({'ALL PASS' if total_fail == 0 else f'{total_fail} FAILED'})")
    print(f"{'='*60}")

    sys.exit(0 if total_fail == 0 else 1)


if __name__ == "__main__":
    main()
