# 企微文档浏览器编辑全类型探索记录（2026-07-16）

## 一、已验证：w3_/e3_/s3_ 浏览器键盘增删改

### 统一编辑流程

1. 用 Playwright + storage_state 打开文档
2. 定位编辑入口：
   - w3_ 微文档：点击 `#melo-hidden-editor`（contenteditable，parent class `hidden-editor`）
   - e3_ 电子表格：双击 canvas 上的单元格（需先用 evaluate 获取 canvas 实际坐标）
   - s3_ 智能表格：单击 canvas 数据行区域 → 双击进入编辑
3. `#alloy-rich-text-editor`（e3_/s3_）或 `#melo-hidden-editor`（w3_）出现
4. 用 `page.evaluate` 聚焦编辑器（绕过 Playwright 可见性检查）
5. `page.keyboard.type()` 输入文字
6. 按 Enter 确认（e3_/s3_ 需要 Enter；w3_ 自动保存）
7. 等待 5-8 秒自动提交到服务器

### 验证结果

| 类型 | 增 | 删 | 改 | 读回验证方式 | 读回确认内容 |
|---|---|---|---|---|---|
| w3_ 微文档 | ✅ | ✅ | ✅ | MCP get_doc_content | "改写后的内容-LeiLei验证" |
| e3_ 电子表格 | ✅ | ✅ | ✅ | wecom_doc_reader CLI | "e3_电子表格改写后-LeiLei验证" |
| s3_ 智能表格 | ✅ | — | ✅ | MCP smartsheet_get_records | "测试记录1s3浏览器写入-LeiLei验证" |

### 编辑器架构对比

| 属性 | w3_ 微文档 | e3_ 电子表格 | s3_ 智能表格 |
|---|---|---|---|
| padType | doc | sheet | smartsheet |
| canvas 数量 | 4 | 4 (2个可见) | 1 |
| contenteditable ID | `#melo-hidden-editor` | `#alloy-rich-text-editor` + `#alloy-simple-text-editor` | `#alloy-rich-text-editor` |
| `window.pad` 对象 | ✅ 有 | ❌ 无 | ❌ 无 |
| `SpreadsheetApp.workbook` | ❌ 无 | ✅ 有 | ❌ 无 |
| 自动提交 | ✅ 5-8秒 | ✅ Enter触发 | ✅ Enter触发 |
| `can_edit` | 1 | 1 | 1 |
| `isCreator` | false(API创建) | false(API创建) | false(API创建) |

### 关键权限发现

- API 创建的文档：`isCreator: false`，但 `can_edit: 1`（有编辑权限）
- 浏览器 UI 创建的文档：`isCreator: true`（用户是创建者）
- 两种方式创建的文档，浏览器用户都有编辑权限

## 二、待探索：m4_/p3_/f4_ 浏览器编辑

### 原则

**人能在网页里操作的，浏览器自动化也应该能操作。** 如果当前方法不工作，说明方法不对，不是"不可行"。结论应该是"方法待探索"，不是"不可行"。

### m4_ 思维导图 — 键盘编辑已验证 + engine API 已找到（2026-07-16 v3）

**✅ 键盘编辑已确认可用**：Tab 添加子节点 + 键盘输入修改文本 + 自动保存到服务器（跨 session 验证）。

**已验证编辑操作**：

| 操作 | 方法 | 持久化 | 验证方式 |
|---|---|---|---|
| 添加子节点 | 点击 canvas 选中根节点 → Tab | ✅ 保存到服务器 | fileData 子节点数 3→4→5 |
| 修改节点文本 | 点击节点 → F2/双击 → 键盘输入 | ✅ 保存到服务器 | fileData 标题"分支主题3"→"直接输入测试" |
| 自动保存 | 无需显式调用 | ✅ 服务器自动接收 | editnotify POST + 下次打开 fileData 已更新 |

**编辑流程**：打开文档 → click canvas 选中根节点 → Tab 添加子节点 → type 输入文本 → Enter 确认 → 等 5-10 秒自动保存

**⚠️ 注意**：caret 高度始终 0px（不能用它判断编辑模式）；点击位置必须命中节点；F2/双击可能激活了编辑模式即使无可见 contenteditable。

**engine 对象提取路径**（通过 React fiber 树）：
1. 从 `canvas.Mind_mindCanvas__Vp1oy` 父元素找 `__reactInternalInstance$xxx`
2. BFS 遍历 fiber 树 → `memoizedProps.engine` → 171 个方法

