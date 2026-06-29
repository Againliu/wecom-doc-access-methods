#!/usr/bin/env python3
"""
企微文档 storage_state cookie 过期检查。

用法:
  python3 check_cookie_expiry.py [--state FILE] [--warn-days N]

检查 wedoc_sid / wedoc_ticket 的 expires 字段，
距过期不足 --warn-days 天时输出警告（供 cron 调用发提醒）。

退出码:
  0 = cookie 仍有效（距过期 > warn-days）
  1 = cookie 即将过期（距过期 <= warn-days）
  2 = cookie 已过期 或 文件不存在
"""

import json, os, sys, time, argparse, datetime

DEFAULT_STATE_FILES = [
    "/root/.hermes/scripts/wecom_states/_shared.json",
    "/root/.hermes/workspace/wecom_browser_state.json",
]

KEY_COOKIES = ("wedoc_sid", "wedoc_ticket")


def check_state(state_file, warn_days):
    if not os.path.exists(state_file):
        return {"file": state_file, "status": "missing", "msg": "文件不存在"}

    try:
        with open(state_file) as f:
            data = json.load(f)
    except Exception as e:
        return {"file": state_file, "status": "error", "msg": f"JSON解析失败: {e}"}

    cookies = data.get("cookies", [])
    earliest_expiry = None
    found = []

    for c in cookies:
        if c.get("name") in KEY_COOKIES:
            exp = c.get("expires", -1)
            found.append(c["name"])
            if exp > 0 and (earliest_expiry is None or exp < earliest_expiry):
                earliest_expiry = exp

    if not found:
        return {"file": state_file, "status": "no_key_cookies",
                "msg": f"未找到 {KEY_COOKIES} cookie，可能未正确登录"}

    if earliest_expiry is None or earliest_expiry <= 0:
        return {"file": state_file, "status": "session_cookie",
                "msg": "cookie 为 session 类型（无 expires），无法判断过期时间"}

    now = time.time()
    remaining = earliest_expiry - now
    remaining_days = remaining / 86400
    exp_str = datetime.datetime.fromtimestamp(earliest_expiry).strftime("%Y-%m-%d %H:%M:%S")

    if remaining <= 0:
        return {"file": state_file, "status": "expired",
                "msg": f"cookie 已过期（过期时间: {exp_str}）", "expires": exp_str}
    elif remaining_days <= warn_days:
        return {"file": state_file, "status": "expiring",
                "msg": f"cookie 将在 {remaining_days:.1f} 天后过期（{exp_str}），需要扫码续期",
                "expires": exp_str, "remaining_days": round(remaining_days, 1)}
    else:
        return {"file": state_file, "status": "valid",
                "msg": f"cookie 有效，剩余 {remaining_days:.1f} 天（过期: {exp_str}）",
                "expires": exp_str, "remaining_days": round(remaining_days, 1)}


def main():
    parser = argparse.ArgumentParser(description="企微文档 cookie 过期检查")
    parser.add_argument("--state", default=None,
                        help="storage_state 文件路径（默认检查所有已知路径）")
    parser.add_argument("--warn-days", type=int, default=2,
                        help="距过期多少天开始警告（默认 2）")
    args = parser.parse_args()

    files = [args.state] if args.state else DEFAULT_STATE_FILES
    worst_exit = 0
    results = []

    for f in files:
        r = check_state(f, args.warn_days)
        results.append(r)
        if r["status"] in ("expired", "missing", "no_key_cookies", "error"):
            worst_exit = max(worst_exit, 2)
        elif r["status"] == "expiring":
            worst_exit = max(worst_exit, 1)

    output = {"checked_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
              "warn_days": args.warn_days, "results": results}
    print(json.dumps(output, ensure_ascii=False, indent=2))
    sys.exit(worst_exit)


if __name__ == "__main__":
    main()
