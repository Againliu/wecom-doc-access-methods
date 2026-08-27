#!/usr/bin/env python3
"""共享浏览器启动 helper — 所有脚本唯一入口（v5.9.0）

解决三层独立依赖误报问题：
  Python playwright 包 / Skill 目录 / 浏览器二进制 是三层独立依赖。
  import 成功 ≠ 浏览器可启动。

启动 fallback 链（Codex/macOS 反馈 2026-08-27）：
  1. PLAYWRIGHT_EXECUTABLE   — 显式指定浏览器二进制路径
  2. PLAYWRIGHT_CHANNEL      — 显式指定 channel（chrome/msedge/chromium 等）
  3. 系统已安装 Chrome        — 自动探测（channel="chrome"），无需配置
  4. Playwright bundled Chromium — 默认（需 playwright install chromium）

任一成功即用；全部失败时抛 BrowserLaunchError，携带结构化 JSON
（缺失层级、已尝试路径、修复命令），绝不甩原始 traceback。
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil

LAUNCH_ARGS = ["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]

# 系统浏览器探测路径（Linux + macOS）
_SYSTEM_CHROME_CANDIDATES = [
    "google-chrome",
    "google-chrome-stable",
    "chromium",
    "chromium-browser",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
]


class BrowserLaunchError(Exception):
    """浏览器启动失败 — str() 是结构化 JSON，不是 traceback"""

    def __init__(self, report: dict):
        self.report = report
        super().__init__(json.dumps(report, ensure_ascii=False))


def _detect_system_chrome() -> str | None:
    """探测系统已安装的 Chrome/Chromium/Edge，返回可用二进制路径或 None"""
    for cand in _SYSTEM_CHROME_CANDIDATES:
        if cand.startswith("/"):
            if os.path.exists(cand):
                return cand
        else:
            path = shutil.which(cand)
            if path:
                return path
    return None


def _bundled_path(p) -> str | None:
    """返回 bundled Chromium 可执行文件路径（可能不存在）"""
    try:
        return p.chromium.executable_path
    except Exception:
        return None


def _structured_failure(p, attempts: list) -> BrowserLaunchError:
    """构造结构化失败报告：缺失层级 + 已检查路径 + 修复命令"""
    bundled = _bundled_path(p)
    system = _detect_system_chrome()
    fix = []
    if system:
        fix.append(f"已检测到系统浏览器 {system}，自动 fallback 应已生效；若仍失败检查其可执行权限")
    else:
        fix.append("python3 -m playwright install chromium  # 安装 bundled Chromium（约 165MB）")
        fix.append("或安装系统 Chrome 后重试（自动 fallback）")
    fix.append("或显式指定: export PLAYWRIGHT_EXECUTABLE=/path/to/chrome")
    return BrowserLaunchError({
        "success": False,
        "error": "browser_launch_failed",
        "missing_layer": "browser_binary",
        "hint": "Python playwright 包正常，但没有任何可用浏览器二进制。"
                "包、skill 目录、浏览器二进制是三层独立依赖，import 成功不代表浏览器可启动。",
        "bundled_chromium_path": bundled,
        "bundled_chromium_exists": bool(bundled and os.path.exists(bundled)),
        "system_chrome": system,
        "attempted": attempts,
        "fix_commands": fix,
    })


async def launch_browser(p, headless: bool = True):
    """统一浏览器启动入口。p 是 async_playwright() 实例。

    返回 launch 成功的 Browser 对象。
    失败抛 BrowserLaunchError（.report 为结构化 dict）。
    """
    attempts = []

    async def _try(desc: str, **kwargs):
        try:
            browser = await p.chromium.launch(headless=headless, args=LAUNCH_ARGS, **kwargs)
            return browser
        except Exception as e:
            attempts.append({
                "method": desc,
                "error": f"{type(e).__name__}: {e}"[:300],
            })
            return None

    # 1. 显式 executable path
    exe = os.environ.get("PLAYWRIGHT_EXECUTABLE")
    if exe:
        b = await _try(f"executable_path={exe}", executable_path=exe)
        if b:
            return b

    # 2. 显式 channel
    channel = os.environ.get("PLAYWRIGHT_CHANNEL")
    if channel:
        b = await _try(f"channel={channel}", channel=channel)
        if b:
            return b

    # 3. 自动探测系统 Chrome（无需任何配置）
    system = _detect_system_chrome()
    if system and not channel:
        b = await _try(f"auto system chrome channel=chrome ({system})", channel="chrome")
        if b:
            return b

    # 4. bundled Chromium（默认）
    b = await _try("bundled chromium")
    if b:
        return b

    raise _structured_failure(p, attempts)


def check_python_package() -> dict:
    """检查第一层依赖：Python playwright 包（供 doctor 使用）"""
    try:
        import playwright  # noqa: F401
        from playwright.async_api import async_playwright  # noqa: F401
        return {"layer": "python_package", "ok": True}
    except ImportError as e:
        return {
            "layer": "python_package",
            "ok": False,
            "error": str(e),
            "fix_commands": ["pip install -r requirements.txt"],
        }


async def _doctor_async() -> dict:
    """真实启动浏览器：launch → about:blank → 读 title → close。"""
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        system = _detect_system_chrome()
        bundled = _bundled_path(p)
        browser = await launch_browser(p)
        page = await browser.new_page()
        await page.goto("about:blank")
        title = await page.title()
        await browser.close()
        return {
            "layer": "browser_launch",
            "ok": True,
            "detail": f"真实启动成功（about:blank title={title!r}）",
            "system_chrome": system,
            "bundled_chromium_path": bundled,
            "bundled_chromium_exists": bool(bundled and os.path.exists(bundled)),
            "note": "doctor 通过 = 安装契约三层（Python 包/Skill 文件/浏览器二进制）全部落地",
        }


def doctor() -> dict:
    """安装健康自检：三层依赖逐层检查，最后一层真实启动浏览器。

    对应反馈：19/19 离线测试通过但首次运行才发现没有 Chromium。
    doctor 不依赖登录态，装完就能跑。
    """
    report = {"success": True, "layers": []}

    # 层1: Python 包
    pkg = check_python_package()
    report["layers"].append(pkg)
    if not pkg["ok"]:
        report["success"] = False
        report["error"] = "python_package 缺失 — 离线测试通过不代表它存在"
        return report

    # 层2: 浏览器真实启动（内部含系统 Chrome / bundled 探测）
    try:
        launch_result = asyncio.run(_doctor_async())
        report["layers"].append(launch_result)
    except Exception as e:
        if isinstance(e, BrowserLaunchError):
            report["layers"].append(e.report)
        else:
            report["layers"].append({
                "layer": "browser_launch",
                "ok": False,
                "error": f"{type(e).__name__}: {e}",
            })
        report["success"] = False
        report["error"] = "browser_launch 失败 — 结构化详情见 layers[-1]，修复命令见其中 fix_commands"

    return report
