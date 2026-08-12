# SmartPage HTTP API 写入协议（2026-08-12 实测验证）

> **突破**：SmartPage 不需要 WebSocket/浏览器即可写入。HTTP API 直接提交 command 即可。之前"假成功"（ret=0 但不执行）的根因是 `Content-Type` 用了 `application/json` 而非 `application/protojson`。

## 端点

| 操作 | 方法 | 端点 | Content-Type |
|---|---|---|---|
| 读文档结构 | POST | `/smartcanvasread/opendoc` | `application/json;charset=UTF-8` |
| 写入 | POST | `/smartcanvaswrite/submit_command` | **`application/protojson`** ⚠️ |

## opendoc 读取

```python
requests.post('https://doc.weixin.qq.com/smartcanvasread/opendoc',
    json={'pad_id': PAD_ID, 'pad_ver': 0, 'req_ts': int(time.time())},
    cookies=cookies, headers={'Content-Type': 'application/json;charset=UTF-8'})
```

返回结构：
- `body.top_blocks[]` — 所有 block（含 root type=4、page type=5、内容块）
- `body.top_blocks[].children[]` — 子 block ID 列表
- `body.top_blocks[].parent_id` — 父 block ID
- `body.top_blocks[].props.title.text` — 标题文本
- `body.meta.pad_ver` — 当前版本号（写入时必须用最新值）
- `param.sid` — 会话 ID（写入时必需）

## submit_command 写入

### 请求格式

```python
requests.post('https://doc.weixin.qq.com/smartcanvaswrite/submit_command',
    json={
        'sid': sid,
        'command': {
            'pad_id': PAD_ID,
            'sid': sid,
            'id': int(time.time() * 1000),          # 整数
            'create_timestamp': int(time.time() * 1000),
            'pad_version': pad_ver,                   # 当前 pad_ver
            'shouldCommit': True,
            'committed': True,
            'createBlockIds': [],                     # 创建新 block 时填新 ID 列表
            'mutations': [...]                        # mutation 数组
        },
        'from_type': 0
    },
    cookies=cookies,
    headers={'Content-Type': 'application/protojson'})  # ⚠️ 关键！
```

### operation 枚举

| 值 | 名称 | 用途 |
|---|---|---|
| 1 | set | 设置 block 属性（标题/内容/parentId） |
| 2 | update | 更新 block 元数据 |
| 3 | listBefore | 在兄弟节点前插入 |
| 4 | listAfter | 在 parent 的 children 末尾添加 |
| 5 | listRemove | 从 parent 的 children 移除 |

### Mutation 格式

```python
{
    'pointer': {'id': block_id, 'table': 'block'},
    'operation': op_code,
    'args': {...}  # 因 operation 而异
}
```

### 各操作 args 格式

**改标题/内容（operation=1 set）**：
```python
{'id': block_id, 'type': 5, 'props': {'title': {'text': '新标题'}}}
```
⚠️ `operation=1 set` 会**覆盖整个 props**，包括已有内容。

**创建页面（createBlockIds + set + listAfter）**：
```python
# 1. createBlockIds: [new_id]（6字符随机字母数字）
# 2. mutation 1: set 新 block 属性
{'pointer': {'id': new_id, 'table': 'block'}, 'operation': 1,
 'args': {'id': new_id, 'type': 5, 'parentId': parent_id, 'enabled': True,
          'props': {'title': {'text': '页面标题'}}}}
# 3. mutation 2: listAfter 加到 parent 的 children
{'pointer': {'id': parent_id, 'table': 'block'}, 'operation': 4,
 'args': {'id': parent_id, 'childId': new_id, 'type': parent_type}}
```

**删除页面（listRemove）**：
```python
{'pointer': {'id': parent_id, 'table': 'block'}, 'operation': 5,
 'args': {'id': parent_id, 'childId': page_id, 'type': parent_type}}
```

**移动页面（设层级）**：
```python
# 1. listRemove 从旧 parent 移除
{'pointer': {'id': old_parent_id, 'table': 'block'}, 'operation': 5,
 'args': {'id': old_parent_id, 'childId': page_id, 'type': old_parent_type}}
# 2. listAfter 加到新 parent
{'pointer': {'id': new_parent_id, 'table': 'block'}, 'operation': 4,
 'args': {'id': new_parent_id, 'childId': page_id, 'type': new_parent_type}}
# ⚠️ 不要用 operation=1 改 parentId！会覆盖 props 清掉标题
```

### 关键字段类型

| 字段 | 类型 | 说明 |
|---|---|---|
| `id`（command 层） | int | 毫秒时间戳 |
| `create_timestamp` | int | 毫秒时间戳 |
| `pad_version` | int | 当前 pad_ver，每次写入后 +1 |
| `enabled` | bool | `True`/`False`，不是 `1`/`0` |
| `childId` | string | 驼峰命名，不是 `child_id` |
| `type`（listAfter args） | int | root=4, page=5 |
| block ID | string | **必须恰好 6 字符**随机字母数字 |

