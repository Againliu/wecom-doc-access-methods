# e3_ 电子表格浏览器写入 API（2026-07-23 实测闭环）

## 状态：✅ 已闭环（纯 API 写入 + 服务端持久化验证通过）

## 核心发现

企微 e3_ 电子表格使用 **OT/Mutation 协同模型**。写入数据需要通过 mutation 系统：

```
keyboard event → 生成 mutation → mutationApi.applyMutation (本地) → commitService.commitMutation (服务端)
                                                                  ↓
                                                          WebSocket USER_CHANGES 帧 → 服务端持久化
```

## 关键 API 入口

```javascript
const app = window.SpreadsheetApp;
const ma = app.mutationApi;           // 本地应用 mutation
const cs = app.commitService;          // 提交到服务端（发 WS）
const wb = app.workbook;
const sheet = wb.worksheetManager.sheetList[0];
const sheetId = sheet.cellDataGrid.usedRange.sheetId;
```

## Mutation 格式（type=17 = SetCellValue）

```javascript
{
    type: 17,                                    // 17 = SetCellValue
    gridRangeData: {                             // ⚠️ 必须是 GridRange 类实例（有 isInvalid 等方法）
        sheetId: "BB08J2",
        startRowIndex: 40, endRowIndex: 40,     // 单 cell: start=end
        startColIndex: 8, endColIndex: 8
    },
    cell: {                                      // ⚠️ 必须是 Cell 类实例（有 getAuthor 等方法）
        type: 4,                                 // 4=string, 2=number
        value: "写入内容",
        dataValidationResult: null,
        ignoredErrorType: null
    },
    _Bdu: false
}
```

## 🚨 关键 Pitfall：不能替换 cell/gridRangeData 对象

**只能修改属性值，不能替换整个对象**。因为 cell 和 gridRangeData 是类实例（有 `isInvalid()`/`getAuthor()` 等方法），替换为 plain object 会导致 applyMutation/commitMutation 校验失败。

```javascript
// ❌ 错误：替换整个对象 → 丢实例方法 → "isInvalid is not a function"
m.cell = {type: 4, value: "xxx"};
m.gridRangeData = {sheetId: "...", startRowIndex: 40, ...};

// ✅ 正确：只改标量属性，保留类实例
m.cell.value = "xxx";
m.cell.type = 4;
m.gridRangeData.startRowIndex = 40;
m.gridRangeData.endRowIndex = 40;
m.gridRangeData.startColIndex = 8;
m.gridRangeData.endColIndex = 8;
```

## 获取 Mutation 实例的方法

Mutation 类是混淆的（ctor 名 `t`），无法直接 `new`。**通过 monkey-patch commitMutation 捕获键盘编辑产生的真实实例**：

```javascript
// 安装 patch
const cs = app.commitService;
const origCommit = cs.commitMutation.bind(cs);
cs.commitMutation = function(e) {
    if (e?.options?.mutations?.length > 0) {
        window.__capturedMutation = e.options.mutations[0];  // 保存实例引用
        window.__capturedOptions = {
            requestType: e.options.requestType,
            requestKey: e.options.requestKey,
            sheetId: e.options.sheetId,
            operateType: e.options.operateType
        };
    }
    return origCommit(e);
};

// 键盘编辑触发（方向键定位 + F2 + type + Enter）
// → patch 捕获 mutation 实例
```

## 完整写入流程

```javascript
async function writeCell(row, col, value, sheetId) {
    const m = window.__capturedMutation;
    const opts = window.__capturedOptions;

    // 保存原属性
    const saved = {
        sr: m.gridRangeData.startRowIndex, er: m.gridRangeData.endRowIndex,
        sc: m.gridRangeData.startColIndex, ec: m.gridRangeData.endColIndex,
        val: m.cell.value, typ: m.cell.type
    };

    // 只改标量属性（保留类实例方法！）
    m.gridRangeData.startRowIndex = row;
    m.gridRangeData.endRowIndex = row;
    m.gridRangeData.startColIndex = col;
    m.gridRangeData.endColIndex = col;
    m.cell.value = value;
    m.cell.type = 4;  // string

    // 1. 本地应用
    app.mutationApi.applyMutation(wb, m);

    // 2. 提交服务端（⚠️ 返回 Promise，必须 await！）
    await app.commitService.commitMutation({
        options: {
            requestType: opts.requestType || 5,
            requestKey: Date.now(),
            sheetId: sheetId,
            operateType: opts.operateType ?? 0,
            mutations: [m]
        }
    });

    // 3. 恢复原属性（避免副作用）
    m.gridRangeData.startRowIndex = saved.sr;
    m.gridRangeData.endRowIndex = saved.er;
    m.gridRangeData.startColIndex = saved.sc;
    m.gridRangeData.endColIndex = saved.ec;
    m.cell.value = saved.val;
    m.cell.type = saved.typ;
}
```

## commitMutation 返回 Promise（重要）

```javascript
const ret = cs.commitMutation(arg);
// ret 是 Promise，不是 generator！必须 await
await ret;  // ✅
// ret.next()  // ❌ Promise 没有 next
```

## WS 协议

- WebSocket: `wss://doc.weixin.qq.com/websocket/?tag=<docid>&...`
- Socket.IO 风格：`42["post", "{JSON}"]`
- **数据变更帧**：`type: "USER_CHANGES"`（含 generalpacket + mutations 序列化）
- **光标帧**：`type: "CURSOR_MESSAGE"`（含 cookie + 光标位置）
- **心跳**：`type: "HEART_BEAT"`（15s 间隔）

## 替代方案：键盘模拟写入（已验证可用）

如果不想用 mutation API，键盘模拟也可行（100% 持久化）：

1. 点击 canvas 获取焦点
2. 方向键移动到目标 cell（ArrowDown/ArrowRight）
3. F2 进入编辑模式
4. `keyboard.type(value)`
5. Enter 确认

**缺点**：需要方向键定位（坐标点击不稳定），写入速度慢。推荐用 mutation API。

## 实测验证记录（2026-07-23）

| 测试值 | 写入位置 | 本地读回 | WS USER_CHANGES | 重载持久化 |
|--------|---------|---------|-----------------|-----------|
| PROBE1 | 6,0 | ✅ | —（键盘路径） | ✅ |
| ARROW1 | 18,2 | ✅ | ✅ | ✅ |
| SEED1-D | 13-19,3 | ✅ | ✅ | ✅ |
| **API_V4_FINAL** | **40,8** | **✅** | **✅** | **✅** |

## 探索历程

| Phase | 发现 |
|-------|------|
| 1 | setCellDataAtPosition 存在但只写本地内存；手动键盘编辑可持久化 |
| 2 | setCellDataAtPosition 值格式（克隆 cell 构造器）；PROBE1 重载后仍在 |
| 3 | mutationApi.applyMutation / commitService.commitMutation 发现 |
| 4 | applyMutation 不被键盘触发；commitMutation 接口签名获取 |
| 5 | 坐标点击不稳定；behaviorApi 非写入入口 |
| 5b | 方向键定位可靠；commitMutation 抓到 mutation 格式 |
| 6 | clone mutation 缺实例方法（isInvalid/getAuthor） |
| 6b | 直接改原实例仍失败（替换了 cell/gr 对象） |
| **6d** | **只改标量属性保留实例 → 闭环！** |

## 测试文档

- 测试电子表格（可删）：`https://doc.weixin.qq.com/sheet/e3_AMgAkng0AMMCN8zGRYGZ1StqUJZMn_a`
