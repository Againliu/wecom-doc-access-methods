#!/usr/bin/env python3
"""wecom_status.py — 一键检查企微文档访问状态

检查项:
  1. Cookie 文件存在性 + 过期时间
  2. MCP API Key 有效性（调 smartsheet_get_sheet 测试）
  3. 综合状态报告

用法:
  python3 wecom_status.py                          # 只检查状态
  python3 wecom_status.py --user <userid>          # 指定用户 cookie
  python3 wecom_status.py --test-url <doc_url>     # 额外做读写冒烟测试
  python3 wecom_status.py --json                   # JSON 输出

环境变量:
  WECOM_MCP_APIKEY   — MCP API key（或 WECOM_MCP_URL）
  WECOM_USERID       — 默认用户 ID
  WECOM_STATE_DIR    — cookie 目录（默认: 脚本所在目录/wecom_states）
"""
import argparse, json, os, sys, time, glob


def check_cookie(user_id=None, state_dir=None):
    """Check cookie file existence and expiry."""
    if state_dir is None:
        state_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "wecom_states")

    if user_id:
        pattern = os.path.join(state_dir, f"{user_id}.json")
    else:
        # find most recent cookie file
        files = glob.glob(os.path.join(state_dir, "*.json"))
        if not files:
            return {"status": "missing", "detail": f"No cookie files in {state_dir}"}
        pattern = max(files, key=os.path.getmtime)
        user_id = os.path.basename(pattern).replace(".json", "")

    if not os.path.exists(pattern):
        return {"status": "missing", "detail": f"Cookie file not found: {pattern}", "user_id": user_id}

    try:
        with open(pattern) as f:
            data = json.load(f)
        cookies = data.get("cookies", [])
        if not cookies:
            return {"status": "empty", "detail": "Cookie file has no cookies", "user_id": user_id}

        # check expiry
        now = time.time()
        min_expiry = None
        for c in cookies:
            exp = c.get("expires", -1)
            if exp > 0:
                if min_expiry is None or exp < min_expiry:
                    min_expiry = exp

        if min_expiry is None:
            return {"status": "ok", "detail": "Session cookies (no expiry)", "user_id": user_id, "cookie_count": len(cookies)}

        remaining = min_expiry - now
        if remaining <= 0:
            return {
                "status": "expired",
                "detail": f"Cookies expired {abs(remaining)/3600:.1f}h ago",
                "user_id": user_id,
                "cookie_count": len(cookies),
                "fix": f"Re-run: python3 scripts/wecom_login.py --state {pattern} --qr /tmp/qr.png"
            }
        elif remaining < 3600:
            return {
                "status": "expiring_soon",
                "detail": f"Cookies expire in {remaining/60:.0f} minutes",
                "user_id": user_id,
                "cookie_count": len(cookies),
                "fix": f"Re-run: python3 scripts/wecom_login.py --state {pattern} --qr /tmp/qr.png"
            }
        else:
            return {
                "status": "ok",
                "detail": f"Cookies valid for {remaining/3600:.1f}h",
                "user_id": user_id,
                "cookie_count": len(cookies),
                "expires_in_hours": round(remaining / 3600, 1)
            }
    except json.JSONDecodeError:
        return {"status": "corrupt", "detail": f"Cookie file is not valid JSON: {pattern}", "user_id": user_id}
    except Exception as e:
        return {"status": "error", "detail": str(e), "user_id": user_id}


def check_mcp_key():
    """Check MCP API key validity via a lightweight call."""
    apikey = os.environ.get("WECOM_MCP_APIKEY", "")
    mcp_url = os.environ.get("WECOM_MCP_URL", "")

    if not apikey and not mcp_url:
        return {"status": "missing", "detail": "Neither WECOM_MCP_APIKEY nor WECOM_MCP_URL is set"}

    if not mcp_url:
        mcp_url = f"https://doc.weixin.qq.com/openapi/mcp?apikey={apikey}"

    try:
        import requests
        resp = requests.post(
            mcp_url,
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            timeout=10
        )
        data = resp.json()
        if "result" in data:
            tools = data["result"].get("tools", [])
            return {
                "status": "ok",
                "detail": f"MCP key valid, {len(tools)} tools available",
                "tool_count": len(tools)
            }
        elif "error" in data:
            err = data["error"]
            code = err.get("code", "?")
            msg = err.get("message", "?")
            if "851014" in str(msg) or "expired" in str(msg).lower():
                return {
                    "status": "expired",
                    "detail": f"MCP authorization expired (errcode {code}): {msg}",
                    "fix": "Re-obtain API key from WeCom admin console → AI Helper → MCP configuration"
                }
            elif "850001" in str(msg) or "invalid" in str(msg).lower():
                return {
                    "status": "invalid",
                    "detail": f"MCP API key invalid (errcode {code}): {msg}",
                    "fix": "Check WECOM_MCP_APIKEY for typos/missing characters"
                }
            return {"status": "error", "detail": f"MCP error {code}: {msg}"}
        return {"status": "unknown", "detail": f"Unexpected response: {str(data)[:200]}"}
    except ImportError:
        return {"status": "skip", "detail": "requests library not installed, skipping MCP check"}
    except Exception as e:
        return {"status": "error", "detail": f"MCP check failed: {e}"}