**方法签名（从 toString 分析）**：
- `addNode(operationType, {defaultTitle, changeSelect, enterEdit})` — 操作类型常量待确定
- `updateTopic(text, shouldCover)` — 修改当前选中节点标题（第一参数是文本，不是 nodeId！）
- `dfsAllNode(callback, callback2)` — 两个参数都是回调函数
- `sendCommand(operation, data, {shouldEmit, record, traceCategory})` — 通用命令分发器

**JS 源码 ADD 常量**：`ADD_CHILD`, `ADD_CHILD_NODE`, `ADD_NODE`, `ADD_DETACHED` — 但传字符串到 addNode 返回 null，可能需要引擎内部常量对象引用

### p3_ 幻灯片

**已探索**（2026-07-16 v3 — 全量 DOM 扫描）：
- `padType: "slide"`, `privilege_can_edit: true`, `isCreator: true`
- 9 个 canvas + 16 个 SVG, 0 个 contenteditable, 1 个 textarea
- **无 engine 对象** — p3_ 使用 service 架构而非 engine
- 找到 5 个 service 对象：`canvasService`(21方法) / `slideListService`(45方法) / `guidesManager`(13方法) / `menuManager`(30方法) / `themeColorManager`(23方法)
- `slideListService` 方法最多（45 个），含 slideSelectedReaction / currentSlideReaction / handleSlideSizeChange 等
- 双击后出现 CopyPasteAssist textarea（剪贴板辅助，非编辑器）
- fileData: null（p3_ 不使用 fileData 格式）
- **下一步**：通过 `slideListService` 或 `canvasService` 的方法操作幻灯片内容

### f4_ 流程图

**已探索**（2026-07-16 v3 — 全量 DOM 扫描）：
- `padType: "flowchart"`, `privilege_can_edit: true`, `isCreator: true`
- 0 个 canvas, 58 个 SVG, 使用 mxGraph 库渲染
- **engine 找到**（26 方法）但仅管多标签页（addTab/removeTab/switchTabWithUndoRedo）
- **双击后 INPUT 元素出现** — 可能是节点文本编辑器！
- **fileData 是 mxGraph XML 格式**（draw.io 兼容）：`<mxfile><diagram><mxGraphModel>...<mxCell>...`
- **下一步**：①双击流程图节点触发文本编辑 ②直接修改 mxGraph XML 回写 ③用 mxGraph JS API（mxGraphModel/mxCell）编程编辑

### SmartPage 智能文档 — 编辑+删除已验证（2026-07-17 v14）

**✅ 编辑已确认可用**：直接构造 `submit_command` POST 请求 + EtherPad changeset，服务器返回 `ret:0, msg:"OK"`，内容跨 session 持久化。

**✅ 删除已确认可用**：浏览器键盘操作（清空文字 + Backspace），跨 session 持久化验证通过。

**删除流程**：
1. 点击目标 block（`page.mouse.click`）
2. `Control+a` 全选 → `Delete` 清空文字
3. 等待 2 秒（让 changeset 提交到服务器）
4. `Backspace` 删除空 block → 自动保存
5. 重新打开验证：`pageStore.children` 数量减少

**拦截到的删除 mutation 格式**（3 步，详见 `references/smartpage-delete-block.md`）：
- `operation:2` 清空 changeset → `operation:2` enabled:false → `operation:5` 从 children 列表移除

**API 直接删除**：`submit_command` POST 返回 `ret:0` 但未持久化。原因：`Z:0>0$` 是空操作（0→0），block 有实际内容需要先用 `Z:<len>-<len>$` 清空。另外 `create_timestamp`/`pad_version` 必须在 `command` 对象内部，`user_infos` 的 name/img_url/corp_id 必填。

**编辑流程**：
1. Playwright + storage_state 打开 SmartPage
2. 从 `clientVars` 获取：`padId`, `vid`（数字用户ID）, `collab_client_vars.rev`（版本号）, `collab_client_vars.client.sid`
3. 拦截页面请求获取 `xsrf` token
4. 从 `AppStore.pageStore.children` 获取 block ID 列表
5. 构造 EtherPad changeset：`Z:<old_len_b36>><change_b36>-<old_len_b36>+<new_len_b36>$<new_text>`
6. 构造 `submit_command` POST 请求（见 SKILL.md 完整格式）
7. 用 `page.evaluate(fetch)` 发送 → `ret:0` = 成功
8. 等待保存，重新打开验证

**EtherPad changeset 格式**：
- 长度用 base-36 编码（0-9a-z）
- `Z:4>b-4+f$new_text` = 替换 4 字符为 15 字符
- 示例验证：block "Ew28rg" 从 "测试标题" → "SmartPage编辑成功验证"，跨 session 持久化

