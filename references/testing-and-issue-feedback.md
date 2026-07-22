# 测试方案 + GitHub Issue 自动反馈机制

> 本文件由 SKILL.md 拆分而来(2026-07-21)。

## 测试方案

### 单元测试（离线，不需要浏览器）

```bash
cd scripts/
python3 test_wecom_doc_reader.py --offline
```

覆盖：URL 解析、base64+zlib 解码（含 padding 边界）、列定义解析（k前缀/数字键）、select 选项提取。

### 集成测试（在线，需要浏览器+cookie）

```bash
cd scripts/
python3 test_wecom_doc_reader.py --state-dir /path/to/wecom_states --user _shared --url "https://doc.weixin.qq.com/smartsheet/s3_xxx"
```

覆盖：单子表读取、多子表读取（24+子表）、错误处理（无效URL/不存在文档）、性能测试（记录数/耗时）。

### 测试维度

| 维度 | 测试点 | 验证方法 |
|------|--------|----------|
| URL 解析 | s3_/w3_/e3_/m4_ 格式 + scode/tab 参数 | `parse_doc_url()` 返回值断言 |
| 解码 | base64 roundtrip + padding 补齐 + 无效数据 | 编码→解码对比 |
| 列定义 | k前缀/数字键 + select 选项 + 字段类型 | `_parse_column_defs()` 返回值 |
| 单子表 | 指定 tab 读取 + 记录数 + 字段数 + 首条记录 | `read(user, url+tab)` |
| 多子表 | 全量子表 + sheets 数组 + 记录总数一致 + 无空表 | `read(user, url)` |
| 错误处理 | 无效URL + 不存在文档 + 异常捕获 | 返回 `success: False` |
| 性能 | 24子表读取耗时 < 120s | 计时断言 |

---

## GitHub Issue 自动反馈机制

### 原理

skill 在遇到关键错误时，自动在 GitHub 仓库创建 issue（带 `auto-reported` label），实现"问题→反馈→修复"闭环。

### 配置

```bash
# 环境变量（必须）
export GITHUB_TOKEN="ghp_xxx"           # GitHub API token
export GITHUB_REPO="Againliu/wecom-doc-access-methods"  # 仓库（可选，有默认值）
export ISSUE_AUTO="1"                    # 1=自动提交, 0=只打印不提交
```

### 自动触发点

| 触发条件 | issue 标题 |
|---------|-----------|
| 未拦截到 get/sheet 请求 | "dop-api 未拦截到 get/sheet 请求" |
| base64+zlib 解码失败 | "base64+zlib 解码失败 (sheet: xxx)" |
| 其他关键异常 | 按错误类型自动生成 |

### 去重

提交前用 GitHub Search API 检查是否已有同名 open issue，避免重复提交。

### 文件

- `scripts/report_issue.py` — 独立可用的 issue 自动反馈脚本
- `scripts/test_wecom_doc_reader.py` — 完备测试套件（7 大维度）

---

