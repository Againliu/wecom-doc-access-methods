#!/usr/bin/env python3
"""
企微文档授权状态检测 — cookie 过期预警 + MCP 授权过期告警
每小时运行，有异常才输出（静默 = 一切正常）
cookie 提前4天预警；MCP 授权过期无法预测，检测到就立即告警

配置（环境变量）：
  WECOM_MCP_APIKEY  — 企微 MCP robot-doc 的 apikey（必填，否则跳过 MCP 检测）
  WECOM_AIBOT_ID    — 企微 AI bot 授权页 ID（用于过期时的授权链接，可选）
  WECOM_DOC_STATE   — cookie storage_state 文件路径（默认 ~/.config/wecom-doc/states/_shared.json）
"""
import json, time, datetime, requests, sys, os

TODAY = int(time.time())
ALERTS = []

# 状态记录文件 — 追踪 MCP 授权成功/失败历史
STATE_LOG = os.path.expanduser(os.environ.get(
    "WECOM_DOC_STATE_LOG", "~/.config/wecom-doc/states/_auth_history.json"))

# === 1. 浏览器 cookie 过期检测 ===
STATE_FILE = os.path.expanduser(os.environ.get(
    "WECOM_DOC_STATE", "~/.config/wecom-doc/states/_shared.json"))
try:
    d = json.load(open(STATE_FILE))
    for c in d.get("cookies", []):
        if c.get("name") == "wedoc_sid":
            exp = int(c.get("expires", 0))
            if exp > 0:
                days_left = (exp - TODAY) // 86400
                if days_left <= 4:
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
_MCK = os.environ.get("WECOM_MCP_APIKEY", "")
AIBOT_ID = os.environ.get("WECOM_AIBOT_ID", "YOUR_AIBOT_ID")
MCP_URL = f"https://qyapi.weixin.qq.com/mcp/robot-doc?apikey={_MCK}" if _MCK else None
_AUTH = os.environ.get("WECOM_AUTH_URL", "（请配置 WECOM_AUTH_URL 环境变量指向授权页）")
payload = {
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {"name": "smartsheet_get_sheet", "arguments": {"url": "https://doc.weixin.qq.com/smartsheet/s3_test"}},
    "id": 1,
}
if not MCP_URL:
    ALERTS.append("ℹ️ 未设置 WECOM_MCP_APIKEY 环境变量，跳过 MCP 授权检测。")
else:
    try:
        resp = requests.post(MCP_URL, json=payload, headers={"Accept": "application/json"}, timeout=15)
        data = resp.json()
        text = data.get("result", {}).get("content", [{}])[0].get("text", "")
        inner = json.loads(text)
        errcode = inner.get("errcode", 0)
        # 851003 = 无此文档权限（正常，说明授权没过期）
        # 851014 / 2200063 = 授权过期（需要重新授权）
        if errcode in (851014, 2200063):
            # 记录过期时间到历史文件
            history = {}
            if os.path.exists(STATE_LOG):
                try:
                    history = json.load(open(STATE_LOG))
                except:
                    pass
            last_ok = history.get("last_ok_time")
            now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            if last_ok:
                days_since_ok = (TODAY - last_ok) // 86400
                ALERTS.append(
                    f"🔴 企微文档 MCP 授权已过期（errcode={errcode}），需要重新授权机器人文档权限。\n"
                    f"上次正常: {datetime.datetime.fromtimestamp(last_ok).strftime('%Y-%m-%d %H:%M')}（{days_since_ok}天前）\n"
                    f"授权链接: {_AUTH}"
                )
            else:
                ALERTS.append(
                    f"🔴 企微文档 MCP 授权已过期（errcode={errcode}），需要重新授权机器人文档权限。\n"
                    f"授权链接: {_AUTH}"
                )
        elif errcode == 851003:
            # 851003 = 无此文档权限（正常，说明授权没过期）
            history = {}
            if os.path.exists(STATE_LOG):
                try:
                    history = json.load(open(STATE_LOG))
                except:
                    pass
            history["last_ok_time"] = TODAY
            os.makedirs(os.path.dirname(STATE_LOG), exist_ok=True)
            json.dump(history, open(STATE_LOG, "w"))
    except Exception as e:
        ALERTS.append(f"⚠️ MCP 检测异常: {e}")

# === 输出 ===
if ALERTS:
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    print(f"企微文档授权检测报告（{now}）：\n")
    for a in ALERTS:
        print(f"{a}\n")
    print("请处理后告诉我，我来验证。")
