# m4_ 思维导图 Engine API 提取与编辑探索（2026-07-16）

## 概述

通过 React fiber 树从企微思维导图页面提取到内部 engine 对象（171 个方法），并验证了键盘编辑（Tab 添加子节点 + 键盘输入修改文本）可自动保存到服务器。

## Engine 对象提取路径

```
canvas.Mind_mindCanvas__Vp1oy
  → parentElement: DIV.Mind_wrapper__McYcU
    → find key starting with __reactInternalInstance$xxx
      → BFS traverse fiber tree
        → find memoizedProps.engine (object with 171 methods)
```

```javascript
// 提取函数（可注入到 page.evaluate）
window.__findEngine = function() {
    const canvas = document.querySelector('canvas:not([style*="display: none"])');
    if (!canvas) return null;
    let element = canvas.parentElement;
    let fiberKey = Object.keys(element).find(k => k.startsWith('__react'));
    while (!fiberKey && element.parentElement) {
        element = element.parentElement;
        fiberKey = Object.keys(element).find(k => k.startsWith('__react'));
    }
    if (!fiberKey) return null;
    let fiber = element[fiberKey];
    if (!fiber.stateNode && fiber.child) fiber = fiber.child;
    const queue = [fiber];
    const visited = new Set();
    while (queue.length > 0) {
        const f = queue.shift();
        if (!f || visited.has(f)) continue;
        visited.add(f);
        const props = f.memoizedProps || {};
        if (props.engine && typeof props.engine === 'object') return props.engine;
        if (f.child) queue.push(f.child);
        if (f.sibling) queue.push(f.sibling);
    }
    return null;
};
```

## 方法签名（从 toString() 分析）

| 方法 | 签名 | 说明 |
|---|---|---|
| `addNode(e, t)` | `addNode(operationType, {defaultTitle, changeSelect, enterEdit})` | e=操作类型常量（待确定），t=选项 |
| `updateTopic(e, t)` | `updateTopic(text, shouldCover)` | e=文本，t=是否覆盖。修改**当前选中节点**的标题 |
| `dfsAllNode(e, t)` | `dfsAllNode(callback, callback2)` | 两个参数都是回调函数 |
| `sendCommand(e, t, i)` | `sendCommand(operation, data, {shouldEmit, record, traceCategory})` | 通用命令分发器，调用 world.getSystem().excute() |
| `getRootId()` | 无参数 → `"root"` | ✅ 验证可用 |
| `getRecordInfo()` | 无参数 → `{canUndo, canRedo}` | ✅ 验证可用 |
| `switchCollapse(e, t)` | `switchCollapse(nodeId, collapse)` | e=节点ID，t=是否折叠 |
| `changeIndent(e)` | `changeIndent(increase)` | e=true增加缩进 |
| `takeSnapshot()` | async, 3 个可选参数 | ✅ 调用成功 |
| `setEditorFocus()` | 无参数 | ✅ 调用成功（但无 contenteditable 出现） |

## engineConfig 属性

| 属性 | 类型 | 说明 |
|---|---|---|
| `textContainerEl` | DIV | `Mind_text-container__2HELZ`，含 caret 光标元素 |
| `canvas` | CANVAS | `Mind_mindCanvas__Vp1oy` |
| `mask` | DIV | `Mind_mask__NTazB` |
| `containerEl` | DIV | `Mind_wrapper__McYcU` |
| `editConfig` | object | `editorFeatureConfig`, `notesPreviewEl`, `maxNodeCount` |
| `getLatestRev` | function | 获取最新版本号 |

## fileData 结构

`clientVars.collab_client_vars.fileData` — 反映当前状态（不是初始数据，编辑后会更新）：

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
          {"id": "yyy", "title": "已编辑的标题", "freshTitle": null}
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

## 已验证的编辑操作

| 操作 | 方法 | 持久化 | 验证方式 |
|---|---|---|---|
| 添加子节点 | 点击 canvas 选中根节点 → Tab | ✅ 跨 session | fileData 子节点 3→4→5 |
| 修改节点文本 | 点击节点 → F2/双击 → 键盘输入 | ✅ 跨 session | 标题 "分支主题3"→"直接输入测试" |
| 自动保存 | 无需显式调用 | ✅ 服务器自动 | editnotify POST + fileData 更新 |

## 关键发现

1. **caret 高度始终 0px** — 即使编辑模式激活，caret height 不变，不能用 caret 高度判断是否在编辑
2. **无 contenteditable 元素** — 编辑通过 canvas 事件处理，不经过 DOM 编辑器
3. **键盘事件不经过 sendCommand** — Tab/Enter 直接通过 React 事件处理，sendCommand hook 捕获不到
4. **fileData 反映当前状态** — 不是初始数据，编辑后会更新
5. **协同通过 HTTP 非 WebSocket** — editnotify POST + collab_client_vars，无 WS 消息

## JS 源码 ADD 常量

从 chunk JS 文件搜索到的常量：`ADD_CHILD`, `ADD_CHILD_NODE`, `ADD_NODE`, `ADD_DETACHED`, `ADD_NODE_LIST`, `ADD_BOUNDARY`, `ADD_LABEL`, `ADD_MARKER` 等

但通过 engine.addNode 传字符串常量返回 null — 可能需要引擎内部的常量对象引用（minified `p.F.*`）

## 下一步方向

1. 找到 addNode 的正确操作类型常量（需访问 minified module `p.F`）
2. 尝试 dfsAllNode(callback) 遍历所有节点（需要选中节点后回调才有数据）
3. p3_/f4_ 用同样的 React fiber 方案（需改搜索策略从 SVG 元素开始）
4. 检查 engineConfig.editConfig.editorFeatureConfig 是否有编辑模式入口
