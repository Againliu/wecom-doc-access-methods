#!/usr/bin/env python3
"""
身份隔离合规审计脚本 — 检查定时任务/skill/SOUL.md/cookie 的身份隔离合规性。

检查 5 个维度：
1. Crontab 定时任务 — 涉及企微/飞书文档操作的有没有 WECOM_USERID
2. Hermes cron jobs — 同上
3. 所有 skill — 有没有做身份隔离评估（有铁规或显式标注不涉及）
4. SOUL.md 铁规 9-13 + 新成员引导是否完整
5. per-user cookie/token 过期预警

用法: python3 audit_identity_isolation.py [--json]
输出: 人类可读报告(默认) 或 JSON(--json)

部署: 放在 ~/.hermes/scripts/ 下，每日复盘 cron 调用。
"""
# 完整脚本见 ~/.hermes/scripts/audit_identity_isolation.py
# 此文件是 skill 打包时的副本，与 ~/.hermes/scripts/ 保持同步
