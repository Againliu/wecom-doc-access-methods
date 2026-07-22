# 企微图片/文件交付排错指南

> 2026-06-14 踩坑总结：给用户发企微扫码二维码，反复失败（MEDIA: 路径、nginx HTTP 链接、lark-cli 飞书发送），用户多次看不到图片。

## 核心问题

WeChat (WeCom) 平台对 outbound media 的支持依赖 gateway 的 `_deliver_media_from_response` 流程：
1. 文本先 flush 发送（MEDIA: 标签被当纯文本）
2. `_deliver_media_from_response` 提取 MEDIA: 路径 → 调 `send_multiple_images` 或 `send_document`

**关键路径**：`gateway/run.py` 第 11534 行 `_deliver_media_from_response`

## 已验证的发送方式

| 方式 | 可靠性 | 说明 |
|------|--------|------|
| **飞书 `send_message(target=feishu)` + MEDIA:** | ✅ 可靠 | 飞书平台原生支持图片附件 |
| **lark-cli `im +messages-send --file`** | ✅ 可靠 | 必须 cd 到文件目录 + 相对路径 + `--as bot` |
| **WeCom MEDIA:** (response 内) | ⚠️ 有条件可用 | 需要 gateway 正确提取并走 send_image 路径，streaming 模式下可能被跳过 |
| **nginx HTTP 链接** | ⚠️ 有条件可用 | 用户必须能访问该 IP:port，企微客户端可能拦截外部链接 |
| **WeCom `send_message` + MEDIA:** | ❌ 不可靠 | 历史上多次失败，MEDIA: 标签被当纯文本发送 |

## 排错流程

```
1. 发图片后 → 立即问用户"能看到吗？"
2. 如果看不到：
   a. 检查 gateway log: grep "media\|image\|deliver" ~/.config/wecom-doc/logs/gateway.log
   b. 检查文件是否存在且权限正确
   c. 换方式重发（优先飞书 → lark-cli → nginx）
3. 如果反复失败 → 查 gateway 源码定位根因，不要换着花样盲试
```

## Pitfalls

1. **不要假设用户能看到图片** — 发完必须确认
2. **不要给用户发 HTTP 链接当图片** — 企微客户端可能不渲染图片 URL
3. **nginx 路径是 `/usr/share/nginx/html/`** — 不是 `/var/www/html/`
4. **lark-cli --file 跨应用发图会报 `open_id cross app`** — 确认 user_id 和 bot 在同一应用
5. **同一方式失败2次就换方法** — 不要重试3次以上
