# Cookie 与授权状态定时检查(长期使用必读)

> 本文件由 SKILL.md 拆分而来(2026-07-21)。

## Cookie 与授权状态定时检查（长期使用必读）

当本 skill 用于定时任务、数据同步等长期场景时，浏览器扫码 cookie（`wedoc_sid`）约 **2 周过期**，MCP 文档授权也可能过期（errcode 851014）。必须部署每日检查 cron，在过期前主动提醒续期。

### 检查脚本

`scripts/wecom_doc_auth_check.py` — 静默运行，有异常才输出（适合 cron）：

| 检查项 | 检测条件 | 告警内容 | 预警策略 |
|--------|---------|---------|----------|
| 浏览器 cookie | `wedoc_sid` 剩余 ≤4 天 | 提醒扫码续期 | **可提前预警**（cookie 有 expires 字段，7 天寿命提前 4 天提醒） |
| MCP 授权 | errcode 851014 / 2200063 | 提醒重新授权机器人文档权限 | **无法提前预警**（状态突变，非时间到期），只能增加检测频率尽快发现 |

**⚠️ MCP 851014 为什么不能提前预警？**
- MCP 授权过期是企微平台层面的**状态突变**（用户撤销了机器人权限 / 平台主动过期），不是"cookie 到了 expires 时间自然失效"
- 企微没有提供"授权剩余有效时间"的 API，只有"有权限"和"没权限"两种状态
- **策略**：无法预测，所以通过提高检测频率（每 1 小时 vs 每天 1 次）来缩短"过期→发现"的时间窗口
- **授权历史追踪**：脚本记录 `last_ok_time` 到 `_auth_history.json`，过期时会告诉用户"上次正常是 X 天前"，帮助判断授权周期

### 部署方式

#### 方式一：Hermes Cron（推荐）

```bash
# 1. 复制脚本到 Hermes scripts 目录
cp scripts/wecom_doc_auth_check.py ~/.hermes/scripts/

# 2. 创建 no_agent cron job（纯脚本，不启动 agent）
# 通过 Hermes cronjob 工具或 CLI 创建：
#   schedule: 每小时 — 17 * * * *（避开整点高峰）
#   script: wecom_doc_auth_check.py
#   no_agent: true
#   deliver: origin（输出推送到当前对话）
```

**⚠️ 为什么每小时而不是每天？**
- cookie 有 expires 字段可提前预警，4 天阈值足够
- 但 MCP 851014 是状态突变，无法预测，只能靠提高检测频率缩短"过期→发现"窗口
- 每小时 = 过期后最多 1 小时内发现并通知用户（vs 每天 1 次 = 最多 24 小时延迟）
- 用户原话："那MCP的授权检查频率提高到1小时1次吧"

#### 方式二：系统 crontab

```bash
# 1. 复制脚本
cp scripts/wecom_doc_auth_check.py ~/scripts/

# 2. 编辑 crontab
crontab -e
# 添加（每日 09:17 运行，有输出才发邮件/通知）：
17 9 * * * python3 ~/scripts/wecom_doc_auth_check.py 2>&1
```

### 配置说明

脚本内需配置两个路径（已内置默认值，按需修改）：

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `STATE_FILE` | `~/.hermes/scripts/wecom_states/_shared.json` | 浏览器 storage_state 文件路径 |
| `MCP_URL` | 企微文档 MCP endpoint | 用于检测 MCP 授权状态 |

### 续期操作

收到告警后：

1. **cookie 续期**：运行 `python3 scripts/wecom_login.py --state ~/.hermes/scripts/wecom_states/_shared.json --qr /tmp/wecom_qr.png`，扫码登录后 cookie 自动刷新
2. **MCP 授权续期**：在企微管理后台重新授权机器人文档权限（授权链接见告警消息）

---

