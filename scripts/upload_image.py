#!/usr/bin/env python3
"""
企微文档图片/文件上传工具 — 直调 MCP JSON-RPC（绕过 Hermes 客户端 8KB 限制）

用法:
  python3 upload_image.py <image_path> <docid> [--title "标题"]
  python3 upload_image.py <file_path> <docid> --file [--file-name "name"]

返回 JSON:
  成功: {"ok": true, "url": "https://wdcdn.qpic.cn/...", "width": 1920, "height": 1080, "size": 36124}
  失败: {"ok": false, "error": "..."}

特性:
  - 无 base64 大小限制（直调 MCP server HTTP 接口，绕过 Hermes 客户端 8KB 限制）
  - 120 秒超时
  - 图片质量几乎无损（99.3%）
  - 自动从 ~/.hermes/config.yaml 读取 MCP URL + apikey

关键发现（2026-07-16 实测）:
  - Hermes MCP upload_doc_image 工具有 ~8KB base64 限制（客户端层）
  - 直调 MCP JSON-RPC HTTP 接口无此限制（server 端）
  - 35.3KB 图片上传成功，CDN 返回 1920x1080 原始尺寸，质量保持率 99.3%
  - 必须传 docid 参数（不传报 errcode 301085）
  - 必须加 Accept: application/json header（否则报 Not Acceptable）
"""
import sys, os, base64, json, argparse, requests

def get_mcp_url():
    """从 hermes config 读取 MCP URL + apikey"""
    config_path = os.path.expanduser("~/.hermes/config.yaml")
    try:
        import yaml
        with open(config_path) as f:
            cfg = yaml.safe_load(f)
        for name, server in (cfg.get("mcp_servers") or {}).items():
            url = server.get("url", "")
            if "robot-doc" in url:
                return url
    except Exception:
        pass
    return os.environ.get("WECOM_MCP_URL", "")

def upload_image(image_path, docid, title=None):
    """上传图片，返回 CDN URL"""
    mcp_url = get_mcp_url()
    if not mcp_url:
        return {"ok": False, "error": "未找到 MCP URL，请检查 config.yaml 或设置 WECOM_MCP_URL 环境变量"}

    if not os.path.exists(image_path):
        return {"ok": False, "error": f"文件不存在: {image_path}"}

    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()

    orig_size = os.path.getsize(image_path)

    payload = {
        "jsonrpc": "2.0", "method": "tools/call",
        "params": {"name": "upload_doc_image", "arguments": {"base64_content": b64, "docid": docid}},
        "id": 1
    }

    try:
        resp = requests.post(mcp_url, json=payload,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            timeout=120)
        data = resp.json()
        if "error" in data:
            return {"ok": False, "error": f"MCP error: {data['error']}"}
        inner = json.loads(data["result"]["content"][0]["text"])
        ec = inner.get("errcode", -1)
        if ec != 0:
            return {"ok": False, "error": f"errcode {ec}: {inner.get('errmsg')}"}
        return {
            "ok": True,
            "url": inner.get("url"),
            "width": inner.get("width"),
            "height": inner.get("height"),
            "size": inner.get("size"),
            "original_size": orig_size,
            "quality_ratio": round(inner.get("size", 0) / orig_size * 100, 1) if orig_size > 0 else 0,
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}

def upload_file(file_path, docid=None, file_name=None):
    """上传文件（非图片），返回 file_id（用于 smartsheet ATTACHMENT 字段）"""
    mcp_url = get_mcp_url()
    if not mcp_url:
        return {"ok": False, "error": "未找到 MCP URL"}

    with open(file_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()

    fname = file_name or os.path.basename(file_path)

    payload = {
        "jsonrpc": "2.0", "method": "tools/call",
        "params": {"name": "upload_doc_file", "arguments": {"file_name": fname, "file_base64_content": b64}},
        "id": 1
    }

    try:
        resp = requests.post(mcp_url, json=payload,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            timeout=120)
        data = resp.json()
        if "error" in data:
            return {"ok": False, "error": f"MCP error: {data['error']}"}
        inner = json.loads(data["result"]["content"][0]["text"])
        ec = inner.get("errcode", -1)
        if ec != 0:
            return {"ok": False, "error": f"errcode {ec}: {inner.get('errmsg')}"}
        return {"ok": True, "fileid": inner.get("fileid")}
    except Exception as e:
        return {"ok": False, "error": str(e)}

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="企微文档图片/文件上传工具（直调 MCP JSON-RPC）")
    parser.add_argument("image_path", help="图片或文件路径")
    parser.add_argument("docid", help="关联的文档 docid")
    parser.add_argument("--title", help="图片标题（可选）")
    parser.add_argument("--file", action="store_true", help="上传文件而非图片")
    parser.add_argument("--file-name", help="文件名（可选）")
    args = parser.parse_args()

    if args.file:
        result = upload_file(args.image_path, args.docid, args.file_name)
    else:
        result = upload_image(args.image_path, args.docid, args.title)

    print(json.dumps(result, ensure_ascii=False, indent=2))
