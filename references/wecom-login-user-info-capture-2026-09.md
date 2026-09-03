# 企微文档扫码登录用户信息捕获（2026-09-02 实测）

## 背景

2026-09-02 负责人指示：完善企微文档 skill 的登录链路——扫码登录后要能拿到用户信息（姓名等）。

## 机制

`wecom_login.py` 登录成功后自动读取页面 `basicClientVars.userInfo`，把 `userName`/`userId`/`userType` 存入状态文件 `login_user` 字段；`wecom_auth_flow.py` 授权完成时调 `broker.set_login_display_name` 回写 principal.display_name（**COALESCE 只填 NULL，不覆盖已验证成员**——已验证成员名字以团队字典为准）。

```javascript
// 企微文档页面登录后的数据结构
basicClientVars.userInfo = {
    userName: "<登录人姓名>",
    userId: "p.xxxxxxxxxxxxxxxx",
    userType: "work"
}
```

⚠️ **cookie 有效才能拿到名字**——过期后页面返回 guest/userName 为空。

注意：`userName` 是登录页标注，**不等于身份验证**——企微通道身份仍以平台原生 sender 绑定为准。未验证 principal 的姓名只能等其本人扫码/OAuth 自动带名，或由团队字典人工配对；**不能按消息内容推断归属**。

## 读历史登录态识别归属

读状态文件时可用 `login_user` 字段识别该登录态属于谁（旧登录态无此字段，需重新扫码补充）。

## 双存储系统说明

历史原因有两套 cookie 存储：
- **系统 A（身份库）**：`~/.hermes/identity/wecom/`，按 principal 分文件
- **系统 B（脚本目录）**：`~/.hermes/scripts/wecom_states/`

同一次登录会同时写入两处（不是两份登录）。定时任务读系统 B，agent 运行时读系统 A。归档过期登录态时两处都要处理。

## 改动文件清单

| 文件 | 改动 |
|---|---|
| `wecom_login.py`（多份硬拷贝） | 抓 `basicClientVars.userInfo` → `login_user` 字段 |
| `wecom_auth_flow.py` | 授权完成时 `set_login_display_name` 回写 |

## 验证记录

- `wecom_login.py` login_user 落盘验证通过 ✅
- 跨渠道账号对应关系管理（飞书 OAuth 等其他渠道的入库方案）不在本 skill 范围，属于 Agent 侧多用户方案，见 skill `skill-building-standard` 的「多用户数据隔离」章节。