**关键发现**：
- `vid`（不是 `userId`）用于 `updated_by` 字段 — `userId` 有 `p.` 前缀会被服务器拒绝
- `pad_version` 从 `collab_client_vars.rev` 获取（每次编辑后递增）
- `create_timestamp` + `pad_version` + `createBlockIds` + `shouldCommit` + `committed` 都是必填字段
- 不需要 editor 实例、不需要 `lastCanWrite`、不需要 `__startCollabEdit` — 直接 HTTP POST
- `Content-Type: application/protojson`（不是 `application/json`）

**之前探索的路径（作为参考，不需要再走）**：
- `offlineEditAdapter.lastCanWrite` 可强制设为 `true`，但不创建 editor 实例
- `getEditorService()` 的 `createEditor` 在 prototype 上找到，但需要 DI 上下文对象
- `execCommand('insertText')` 修改 DOM 但不创建 dataCore mutation — 持久化失败
- **直接 `submit_command` API 是最简单、最可靠的编辑路径**

## 三、Playwright 技术要点

### canvas bounding_box 返回 None 的处理

```python
# ❌ 可能返回 None
box = await canvas.bounding_box()

# ✅ 用 evaluate 获取实际位置
cinfo = await page.evaluate("""() => {
    const c = document.querySelector('canvas');
    const r = c.getBoundingClientRect();
    return {x: r.x, y: r.y, w: r.width, h: r.height};
}""")
```

原因：某些 canvas 元素 CSS 设置了特殊属性（如 transform、display:none），Playwright 的 bounding_box 可能返回 None。`getBoundingClientRect()` 更可靠。

### 点击视口外元素的 workaround

```python
# ❌ 元素在 x:-10000 会超时
await element.click()

# ✅ 用 evaluate 直接聚焦
await page.evaluate("document.querySelector('#target')?.focus()")
```

### 找到正确的 canvas

e3_ 有 4 个 canvas，其中 2 个是 0x0 不可见的。需要过滤可见的 canvas：
```javascript
const canvases = document.querySelectorAll('canvas');
return Array.from(canvases).filter(c => c.getBoundingClientRect().width > 0);
```

### s3_ 智能表格点击位置

s3_ 的 canvas 从 y=144 开始。列标题在 y=144+20=164 附近，数据行从 y=190 开始。点击数据行需要 y >= canvas.y + 80。

### 全量 DOM 扫描找 engine/service 对象（p3_/f4_ 用）

当 canvas 数量 > 1（p3_ 有 9 个）或无 canvas（f4_ 用 SVG 渲染）时，`__findEngine` 从单一 canvas 搜索的策略失效。需要全量扫描所有 DOM 元素的 React fiber：

```javascript
// 1. 遍历所有 DOM 元素找 React fiber
const allElements = document.querySelectorAll('*');
for (const el of allElements) {
    let fiberKey = Object.keys(el).find(k => k.startsWith('__react'));
    if (!fiberKey) continue;
    
    let fiber = el[fiberKey];
    // BFS 这个 fiber 的子树
    const queue = [fiber];
    while (queue.length > 0) {
        const f = queue.shift();
        if (!f) continue;
        const props = f.memoizedProps || {};
        // 检查每个 prop 是否是有大量方法的对象（>10 方法 = engine/service）
        for (const [key, val] of Object.entries(props)) {
            if (val && typeof val === 'object' && !Array.isArray(val)) {
                const methods = Object.keys(val).filter(k => typeof val[k] === 'function');
                if (methods.length > 10) {
                    // 找到 engine/service 对象！
                    console.log(`${key}: ${methods.length} methods`);
                }
            }
        }
        if (f.child) queue.push(f.child);
        if (f.sibling) queue.push(f.sibling);
    }
}
```

**适用场景**：p3_ 幻灯片（找到 canvasService/slideListService 等 service 对象）、f4_ 流程图（找到 engine 对象，但仅管 tab）。

### 方法签名分析（minified JS）

当找到 engine 对象后，方法名可能不够明确。用 `toString()` 分析签名：

```javascript
// 获取方法的函数签名
const sig = engine.addNode.toString();
// → "(e,t)=>{this.sendCommand(e,{defaultTitle:t?.defaultTitle,...})}"
// 从中推断: e=操作类型, t=选项对象
```

**技巧**：通过签名中 `sendCommand` 的第一个参数名（如 `p.F.UPDATE_THEME_TOPIC`）可以推断操作类型常量的命名模式，然后搜索 JS chunk 源码找所有常量。

```javascript
// 搜索 JS chunk 找操作常量
const scripts = document.querySelectorAll('script[src]');
for (const s of scripts) {
    const resp = await fetch(s.src);
    const text = await resp.text();
    const matches = text.match(/ADD_[A-Z_]+/g);  // 找 ADD_ 开头的常量
}
```