def smoke_test(test_url, user_id=None):
    """Quick read smoke test on a real document."""
    try:
        # try MCP path first
        apikey = os.environ.get("WECOM_MCP_APIKEY", "")
        if apikey:
            import requests
            mcp_url = os.environ.get("WECOM_MCP_URL",
                f"https://doc.weixin.qq.com/openapi/mcp?apikey={apikey}")

            # extract docid from URL
            docid = None
            for prefix in ("s3_", "e3_", "w3_", "m4_"):
                idx = test_url.find(prefix)
                if idx >= 0:
                    docid = test_url[idx:].split("?")[0].split("/")[0]
                    break

            if docid and test_url.find("s3_") >= 0:
                resp = requests.post(
                    mcp_url,
                    json={"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                          "params": {"name": "smartsheet_get_sheet", "arguments": {"url": test_url}}},
                    headers={"Content-Type": "application/json", "Accept": "application/json"},
                    timeout=15
                )
                data = resp.json()
                if "result" in data:
                    return {"status": "ok", "method": "MCP", "detail": f"Read OK: {docid}"}
                return {"status": "fail", "method": "MCP", "detail": str(data.get("error", ""))[:200]}

        return {"status": "skip", "detail": "No MCP key or unsupported doc type for smoke test"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


def main():
    parser = argparse.ArgumentParser(description="WeCom doc access status checker")
    parser.add_argument("--user", help="WeCom user ID (for cookie lookup)")
    parser.add_argument("--state-dir", help="Cookie state directory")
    parser.add_argument("--test-url", help="Document URL for read/write smoke test")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    user_id = args.user or os.environ.get("WECOM_USERID")

    result = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "cookie": check_cookie(user_id, args.state_dir),
        "mcp": check_mcp_key(),
    }

    if args.test_url:
        result["smoke_test"] = smoke_test(args.test_url, user_id)

    # overall status
    statuses = [result["cookie"]["status"], result["mcp"]["status"]]
    if "expired" in statuses or "invalid" in statuses:
        result["overall"] = "action_required"
    elif "missing" in statuses and all(s == "missing" for s in statuses):
        result["overall"] = "not_configured"
    elif "error" in statuses or "corrupt" in statuses:
        result["overall"] = "error"
    else:
        result["overall"] = "ok"

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"{'='*50}")
        print(f"  WeCom Doc Access Status — {result['timestamp']}")
        print(f"{'='*50}")

        # cookie
        c = result["cookie"]
        icon = {"ok": "✅", "expiring_soon": "⚠️", "expired": "❌", "missing": "❌", "corrupt": "❌", "empty": "⚠️", "error": "❌"}.get(c["status"], "❓")
        print(f"\n  {icon} Cookie ({c.get('user_id', 'N/A')}): {c['detail']}")
        if c.get("fix"):
            print(f"     → Fix: {c['fix']}")

        # mcp
        m = result["mcp"]
        icon = {"ok": "✅", "expired": "❌", "invalid": "❌", "missing": "❌", "error": "❌", "skip": "⏭️", "unknown": "❓"}.get(m["status"], "❓")
        print(f"\n  {icon} MCP API Key: {m['detail']}")
        if m.get("fix"):
            print(f"     → Fix: {m['fix']}")

        # smoke test
        if "smoke_test" in result:
            s = result["smoke_test"]
            icon = {"ok": "✅", "fail": "❌", "error": "❌", "skip": "⏭️"}.get(s["status"], "❓")
            print(f"\n  {icon} Smoke Test: {s['detail']}")

        # overall
        o = result["overall"]
        icon = {"ok": "✅", "action_required": "🚨", "not_configured": "⚠️", "error": "❌"}.get(o, "❓")
        print(f"\n  {icon} Overall: {o}")
        print()

    sys.exit(0 if result["overall"] == "ok" else 1)


if __name__ == "__main__":
    main()