### 写入后必须刷新 pad_ver

每次 `submit_command` 成功后，必须重新调 `opendoc` 获取新的 `pad_ver`，下一次写入用新值。

## 错误码与排查

| 错误 | 根因 | 修复 |
|---|---|---|
| ret=0 但不执行 | Content-Type 用了 application/json | 改为 application/protojson |
| "字段 'command' 必填" | mutations 没包在 command 对象里 | mutations 放进 command.mutations |
| "id 期望为整数" | command.id 是字符串 | 改为 int |
| "sid cant be empty" | sid 没在 request body 顶层 | sid 放在 command 同级 |
| "duplicate field padId" | command 里同时有 pad_id 和 padId | 只保留 pad_id |
| "BLOCK_TYPE_UNSPECIFIED" | listAfter args 缺 type | args 里加 type:4(root)/5(page) |
| "block id len not 6" | block ID 不是 6 字符 | 用 6 字符随机字母数字 |
| "enabled bool not int" | enabled 用了 1/0 | 改为 True/False |

## Block 结构

```python
{
    'id': 'abc123',           # 6字符
    'type': 5,                # 4=root, 5=page
    'parent_id': 'parent_id',
    'children': ['child1', 'child2'],
    'props': {
        'title': {'text': '页面标题'},
        # 其他属性...
    }
}
```

## 完整写入示例

```python
import requests, json, time, random, string

state = json.load(open('/tmp/wecom_user_state.json'))
cookies = {c['name']: c['value'] for c in state.get('cookies', [])}
headers_json = {'Content-Type': 'application/json;charset=UTF-8', 'Origin': 'https://doc.weixin.qq.com'}
headers_proto = {'Content-Type': 'application/protojson', 'Origin': 'https://doc.weixin.qq.com'}

PAD_ID = 'a1_xxxxxxxxxxxxxxxxx'

# 1. 读取当前状态
r = requests.post('https://doc.weixin.qq.com/smartcanvasread/opendoc',
    json={'pad_id': PAD_ID, 'pad_ver': 0, 'req_ts': int(time.time())},
    cookies=cookies, headers=headers_json, timeout=15)
d = r.json()
sid = d['param']['sid']
pad_ver = d['body']['meta']['pad_ver']
blocks = {b['id']: b for b in d['body']['top_blocks']}

# 2. 创建新页面
new_id = ''.join(random.choices(string.ascii_letters + string.digits, k=6))
root_id = [b for b in d['body']['top_blocks'] if b['type'] == 4][0]['id']

cmd_id = int(time.time() * 1000)
command = {
    'pad_id': PAD_ID, 'sid': sid, 'id': cmd_id, 'create_timestamp': cmd_id,
    'pad_version': pad_ver, 'shouldCommit': True, 'committed': True,
    'createBlockIds': [new_id],
    'mutations': [
        {'pointer': {'id': new_id, 'table': 'block'}, 'operation': 1,
         'args': {'id': new_id, 'type': 5, 'parentId': root_id, 'enabled': True,
                  'props': {'title': {'text': '新页面'}}}},
        {'pointer': {'id': root_id, 'table': 'block'}, 'operation': 4,
         'args': {'id': root_id, 'childId': new_id, 'type': 4}}
    ]
}
r2 = requests.post('https://doc.weixin.qq.com/smartcanvaswrite/submit_command',
    json={'sid': sid, 'command': command, 'from_type': 0},
    cookies=cookies, headers=headers_proto, timeout=15)
assert r2.json()['head']['ret'] == 0

# 3. 刷新 pad_ver
r3 = requests.post('https://doc.weixin.qq.com/smartcanvasread/opendoc',
    json={'pad_id': PAD_ID, 'pad_ver': 0, 'req_ts': int(time.time())},
    cookies=cookies, headers=headers_json, timeout=15)
pad_ver = r3.json()['body']['meta']['pad_ver']
```

## 与浏览器方案对比

| 维度 | HTTP API | 浏览器 WebSocket |
|---|---|---|
| 环境要求 | 无（纯 HTTP） | 需要 headless 浏览器 |
| 稳定性 | ✅ 高 | ⚠️ WS 断连风险 |
| 速度 | ✅ 快（~0.3s/操作） | 慢（页面加载+JS 执行） |
| 批量操作 | ✅ 可循环 | 需逐页操作 |
| 层级设置 | ✅ listAfter/listRemove | 拖拽 UI |
| 标题修改 | ✅ set props.title | execCommand |
| 创建页面 | ✅ createBlockIds | UI 按钮 |
| 删除页面 | ✅ listRemove | 键盘清空+Backspace |

## 实战记录（2026-08-12）

- 在副本文档 `a1_AGIAUQZXAMsCNeYw4FfoHT2S1m3hR` 上完成全量同步
- 创建 114 个新页面 + 设置 99 个层级关系 + 删除 56 个多余页面 + 补充 43 个缺失页面
- 最终 130 页面与飞书知识库 130 节点完全匹配
- 零失败
