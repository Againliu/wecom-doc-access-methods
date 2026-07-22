# m4_ 思维导图 Engine API 探索记录

> 2026-07-16 深度探索。从"方法待探索"升级为"engine API 已找到（171 方法），参数和保存机制待完善"。

## Engine 对象提取方法

通过 React fiber 树可以访问思维导图引擎对象：

```javascript
// 1. 从 canvas 父元素找 React fiber key
const canvas = document.querySelector('canvas:not([style*="display: none"])');
let element = canvas.parentElement;
let fiberKey = Object.keys(element).find(k => k.startsWith('__react'));
while (!fiberKey && element.parentElement) {
    element = element.parentElement;
    fiberKey = Object.keys(element).find(k => k.startsWith('__react'));
}

// 2. BFS 遍历 fiber 树，找 memoizedProps.engine
let fiber = element[fiberKey];
if (!fiber.stateNode && fiber.child) fiber = fiber.child;
const queue = [fiber];
const visited = new Set();
while (queue.length > 0) {
    const f = queue.shift();
    if (!f || visited.has(f)) continue;
    visited.add(f);
    const props = f.memoizedProps || {};
    if (props.engine && typeof props.engine === 'object') {
        // 找到了！props.engine 就是引擎对象
        return props.engine;
    }
    if (f.child) queue.push(f.child);
    if (f.sibling) queue.push(f.sibling);
}
```

## React 组件树结构

```
C (mind, workbenchLoader, initRenderEl, onComplete)
  → ... (sub-app loader: onReady, initData, initDataInfo, bindSubApp, subAppEvent)
    → div.Pc_mind-group
      → div.Mind_wrapper
        → canvas.Mind_mindCanvas
      → function(engine, toolbarDisable)  ← engine 在这里
      → q(wrapRef, canvasRef, maskRef, fpsElRef, textContainerRef)
      → function(engine, disable)
```

## Engine 方法清单（171 个，关键方法）

### 节点操作
| 方法 | 用途 | 测试状态 |
|---|---|---|
| `getRootId()` | 获取根节点 ID | ✅ 返回 `"root"` |
| `addNode(...)` | 添加节点 | ⚠️ 返回 null，参数格式不对 |
| `removeNodes(...)` | 删除节点 | 未测试 |
| `removeNodeOnly(...)` | 仅删除节点 | 未测试 |
| `changeIndent(...)` | 改变缩进层级 | 未测试 |
| `switchCollapse(...)` | 折叠/展开 | 未测试 |
| `switchCollapseAll(...)` | 全部折叠/展开 | 未测试 |
| `spreadNodeLevel(...)` | 展开节点层级 | 未测试 |
| `moveToCenter()` | 移动到中心 | 未测试 |

### 文本编辑
| 方法 | 用途 | 测试状态 |
|---|---|---|
| `getTopic(nodeId)` | 获取主题（返回 "default" = 主题样式名） | ✅ 但不是文本内容 |
| `updateTopic(nodeId, text)` | 更新节点文本 | ✅ 调用成功 |
| `textEditBreakLine()` | 文本编辑中换行 | 未测试 |
| `resetEditorText()` | 重置编辑器文本 | 未测试 |
| `setEditorFocus()` | 设置编辑器焦点 | ✅ 调用成功（无 contenteditable 出现） |
| `setFocus(...)` | 设置焦点 | 未测试 |

### 命令系统
| 方法 | 用途 | 测试状态 |
|---|---|---|
| `sendCommand(cmd, ...)` | 通用命令分发 | ⚠️ "insertChild"/"addSibling" 等都返回 null |
| `undo()` / `redo()` | 撤销/重做 | 未测试 |
| `runFormatter(...)` | 运行格式化 | 未测试 |
| `takeSnapshot()` | 截取快照 | ✅ 调用成功 |

### 遍历/查询
| 方法 | 用途 | 测试状态 |
|---|---|---|
| `dfsAllNode(...)` | 深度优先遍历所有节点 | ⚠️ `{includeSummary: false}` 报错 |
| `getRecordInfo()` | 获取撤销/重做状态 | ✅ `{canRedo: false, canUndo: false}` |
| `getRootId()` | 获取根节点 ID | ✅ |
| `getNodeItemLevel(...)` | 获取节点层级 | 未测试 |
| `getExtension(...)` | 获取扩展属性 | 未测试 |
| `getNodeCount()` | 获取节点数 | 未测试 |
| `saveSelect()` | 保存选中状态 | 未测试 |

