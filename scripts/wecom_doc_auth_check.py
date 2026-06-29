#!/usr/bin/env python3
"""
企微文档授权状态检测 — cookie 过期预警 + MCP 授权过期告警
每日运行（crontab），有异常才输出（静默 = 一切正常）。

crontab 示例（避开整点）:
  17 9 * * * /usr/bin/python3 /root/.hermes/scripts/wecom_doc_auth_check.py 2>&1

检测项:
  1. 浏览器 storage_state cookie (wedoc_sid) 到期前 ≤2 天 → 提醒扫码续期
  2. MCP 机器人授权 (errcode 851014/2200063) → 即时告警 + 授权链接

errcode 含义:
  851014 / 2200063 = 授权过期（需重新授权）
  851003 = 无此文档权限但授权有效（正常，不告警）
  851000 = 无效URL但授权有效（正常，不告警）
"""
import json, time, datetime, requests, sys

TODAY = int(time.time())
ALERTS = []

# === 1. 浏览器 cookie 过期检测 ===
STATE_FILE = "/root/.hermes/scripts/wecom_states/_shared.json"
try:
    d = json.load(open(STATE_FILE))
    for c in d.get("cookies", []):
        if c.get("name") == "wedoc_sid":
            exp = int(c.get("expires", 0))
            if exp > 0:
                days_left = (exp - TODAY) // 86400
                if days_left <= 2:
                    exp_str = datetime.datetime.fromtimestamp(exp).strftime("%Y-%m-%d %H:%M")
                    ALERTS.append(f"⚠️ 企微文档浏览器扫码 cookie 还有 {days_left} 天过期（{exp_str}），需要扫码续期。")
            break
    else:
        ALERTS.append(f"⚠️ storage_state 中未找到 wedoc_sid cookie")
except FileNotFoundError:
    ALERTS.append(f"⚠️ storage_state 文件不存在: {STATE_FILE}")
except Exception as e:
    ALERTS.append(f"⚠️ 读取 cookie 状态异常: {e}")

# === 2. MCP 授权过期检测 ===
# ⚠️ MCP URL 含 apikey，从 hermes config.yaml 读取
MCP_URL = "https://qyapi.weixin.qq.com/mcp/robot-doc?apikey=YOUR_API_KEY"
payload = {
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {"name": "smartsheet_get_sheet", "arguments": {"url": "https://doc.weixin.qq.com/smartsheet/s3_test"}},
    "id": 1,
}
try:
    resp = requests.post(MCP_URL, json=payload, headers={"Accept": "application/json"}, timeout=15)
    data = resp.json()
    text = data.get("result", {}).get("content", [{}])[0].get("text", "")
    inner = json.loads(text)
    errcode = inner.get("errcode", 0)
    # 851003 = 无此文档权限（正常，说明授权没过期）
    # 851014 / 2200063 = 授权过期（需要重新授权）
    if errcode in (851014, 2200063):
        ALERTS.append(
            f"🔴 企微文档 MCP 授权已过期（errcode={errcode}），需要重新授权机器人文档权限。\n"
            f"授权链接: https://work.weixin.qq.com/ai/aiHelper/authorizationPage?str_aibotid=YOUR_BOT_ID"
        )
except Exception as e:
    ALERTS.append(f"⚠️ MCP 检测异常: {e}")

# === 输出 ===
if ALERTS:
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    print(f"企微文档授权检测报告（{now}）：\n")
    for a in ALERTS:
        print(f"{a}\n")
    print("请处理后告诉我，我来验证。")
