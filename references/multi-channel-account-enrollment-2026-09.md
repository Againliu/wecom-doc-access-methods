# 多渠道账号信息自动入库（2026-09-02 实测）

## 背景

负责人要求：不同渠道登录/授权的账号信息要都能及时入库，把对应关系管理好。
盘点后发现飞书 OAuth 链路有缺口——授权完成时不回写姓名。已修复。

## 四渠道姓名/ID 入库状态

| 渠道 | ID 入库 | 姓名入库 | 机制 |
|---|---|---|---|
| ① 企微机器人对话 | ✅ 自动（sender userid） | ❌ 平台限制 | 企微 AI Bot 回调只给 userid 不给姓名；靠 ② 补 |
| ② 企微文档扫码登录 | ✅ 自动 | ✅ v5.11.0 | `wecom_login.py` 抓 `basicClientVars.userInfo.userName` → `login_user` 字段；`auth_flow` 完成时 `broker.set_login_display_name` 回写 |
| ③ 飞书机器人对话 | ✅ 自动 | ✅ 自动 | 飞书 adapter 自带 `user_name`（`resolve_sender_profile`） |
| ④ 企微里点飞书 OAuth 授权 | ✅ 自动 | ✅ 2026-09-02 | `lark_bridge.verify_profile` 返回三元组；`lark_auth_flow` 完成时 `set_login_display_name` 回写 |

## 改动详情

### 1. wecom_login.py（企微文档扫码登录）

登录成功后自动读取页面 `basicClientVars.userInfo`，把 `userName`/`userId`/`userType` 存入状态文件 `login_user` 字段。

```javascript
// 页面里的数据结构
basicClientVars.userInfo = {
    userName: "<成员姓名示例>",
    userId: "p.13102700871901602",
    userType: "work"
}
```

⚠️ cookie 有效才能拿到名字——过期后页面返回 guest/userName 为空。

### 2. lark_bridge.py（飞书 CLI 验证）

`verify_profile` 返回值从 2 元改 3 元：

```python
# 旧：verify_profile(profile) → (open_id, fingerprint)
# 新：verify_profile(profile) → (open_id, fingerprint, user_name)
# user_name 来自 lark-cli auth list --json 的 userName 字段
```

实测验证：
```python
verify_profile(Path('...20b35c2e...')) 
# → ('ou_bf2effa699323b81c3bb4e6305aae205', 'ca76e6faf2177e54', '<成员姓名>')
```

### 3. lark_auth_flow.py（飞书授权流程）

`wait_for_auth()` 在授权完成时调用 `broker.set_login_display_name` 回写姓名：

```python
open_id, fingerprint, login_name = verify_profile(profile, timeout=45)
if login_name:
    store.set_login_display_name(
        active.principal_id,
        login_name,
        source_external_id=active.external_id,
    )
```

4 个 `verify_profile` 调用点全部适配 3 元返回值。

### 4. broker.set_login_display_name 方法

新增的 broker 方法，用于从登录/授权结果回写姓名：

```python
store.set_login_display_name(
    principal_id,
    display_name,           # 从登录/授权拿到的真实姓名
    source_external_id=None  # 可选：来源外部 ID
)
```

**安全规则**：不覆盖已验证成员的 display_name（COALESCE 只填 NULL）。已验证成员的名字由 team-members.json 字典或飞书 adapter 优先。

## 未验证会话的身份排查教训

8/17 出现的 `woTr…（原始userid，已截断脱敏）` 会话，8/16 用企微文档登录态问了 20 轮产品问题。

- ❌ **错误**：看问题内容像行内人，就说"行为上大概率是你"——违反身份不猜铁律
- ✅ **正确**：企微渠道每人有独立 sender ID，机器层面分得清。不同 ID = 不同人，不靠内容推断
- 未验证 ID 的姓名只能等该人下次扫码/OAuth 自动带名，或由团队字典人工配对

## 双存储系统说明

历史原因有两套 cookie 存储：
- **系统 A（身份库）**：`~/.hermes/identity/wecom/`，按 principal 分文件
- **系统 B（脚本目录）**：`~/.hermes/scripts/wecom_states/`

同一次登录会同时写入两处（不是两份登录）。定时任务读系统 B，agent 运行时读系统 A。归档过期登录态时两处都要处理。

## 改动文件清单

| 文件 | 改动 |
|---|---|
| `wecom_login.py`（两份硬拷贝） | 抓 basicClientVars.userInfo → login_user 字段 |
| `lark_bridge.py` | verify_profile 2→3 元返回 |
| `lark_auth_flow.py` | 4 个调用点适配 + wait_for_auth 回写姓名 |
| `wecom-doc-access-methods` SKILL.md | 扫码授权铁律第 5 条（已在前台会话写入 v5.11.0） |

## 验证记录

- `verify_profile` 实测返回 `('ou_bf2eff…', '指纹', '<成员姓名>')` ✅
- `lark_auth_flow --check` 回归正常 ✅
- `wecom_login.py` login_user 落盘验证通过 ✅
