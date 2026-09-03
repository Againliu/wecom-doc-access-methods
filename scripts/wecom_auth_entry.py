#!/usr/bin/env python3
"""企微文档授权的**过渡入口**(将被配置驱动的 wecom_login.py 取代,见 reflections/wecom-doc-skill-genericity-2026-09-02.md 蓝图第 7 步)—— 2026-09-02,负责人反馈 skill 通用性不足。

此前 SKILL 里写两行"Hermes 入口/OpenClaw 入口",各指各的绝对路径;另一台 Agent 照着旧副本走错了入口,10 天报"不可用"。
共享 skill 不该让读者判断"我是谁",由入口自己判:
  - 能读 ~/.hermes/scripts/wecom_auth_flow.py  → Hermes 侧上游流程
  - 否则若存在 ~/.openclaw/scripts/wecom_auth_xiaoming.py → OpenClaw 侧包装器(供应商化产物)
  - 都不满足 → 明确报错,不猜
参数原样透传:--check|--wait-done <发信人ID> | --status <transaction_id>
发信人 ID 用**你收到消息时看到的那个**(Hermes 侧是 wo… 开头,OpenClaw 侧是企业 userid),不要互换。
"""
import os, subprocess, sys

HERMES = "~/.hermes/scripts/wecom_auth_flow.py"
XIAOMING = "~/.openclaw/scripts/wecom_auth_xiaoming.py"

def pick():
    # 2026-09-02 晚(审计蓝图 §2/§4-7):入口只看配置,不探测路径、不猜身份。
    #   WECOM_DOC_AUTH_BACKEND=<可执行路径>  由宿主(hermes 服务 env / openclaw 单元 drop-in)注入
    # 下面两条路径探测是过渡兜底,通用层重构完成后本文件整体删除(蓝图第 7 步)。
    cfg = os.environ.get("WECOM_DOC_AUTH_BACKEND", "").strip()
    if cfg:
        return cfg, "configured"
    if os.access(HERMES, os.R_OK):
        return HERMES, "hermes"
    if os.path.isfile(XIAOMING):
        return XIAOMING, "openclaw"
    return None, None

def main(argv):
    target, side = pick()
    if not target:
        print('{"action":"error","reason":"本机没有可用的授权入口:既读不到 ~/.hermes 的上游流程,也没有 ~/.openclaw/scripts/wecom_auth_xiaoming.py"}')
        return 2
    env = dict(os.environ)  # 不再导出无人消费的 WECOM_AUTH_ENTRY_SIDE
    return subprocess.run([sys.executable, target] + argv, env=env).returncode

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
