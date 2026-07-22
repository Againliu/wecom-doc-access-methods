# SmartPage 删除 Block — 完整探索记录（2026-07-17）

## 浏览器键盘路径（✅ 已验证跨 session 持久化）

**编辑流程**：
1. Playwright + storage_state 打开 SmartPage
2. `page.evaluate` 定位目标 block DOM 元素（`[data-block-id="xxx"]`）
3. `page.mouse.click(x+50, y+h/2)` 点击 block
4. `page.keyboard.press("Control+a")` 全选 block 文字
5. `page.keyboard.press("Delete")` 清空文字
6. 等待 2 秒（让 changeset 提交）
7. `page.keyboard.press("Backspace")` 删除空 block
8. 等待 3-5 秒自动保存
9. 重新打开验证：`pageStore.children` 数量减少

**验证结果**：block 数量 4→3，跨 session 重新打开确认持久化。

## 拦截到的完整删除请求体

从 `submit_command` POST 请求拦截（Playwright `page.on("request")`）：

```json
{
  "sid": "<body_sid from clientVars.collab_client_vars.client.sid>",
  "command": {
    "id": <timestamp_ms>,
    "pad_id": "<padId from clientVars.padId>",
    "mutations": [
      {
        "path": ["props", "title_changeset"],
        "args": {
          "id": "<block_id>",
          "type": 1,
          "props": {
            "title_changeset": {
              "changeset": "Z:0>0$",
              "apool": "{\"numToAttrib\":{},\"nextNum\":0}"
            }
          },
          "updated_at": <ts>,
          "updated_by": "<vid>"
        },
        "operation": 2,
        "operation_type": 0,
        "meta": {}
      },
      {
        "args": {
          "id": "<block_id>",
          "type": 1,
          "enabled": false,
          "props": {},
          "updated_at": <ts+1>,
          "updated_by": "<vid>"
        },
        "operation": 2,
        "operation_type": 0,
        "meta": {}
      },
      {
        "args": {
          "id": "<page_id>",
          "type": 5,
          "child_id": "<block_id>",
          "updated_at": <ts+2>,
          "updated_by": "<vid>",
          "props": {}
        },
        "operation": 5,
        "operation_type": 0,
        "meta": {}
      }
    ],
    "user_infos": [
      {
        "identity": {
          "vid": "<vid>",
          "uid": "<uid>"
        },
        "name": "<userName>",
        "img_url": "<avatarUrl>",
        "corp_id": "<corpId>",
        "corp_name": "<corpName>",
        "extern_name": "<userName>",
        "from_corp_id": "<corpId>"
      }
    ],
    "user_actions": [],
    "extras": {
      "affected_page_ids": ["<page_id>"]
    },
    "create_timestamp": <ts>,
    "pad_version": <rev>
  },
  "from_type": 0,
  "req_tag": "<random_tag>",
  "req_ts": <ts+1>
}
```

## 3 步 Mutation 说明

| 步骤 | operation | 作用 | 关键字段 |
|---|---|---|---|
| 1. 清空 changeset | 2 | 把 block 文字内容清空 | `path: ["props","title_changeset"]`, `changeset: "Z:<len>-<len>$"` |
| 2. 禁用 block | 2 | 设置 `enabled: false` | 无 `path` 字段, `args.enabled: false` |
| 3. 从 children 移除 | 5 | 从页面的 children 列表中删除 block ID | `args.child_id`, `args.type: 5` |

## operation 枚举值

| 值 | 含义 | args 特征 |
|---|---|---|
| 1 | 创建 block | 有 `created_at`, `created_by`, `parent_id` |
| 2 | 修改 block | 有 `updated_at`, `updated_by` |
| 5 | 更新页面 children | 有 `child_id`, `type: 5` |

## API 直接删除路径（⚠️ 待调试）

**状态**：`submit_command` POST 返回 `ret:0, msg:"OK"`，但重新打开后 block 未删除。

**可能原因**：
1. `Z:0>0$` 是空操作（0→0），但 block 有实际内容（如 15 字符 = base-36 `f`）。需要用 `Z:f<f-f$` 先清空实际内容。
2. `pad_version` 可能不是最新值 — 需要在发请求前先触发一个操作（如点击）让客户端刷新 rev。

**已验证的字段要求**：
- `create_timestamp` 和 `pad_version` 必须在 `command` 对象内部（不在顶层）
- `user_infos` 的 `name`、`img_url`、`corp_id` 都是必填（空字符串会被 `ret:-20011` 拒绝）
- `corp_id` 和 `from_corp_id` 必须是数字字符串（如 `"1970325043983438"`），空字符串报 `ret:-5002 invalid value for uint64`
- `vid`（不是 `userId`）用于 `updated_by` — `userId` 有 `p.` 前缀会被拒绝
- URL 中的 `sid` 参数是 collab session ID（如 `1qJaOYxhNG0uEUdpAEdkVQAA`），与 body 中的 `sid`（WebSocket session ID，如 `895475889537`）不同

## 关键变量获取路径

| 变量 | 获取方式 | 示例值 |
|---|---|---|
| `body_sid` | `clientVars.collab_client_vars.client.sid` | `"895475889537"` |
| `vid` | `clientVars.vid` | `"1688853271761250"` |
| `rev` | `clientVars.collab_client_vars.rev` | `7` |
| `padId` | `clientVars.padId` | `"a1_AMgAkng0AMMCNK8wXXz0qQ0aeL0J6_a"` |
| `page_id` | `AppStore.pageStore.id` | `"yYWhm1"` |
| `block_id` | `AppStore.pageStore.children` 数组 | `["jkStNZ", "QXW834", ...]` |
| `uid` | `clientVars.userInfo.uid` 或 `basicClientVars.userInfo.wedriveUid` | `"13102700871901602"` |
| `corpId` | `clientVars.userInfo.corp_id` | `"1970325043983438"` |
| `userName` | `basicClientVars.userInfo.userName` | 从页面获取 |
| `imgUrl` | `basicClientVars.docInfo.ownerInfo.ownerAvatar` | URL |
| `xsrf` | 从拦截的请求 URL 提取（`xsrf=([a-f0-9]+)`）或 resource timing | `"39960f5e6d67a6ca"` |
| `url_sid` | 从拦截的请求 URL 提取（`sid=([^&]+)`） | `"1qJaOYxhNG0uEUdpAEdkVQAA"` |

## 测试文档

- 测试 SmartPage：`https://doc.weixin.qq.com/smartpage/a1_AMgAkng0AMMCNK8wXXz0qQ0aeL0J6_a`
- 创建方式：MCP `smartpage_create(title, pages)` — bot 创建，用户有编辑权限
