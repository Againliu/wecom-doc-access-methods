#!/usr/bin/env python3
"""
GitHub Issue 自动反馈脚本

当 wecom-doc-access-methods skill 遇到异常时，自动在 GitHub 仓库创建 issue。
设计原则：通用可配置（环境变量 > 配置文件 > 默认值），不硬编码内部地址。

用法（被 wecom_doc_reader.py 自动调用）：
    from report_issue import auto_report_issue
    auto_report_issue(
        title="dop-api 返回 retcode 538002",
        error_detail="...",
        context={"url": "...", "sheet_id": "...", "step": "fetch"},
    )

环境变量：
    GITHUB_REPO   — GitHub 仓库 (owner/repo)，默认 Againliu/wecom-doc-access-methods
    GITHUB_TOKEN  — GitHub API token（必须设置）
    ISSUE_AUTO    — 是否自动提交，默认 "1"（提交），设为 "0" 只打印不提交
"""

import os
import sys
import json
import subprocess
from datetime import datetime


def _get_env(key, default=""):
    return os.environ.get(key, default)


def _gh_available():
    """检查 gh CLI 是否可用且已登录"""
    try:
        r = subprocess.run(
            ["gh", "auth", "status"],
            capture_output=True, text=True, timeout=10,
            env={**os.environ, "PATH": os.environ.get("PATH", "")}
        )
        return r.returncode == 0
    except Exception:
        return False


def _create_issue_via_api(repo, token, title, body, labels):
    """通过 GitHub REST API 创建 issue"""
    import urllib.request
    import urllib.error

    url = f"https://api.github.com/repos/{repo}/issues"
    data = json.dumps({
        "title": title,
        "body": body,
        "labels": labels,
    }).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            return result.get("html_url", "")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"[report_issue] GitHub API error {e.code}: {body[:200]}", file=sys.stderr)
        return ""
    except Exception as e:
        print(f"[report_issue] GitHub API request failed: {e}", file=sys.stderr)
        return ""


def _create_issue_via_gh(repo, title, body, labels):
    """通过 gh CLI 创建 issue"""
    cmd = [
        "gh", "issue", "create",
        "--repo", repo,
        "--title", title,
        "--body", body,
    ]
    for label in labels:
        cmd.extend(["--label", label])

    try:
        r = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30,
            env={**os.environ, "PATH": os.environ.get("PATH", "")}
        )
        if r.returncode == 0:
            return r.stdout.strip()
        else:
            print(f"[report_issue] gh CLI error: {r.stderr[:200]}", file=sys.stderr)
            return ""
    except Exception as e:
        print(f"[report_issue] gh CLI failed: {e}", file=sys.stderr)
        return ""


def _check_duplicate(repo, token, title_prefix):
    """检查是否已有相似 issue（避免重复提交）"""
    import urllib.request
    import urllib.error

    url = f"https://api.github.com/search/issues?q=repo:{repo}+is:issue+is:open+{title_prefix[:50]}"

    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            return result.get("total_count", 0) > 0
    except Exception:
        return False


def auto_report_issue(title, error_detail="", context=None, labels=None):
    """
    自动在 GitHub 创建 issue 反馈问题。

    Args:
        title: issue 标题（简短描述问题）
        error_detail: 错误详情（堆栈跟踪、错误消息等）
        context: 上下文字典（url, sheet_id, step, user_id 等）
        labels: GitHub labels 列表，默认 ["bug", "auto-reported"]

    Returns:
        issue URL（成功）或空字符串（失败/跳过）
    """
    repo = _get_env("GITHUB_REPO", "Againliu/wecom-doc-access-methods")
    token = _get_env("GITHUB_TOKEN", "")
    auto = _get_env("ISSUE_AUTO", "1")

    if auto != "1":
        print(f"[report_issue] ISSUE_AUTO=0, skip: {title}", file=sys.stderr)
        return ""

    if not token:
        print("[report_issue] GITHUB_TOKEN not set, skip", file=sys.stderr)
        return ""

    if labels is None:
        labels = ["bug", "auto-reported"]

    # 去重检查
    if _check_duplicate(repo, token, title):
        print(f"[report_issue] 已有相似 open issue, skip: {title}", file=sys.stderr)
        return ""

    # 构建 issue body
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ctx_lines = ""
    if context:
        for k, v in context.items():
            val = str(v)
            if len(val) > 200:
                val = val[:200] + "..."
            ctx_lines += f"- **{k}**: {val}\n"

    body = f"""## 自动反馈 — {title}

**时间**: {ts}
**来源**: wecom-doc-access-methods skill 自动反馈

### 上下文
{ctx_lines}

### 错误详情
```
{error_detail[:3000]}
```

---
_此 issue 由 skill 自动创建。如需关闭，请添加 `wontfix` label。_
"""

    # 优先用 API，fallback 到 gh CLI
    issue_url = ""
    if token:
        issue_url = _create_issue_via_api(repo, token, title, body, labels)

    if not issue_url and _gh_available():
        issue_url = _create_issue_via_gh(repo, title, body, labels)

    if issue_url:
        print(f"[report_issue] Issue created: {issue_url}")
    else:
        print(f"[report_issue] Failed to create issue (title: {title})", file=sys.stderr)

    return issue_url


if __name__ == "__main__":
    # 命令行测试
    import argparse
    parser = argparse.ArgumentParser(description="GitHub Issue 自动反馈")
    parser.add_argument("--title", required=True, help="Issue 标题")
    parser.add_argument("--detail", default="", help="错误详情")
    parser.add_argument("--context", default="{}", help="上下文 JSON")
    args = parser.parse_args()

    ctx = json.loads(args.context) if args.context else {}
    url = auto_report_issue(args.title, args.detail, ctx)
    print(f"Result: {url or '(failed)'}")