### 样式
| 方法 | 用途 | 测试状态 |
|---|---|---|
| `getNodeStyle(...)` | 获取节点样式 | 未测试 |
| `updateColorTheme(...)` | 更新配色主题 | 未测试 |
| `setColorTheme(...)` | 设置配色主题 | 未测试 |
| `setFontFamilyUtils(...)` | 设置字体 | 未测试 |

## engineConfig 关键属性

| 属性 | 说明 |
|---|---|
| `textContainerEl` | 文本容器 DOM 元素引用（可能是文本编辑入口） |
| `canvas` | canvas 元素引用 |
| `mask` | 遮罩元素 |
| `containerEl` | 容器元素 |
| `editConfig` | 编辑配置 |
| `getLatestRev` | 获取最新版本号 |
| `uploadImage` | 图片上传函数 |

## fileData 数据结构

`clientVars.collab_client_vars.fileData` 是 JSON 字符串：

```json
{
  "content": [{
    "rootTopic": {
      "id": "root",
      "title": "中心主题",
      "collapse": false,
      "children": {
        "attached": [
          {"id": "xxx", "title": "分支主题1", "freshTitle": true},
          {"id": "yyy", "title": "分支主题2", "freshTitle": true}
        ]
      }
    },
    "theme": {"topic": "default"},
    "title": "",
    "id": "",
    "relationships": []
  }],
  "metaData": {}
}
```

## 权限状态

- `privilegeAttribute.can_edit: true` — **有编辑权限**（`clientVars.can_edit` 为 null 是误导）
- `isCreator: true`, `isOwner: true`
- `rightFlag: 2048`

## 网络请求

| 请求 | 说明 |
|---|---|
| `GET dop-api/mind/data/get?id=xxx&xsrf=xxx` | 获取思维导图数据 |
| `POST wedoc/editnotify` | 编辑通知（页面加载时自动发送） |

注意：API 端点是 `dop-api/mind/data/get`，不是 `dop-api/get/mind`。

## 已尝试但未成功的操作

| 操作 | 结果 |
|---|---|
| 双击 canvas 中心 | 无编辑框出现 |
| 单击 + 空格/Enter/Tab/F2/Insert/Control+Enter | 无编辑框出现 |
| `dispatchEvent` pointerdown/pointerup/click/dblclick | 无效果 |
| 大纲模式按钮（`toolbar_outline__kdx1j`） | 点击后无编辑器出现 |
| `addNode()` 无参数 | null |
| `addNode(rootId)` | null |
| `addNode(rootId, "title")` | null |
| `addNode({parentId, title, position})` | null |
| `sendCommand("addNode", {parentId, title})` | null |
| `sendCommand("insertChild"/"addSibling"/"editTopic"等, rootId)` | null |
| `dfsAllNode({includeSummary: false})` | Error: "t is not a function" |
| `dfsAllNode({})` | Error: "t is not a function" |
| `dfsAllNode(true)` | Error: "t is not a function" |

## 下一步探索方向

1. 检查 `engineConfig.textContainerEl` 的 DOM 元素类型和属性（是否 contenteditable）
2. 通过 `engineConfig.editConfig` 找到编辑模式入口
3. 研究 `sendCommand` 的正确命令名（可能不是英文名，可能是数字 ID 或内部命令码）
4. 直接修改 `fileData` JSON 并触发 re-render
5. 检查 WebSocket 连接 — 协同编辑可能通过 WS 发送变更
6. 研究节点 model 对象 — `addNode` 可能需要传入 model 实例而非简单参数
7. 先选中节点再右键 — 右键在 canvas 空白处只显示画布操作菜单，选中节点后右键可能显示节点操作菜单

## 工具栏和右键菜单

**工具栏按钮**：大纲模式 / 插入 / 结构 / 主题 / 格式

**右键菜单（canvas 空白处）**：粘贴 / 仅粘贴文本 / 全选 / 设置格式 / 画布放大 / 画布缩小 / 主题级别（1-6 级）
