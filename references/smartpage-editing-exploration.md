# SmartPage（智能文档）编辑深度探索（2026-07-16 v2-v9）

> 脱敏版 — 不含公司/团队/个人信息

## 探索总结

**从"不可编辑"升级为"编辑器可激活，DI 上下文是最后障碍"**

| 探索轮次 | 发现 | 状态 |
|---|---|---|
| v2 | `lastCanWrite` 可强制 `true` + `__startCollabEdit()` 可调用 | ✅ |
| v2 | `execCommand('insertText')` 修改 DOM 成功 | ✅ |
| v2 | `submit_command` POST 发送到服务器（时间戳变更） | ✅ |
| v3 | 内容未持久化（DOM 改了但 reload 后消失） | ⚠️ |
| v4 | `dataDispatcher.commit()` 报错（需要 command 对象参数） | ⚠️ |
| v5 | `dataDispatcher` 方法签名分析（create/addMutation/commit） | ✅ |
| v5 | `collabAdapter.throttledFlushCommands()` 可调用 | ✅ |
| v5 | `composeCommands` 为空 — execCommand 未创建 mutation | ⚠️ |
| v6 | `execCommand` + `throttledFlushCommands` — 仍无持久化 | ⚠️ |
| v7 | 键盘输入（非 execCommand） — 0 个 mutation 被拦截 | ⚠️ |
| v8 | `createEditor` 在 prototype 上找到！但需要 DI 上下文 | ⚠️ |
| v9 | DI 上下文搜索 — 只找到 i18n 和 ARK_EXTENSION，都不是 | ⚠️ |

## dataCore 结构（`AppStore.dataService.dataCore`）

| 属性 | 子键 | 用途 |
|---|---|---|
| `offlineEditAdapter` | `lastCanWrite`, `isOnline`, `changesCache`, `syncOfflineEvent` | 可强制 `lastCanWrite=true` |
| `dataDispatcher` | `create`, `commit`, `addMutation`, `getCollabCenterAdapter` | 结构化编辑入口 |
| `api` | `getBlockById`, `getApool`, `loadChunkPage`, `duplicateBlock` | 数据读取 |
| `memoryCache` | `cache`, `recordEvents`, `globalAttribPool`, `blockFieldFactory` | 内存数据模型 |
| `collabAdapter` | `throttledFlushCommands`, `customSendUserChange`, `composeCommands` | 协同适配器 |
| `mode` | `"default"` | 编辑模式 |

## dataDispatcher 方法签名

```
create(e, t)      → new h.A(e, t)  — 创建命令对象，e=操作类型，t=数据
addMutation(e)    → e={mutation, command}  — mutation 有 pointer/args/invertMutation
commit(e)         → e={command}  — command 有 createBlockIds/mutations/shouldCommit/committed
```

## 编辑器 Service（`getEditorService()`）

**Prototype 方法**：
- `createEditor(ctx, {type})` — **关键**！ctx 需要有 `createInstance` 方法的 DI 上下文
- `addEditor(editor)` / `removeEditor(id)` / `getEditorById(id)`
- `getActiveEditor()` / `getAvailableEditors()` / `getFirstEditorByType(type)`
- `generateEditorId()`

**`createEditor` 签名分析**：
```javascript
function(e, t) {
    var r = this.generateEditorId();
    switch(t?.type) {
        case XDASHBOARD: n = $e; break;
        case XEXTERNAL: n = tt; break;
        default: n = En;
    }
    var o = e.createInstance(new u.d(n, [{...t, id: r}]));  // ← 需要 e.createInstance
    this.addEditor(o);
    return o;
}
```

**DI 上下文搜索结果**（v9 全量搜索）：
- `window` 上：`i18n`（有 createInstance 但是 i18n 库）+ `__ARK_EXTENSION_INSTANTIATION_SERVICE__`（空方法）
- `AppStore` 递归搜索 3 层：未找到
- React fiber 树遍历 500 节点：未找到

## block 结构

```javascript
pageStore = {
    id: "2sjW3N",
    table: "block",
    children: ["Ew28rg", "mM8Kti", "9tqDJT"],
    properties: {...},
    // 方法: getValue(), clone(), isEmpty(), isTitleEmpty(), isChildrenEmpty()
}
api.getBlockById(blockId)  // 返回 block 对象
```

## 根因分析

```
execCommand / 键盘输入
  → 修改 DOM（#root-editable 文本变化）
  → 但 composeCommands 为空（dataCore 未创建 mutation）
  → throttledFlushCommands 无内容刷出
  → 服务器只收到 browse_location（时间戳变）
  → 内容未保存

正确路径（待实现）：
  dataDispatcher.create(operationType, data)
  → addMutation({mutation, command})
  → commit({command})
  → throttledFlushCommands()
  → 服务器保存

但需要：
  - operationType 的正确值（从 JS 源码 h.A 构造函数找）
  - mutation 对象格式（pointer.table, pointer.id, args, invertMutation）
  - 或者：找到 DI 上下文 → createEditor → 编辑器处理键盘输入 → 自动创建 mutation
```

## 下一步

1. 从 JS chunk 源码搜索 `h.A` 构造函数和 operationType 枚举
2. 用 XMLHttpRequest hook 拦截 submit_command 请求体
3. 模拟 UI 编辑操作，hook addMutation 拦截真实 mutation 格式
4. 检查是否有"编辑模式"按钮需要先点击
