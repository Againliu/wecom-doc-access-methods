# WeCom 消息媒体发送指南

> 2026-06-14 整理。团队负责人多次因企微发图失败而愤怒，此文档为操作标准。

## 平台能力（从 wecom.py 插件源码确认）

| 方法 | 发送内容 | 大小限制 | 说明 |
|------|---------|---------|------|
| `send_image` / `send_image_file` | 原生图片消息 | 10 MB | .jpg/.png/.webp 直接显示 |
| `send_document` | 文件附件 | 20 MB | .pdf/.docx/.xlsx/.md 等可下载 |
| `send_voice` | 语音消息 | 2 MB | 仅 AMR 格式原生播放 |
| `send_video` | 视频消息 | 10 MB | .mp4 内联播放 |
| `send` | Markdown 文本 | 4000 字符 | 支持 markdown 渲染 |

## Chunked Upload 机制

文件通过三步协议上传：`aibot_upload_media_init` → `aibot_upload_media_chunk` → `aibot_upload_media_finish`。512KB 块大小，插件自动处理。

## 自动降级规则

| 原始类型 | 超限后 |
|---------|-------|
| 图片 > 10MB | 降级为文件附件 |
| 视频 > 10MB | 降级为文件附件 |
| 语音 > 2MB 或非 AMR | 降级为文件附件 |
| 文件 > 20MB | 拒绝 + 发通知 |

## MEDIA: 语法使用规范

```
MEDIA:/absolute/path/to/file.png
```

**正确用法：**
- 图片文件（.jpg/.png/.webp）→ 作为原生照片发送（≤10MB）
- 文档文件（.pdf/.md/.txt）→ 作为可下载附件发送（≤20MB）
- 视频文件（.mp4）→ 内联播放（≤10MB）

**⚠️ 注意事项：**
1. **路径必须是绝对路径**且文件必须存在
2. **图片格式优先用 PNG**（兼容性最好）
3. 文件大小必须低于对应类型限制
4. 企微的 markdown 中也可以用 `![alt](url)` 嵌入图片

## 已知踩坑记录

### 踩坑1：二维码图片发送失败（2026-06-14）
- 场景：给团队负责人发企微扫码二维码 `/tmp/wecom_qr_code.png`
- 问题1：发了 `MEDIA:/tmp/wecom_qr_code.png` 但用户说看不到
- 问题2：尝试 nginx HTTP 链接，用户说打不开（可能是外网访问问题）
- 问题3：用 lark-cli 发飞书，报 `open_id cross app` 错误
- 最终：通过 `send_message(target=feishu) + MEDIA:` 成功发到飞书

**根因分析（gateway 源码确认）：**
- hermes gateway 的 `_deliver_media_from_response` 会调用 `filter_media_delivery_paths()` 检查 MEDIA: 路径
- `media_delivery_allow_dirs` 配置限制了允许发送的目录，**`/tmp/` 默认不在白名单中**
- 被拦截后**静默失败**（不发图片，不报错），文本照常发送
- 日志中无 media delivery 调用记录，只有 "Flushing text batch"
- 这是 hermes 的安全设计：防止 agent 意外发送敏感文件（如 `/etc/passwd`）

**解决方案：**
1. **首选**：把文件复制到已允许的目录（如 hermes workspace）再发
2. **飞书发送**：`send_message(target=feishu, message="MEDIA:/path/file.png")` — 已验证可靠
3. **配置白名单**：在 hermes config 中 `gateway.media_delivery_allow_dirs` 添加 `/tmp/`（需重启 gateway）

**教训：**
- 企微发图的 `MEDIA:` 在 gateway 层面可能被路径白名单拦截
- 如果企微发图不确定能成功，**双保险**：同时发飞书
- nginx HTTP 链接在外网可能不通，不能依赖
- 发图失败后**必须检查 gateway 日志**（`~/.config/wecom-doc/logs/gateway.log`）看是否有 media delivery 错误

### 踩坑1 复现（2026-07-08 — 同一坑第二次踩）
- 场景：cookie 续期扫码，QR 生成在 `/tmp/wecom_qr_rgb.png`，用 `MEDIA:/tmp/wecom_qr_rgb.png` 发企微
- 结果：用户看不到图片，说"又不会发图片了？"
- 根因：和 2026-06-14 完全相同 — `/tmp/` 不在 `media_delivery_allow_dirs` 白名单，静默拦截
- **修复**：`cp /tmp/wecom_qr_rgb.png ~/.config/wecom-doc/workspace/wecom_qr_send.png` → `MEDIA:~/.config/wecom-doc/workspace/wecom_qr_send.png`
- **铁规**：任何要发给用户的文件，**永远先复制到 `~/.config/wecom-doc/workspace/`** 再用 `MEDIA:` 发，不要直接发 `/tmp/` 路径

### 踩坑2：lark-cli 跨应用发文件
- `lark-cli im +messages-send --user-id <open_id> --file ./file.png --as bot`
- 报 `open_id cross app` → 说明目标 open_id 不在当前 bot 应用下
- 解决：确认 open_id 属于当前 bot 所在应用，或用 `send_message(target=feishu)` 走 home channel

## 文件交付优先级

当需要给用户发送文件/图片时，按以下优先级：

1. **直接 `MEDIA:` 语法**（在回复中包含）→ 最简单
2. **`send_message(target=feishu) + MEDIA:`** → 发飞书，已验证可靠
3. **lark-cli 发飞书** → 需要确认 open_id 和 bot 应用匹配
4. **nginx HTTP 链接** → 备选，确认用户外网能访问

## ⚠️ 绝对不要做的事

- ❌ 给用户一个本地文件路径让他自己找（用户看不到服务器文件系统）
- ❌ 只发 nginx 链接不验证外网可达性
- ❌ 企微发图失败后默默换方式不告知用户
- ❌ 反复尝试同一种失败方法（最多2次，第3次必须换方案）
- ❌ 假设 `MEDIA:` 语法在所有平台都表现一致（每个平台有差异）
