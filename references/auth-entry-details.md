# 扫码授权入口实现细节（自 SKILL.md v5.11.1 外移，原文未删减）

## 入口内部实现（入口自动选,勿直接调）:

- Hermes 入口：`python3 ~/.hermes/scripts/wecom_auth_flow.py --check <wecom_userid>`
- OpenClaw 入口：`python3 ~/.openclaw/scripts/wecom_auth_xiaoming.py --check <wecom_userid>`
- ⚠️ OpenClaw 侧 `~/.hermes` 不可读是私有边界(非故障),勿上报勿 chmod;OpenClaw 侧用 `--wait-done <企业userid>` 取二维码。
  **必须显式传 wecom_userid**（2026-09-01 修）：openclaw 不像 hermes 那样往子进程注入
  发信人环境变量（实测 `OPENCLAW_CHANNEL_CONTEXT` 在整个运行时零命中，是早先照搬
  hermes 想当然写的），所以小明拿不到"当前跟我说话的是谁"，必须由你从对话里取到
  对方的企微 userid 显式传入。安全锁在通讯录校验：传入的 id 查不到就拒绝执行。
  不传参会报 `credential access requires a gateway-bound sender`——**那不是故障，
  是缺参数**。此前小明因此反复回报"扫码做不了"。
- **小明禁止用 `~/.hermes` 入口**，否则其独立凭据失效。

## 扫码即自动捕获姓名（2026-09-02 v5.11.0）

`wecom_login.py` 登录成功后自动读取 `basicClientVars.userInfo.userName` 存入状态文件
`login_user` 字段，`wecom_auth_flow.py` 完成时回写 principal.display_name
（`set_login_display_name`，不覆盖已验证成员）。新用户扫码后无需再人工配对姓名；
读历史登录态可用 `login_user` 字段识别归属。注意：**cookie 有效才能拿到名字**
（过期后页面返回 guest/userName 为空）；这是登录页标注，不等于身份验证——企微通道
身份仍以平台原生 sender 绑定为准。机制详情与双存储说明见
`references/wecom-login-user-info-capture-2026-09.md`。

## 机制原文（保证零丢失）

5. **扫码即自动捕获姓名（2026-09-02 v5.11.0）**：`wecom_login.py` 登录成功后自动读取
   `basicClientVars.userInfo.userName` 存入状态文件 `login_user` 字段，
内部实现(入口自动选,勿直接调):

## 原卡顶部说明（压缩卡时改写，原文存档）

> **本卡 <5000 字符，压缩时不会被剪。** 详细内容在 references/，用
> `skill_view(name="wecom-doc-access-methods", file="references/<文件>")` 按需加载。
