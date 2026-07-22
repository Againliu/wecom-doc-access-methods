#!/usr/bin/env python3
"""
企微文档统一写工具 — MCP JSON-RPC 直调，一个入口覆盖 s3_/e3_/w3_/SmartPage

设计目标:
  - 任意 AI 工具（有无 MCP client 框架）都能用：纯 requests + json，无框架依赖
  - 简单数据结构自动包装：2D 数组 → CellData，标量 → 字段类型格式
  - SmartPage 带图四步法封装：local: 占位符自动上传替换为 CDN URL

凭据来源（按优先级）:
  1. 环境变量 WECOM_MCP_URL（完整 URL 含 apikey）
  2. 环境变量 WECOM_MCP_APIKEY（自动拼 URL）
  3. ~/.hermes/config.yaml 或 ~/.openclaw/config.yaml 的 mcp_servers（robot-doc）

用法示例:
  # s3_ 智能表格
  wecom_doc_writer.py s3 sheets --url <s3_url>
  wecom_doc_writer.py s3 fields --url <s3_url> --sheet-id <id>
  wecom_doc_writer.py s3 get --url <s3_url> --sheet-id <id> --limit 10
  wecom_doc_writer.py s3 add --url <s3_url> --sheet-id <id> --records '[{"标题":"x","进度":50}]'
  wecom_doc_writer.py s3 update --url <s3_url> --sheet-id <id> --records '[{"record_id":"r_x","进度":80}]'
  wecom_doc_writer.py s3 delete --url <s3_url> --sheet-id <id> --record-ids r_a,r_b

  # e3_ 电子表格（data 为 2D 数组，自动包装成 CellData）
  wecom_doc_writer.py e3 info --url <e3_url>
  wecom_doc_writer.py e3 update-range --url <e3_url> --sheet-id <id> --start-row 0 --start-col 0 --data '[["姓名","分数"],["张三",95]]'
  wecom_doc_writer.py e3 append --url <e3_url> --sheet-id <id> --row '["李四",88]'

  # w3_ 微文档
  wecom_doc_writer.py w3 create --name "标题" --content @doc.md
  wecom_doc_writer.py w3 edit --url <w3_url> --content @doc.md
  wecom_doc_writer.py w3 get --url <w3_url>

  # SmartPage（markdown 里用 ![](local:/path/img.png) 占位，自动上传到容器并替换 CDN URL）
  wecom_doc_writer.py smartpage create --title "标题" --pages '[{"page_title":"页1","content":"# 内容"}]'
  wecom_doc_writer.py smartpage create-with-images --title "标题" --markdown @page.md [--container-url <容器url>]
  wecom_doc_writer.py smartpage export --url <sp_url>

  # 图片/文件上传
  wecom_doc_writer.py upload-image --file img.png --doc-url <容器或文档url>
  wecom_doc_writer.py upload-file --file a.zip

所有命令输出 JSON: {"ok": true/false, ...}
"""
import sys, os, json, base64, time, argparse, re

try:
    import requests
except ImportError:
    print(json.dumps({"ok": False, "error": "缺少 requests: pip install requests"}))
    sys.exit(1)

MCP_BASE = "https://qyapi.weixin.qq.com/mcp/robot-doc"


# ---------- 凭据与 MCP 直调 ----------

def get_mcp_url():
    """按优先级获取 MCP URL"""
    url = os.environ.get("WECOM_MCP_URL", "")
    if url:
        return url
    key = os.environ.get("WECOM_MCP_APIKEY", "")
    if key:
        return f"{MCP_BASE}?apikey={key}"
    # fallback: 从 agent 配置文件读（可选，非 Hermes/OpenClaw 环境自动跳过）
    for cfg_path in ("~/.hermes/config.yaml", "~/.openclaw/config.yaml"):
        p = os.path.expanduser(cfg_path)
        if not os.path.exists(p):
            continue
        try:
            import yaml
            with open(p) as f:
                cfg = yaml.safe_load(f)
            for _name, server in (cfg.get("mcp_servers") or {}).items():
                u = (server or {}).get("url", "")
                if "robot-doc" in u:
                    return u
        except Exception:
            continue
    return ""


def mcp_call(tool, arguments, timeout=120):
    """统一 MCP JSON-RPC 调用，返回解析后的 inner dict"""
    url = get_mcp_url()
    if not url:
        return {"ok": False, "error": "未找到 MCP 凭据，请设置 WECOM_MCP_URL 或 WECOM_MCP_APIKEY 环境变量"}
    payload = {"jsonrpc": "2.0", "method": "tools/call",
               "params": {"name": tool, "arguments": arguments}, "id": 1}
    try:
        resp = requests.post(url, json=payload,
                             headers={"Content-Type": "application/json",
                                      "Accept": "application/json"},
                             timeout=timeout)
        data = resp.json()
        if "error" in data:
            return {"ok": False, "error": f"MCP error: {data['error']}"}
        inner = json.loads(data["result"]["content"][0]["text"])
        ec = inner.get("errcode", 0)
        if ec not in (0, None):
            return {"ok": False, "errcode": ec, "error": inner.get("errmsg", ""), "raw": inner}
        inner["ok"] = True
        return inner
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ---------- 数据结构自动包装 ----------

def _wrap_cell(v):
    """标量/结构化值 → e3_ CellData"""
    if isinstance(v, dict) and "data_type" in v:
        return v  # 已是 CellData，透传
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return {"data_type": "NUMBER", "cell_value": {"number": v}}
    return {"data_type": "TEXT", "cell_value": {"text": str(v)}}


def wrap_grid(data_2d):
    """2D 数组 → e3_ rows 结构"""
    return [{"values": [_wrap_cell(c) for c in row]} for row in data_2d]


def _wrap_field_value(v):
    """标量 → s3_ 字段值格式（文本数组/数字/布尔/选项）"""
    if isinstance(v, list) and v and isinstance(v[0], dict):
        return v  # 已是结构化格式，透传
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return v
    if isinstance(v, list):  # 字符串列表 → 多选选项
        return [{"text": str(x)} for x in v]
    return [{"type": "text", "text": str(v)}]


def wrap_record(rec):
    """简单 dict → s3_ AddRecord 格式；含 record_id 则拆出（update 用）"""
    rid = rec.pop("record_id", None)
    values = {k: _wrap_field_value(v) for k, v in rec.items()}
    return rid, values


# ---------- s3_ 智能表格 ----------

def s3_sheets(doc_url):
    return mcp_call("smartsheet_get_sheet", {"url": doc_url})


def s3_fields(doc_url, sheet_id):
    return mcp_call("smartsheet_get_fields", {"url": doc_url, "sheet_id": sheet_id})


def s3_get(doc_url, sheet_id, limit=100, cursor=None):
    args = {"url": doc_url, "sheet_id": sheet_id, "limit": limit}
    if cursor:
        args["cursor"] = cursor
    return mcp_call("smartsheet_get_records", args)


def s3_add(doc_url, sheet_id, records):
    wrapped = []
    for rec in records:
        rec = dict(rec)
        rid, values = wrap_record(rec)
        if rid:
            return {"ok": False, "error": "add 不允许带 record_id（那是 update 的参数）"}
        wrapped.append({"values": values})
    return mcp_call("smartsheet_add_records",
                    {"url": doc_url, "sheet_id": sheet_id, "records": wrapped})


def s3_update(doc_url, sheet_id, records):
    wrapped = []
    for rec in records:
        rec = dict(rec)
        rid, values = wrap_record(rec)
        if not rid:
            return {"ok": False, "error": "update 必须带 record_id（先用 s3 get 查询）"}
        wrapped.append({"record_id": rid, "values": values})
    return mcp_call("smartsheet_update_records",
                    {"url": doc_url, "sheet_id": sheet_id, "records": wrapped})


def s3_delete(doc_url, sheet_id, record_ids):
    return mcp_call("smartsheet_delete_records",
                    {"url": doc_url, "sheet_id": sheet_id, "record_ids": record_ids})


# ---------- e3_ 电子表格 ----------

def e3_info(doc_url):
    return mcp_call("sheet_get_info", {"url": doc_url})


def e3_update_range(doc_url, sheet_id, start_row, start_col, data_2d):
    grid = {"start_row": start_row, "start_column": start_col,
            "rows": wrap_grid(data_2d)}
    return mcp_call("sheet_update_range_data",
                    {"url": doc_url, "sheet_id": sheet_id, "grid_data": grid})


def e3_append(doc_url, sheet_id, row):
    return mcp_call("sheet_append_data",
                    {"url": doc_url, "sheet_id": sheet_id,
                     "row": {"values": [_wrap_cell(c) for c in row]}})


# ---------- w3_ 微文档 ----------

def w3_create(name, content, doc_type=3):
    return mcp_call("create_doc", {"doc_name": name, "doc_type": doc_type}) \
        if content is None else _w3_create_with_content(name, content, doc_type)


def _w3_create_with_content(name, content, doc_type):
    r = mcp_call("create_doc", {"doc_name": name, "doc_type": doc_type})
    if not r.get("ok"):
        return r
    docid = r.get("docid")
    url = r.get("url")
    e = mcp_call("edit_doc_content",
                 {"docid": docid, "content": content, "content_type": 1})
    if not e.get("ok"):
        return {"ok": False, "error": f"文档已创建({url})但写入内容失败: {e.get('error')}",
                "docid": docid, "url": url}
    return {"ok": True, "docid": docid, "url": url}


def w3_edit(doc_url, content):
    return mcp_call("edit_doc_content",
                    {"url": doc_url, "content": content, "content_type": 1})


def w3_get(doc_url, max_poll=20, interval=2):
    """异步轮询读取，返回 Markdown 正文"""
    r = mcp_call("get_doc_content", {"url": doc_url, "type": 2})
    if not r.get("ok"):
        return r
    if r.get("task_done") and r.get("content"):
        return r
    task_id = r.get("task_id")
    if not task_id:
        return r
    for _ in range(max_poll):
        time.sleep(interval)
        r = mcp_call("get_doc_content", {"task_id": task_id, "type": 2})
        if not r.get("ok"):
            return r
        if r.get("task_done"):
            return r
    return {"ok": False, "error": f"轮询 {max_poll} 次后仍未完成", "task_id": task_id}


# ---------- SmartPage ----------

def sp_create(title, pages):
    """pages: [{"page_title":..., "content": markdown}]，content_type 固定 1"""
    wrapped = [{"page_title": p["page_title"], "content_type": 1,
                "page_content": p["content"]} for p in pages]
    return mcp_call("smartpage_create", {"title": title, "pages": wrapped})


def sp_export(doc_url, max_poll=20, interval=2):
    r = mcp_call("smartpage_export_task", {"url": doc_url, "content_type": 1})
    if not r.get("ok"):
        return r
    if r.get("task_done") and r.get("content"):
        return r
    task_id = r.get("task_id")
    if not task_id:
        return r
    for _ in range(max_poll):
        time.sleep(interval)
        r = mcp_call("smartpage_get_export_result", {"task_id": task_id})
        if not r.get("ok"):
            return r
        if r.get("task_done"):
            return r
    return {"ok": False, "error": f"轮询 {max_poll} 次后仍未完成", "task_id": task_id}


def upload_image(image_path, doc_url=None, docid=None):
    """上传图片到指定文档（容器），返回 CDN URL。doc_url/docid 二选一，必须提供一个"""
    if not os.path.exists(image_path):
        return {"ok": False, "error": f"文件不存在: {image_path}"}
    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    args = {"base64_content": b64}
    if doc_url:
        args["url"] = doc_url
    elif docid:
        args["docid"] = docid
    else:
        return {"ok": False, "error": "必须提供 --doc-url 或 docid（否则报 errcode 301085）"}
    return mcp_call("upload_doc_image", args, timeout=180)


def upload_file(file_path, file_name=None):
    """上传文件（非图片），返回 fileid（用于 s3_ ATTACHMENT 字段）"""
    if not os.path.exists(file_path):
        return {"ok": False, "error": f"文件不存在: {file_path}"}
    with open(file_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    return mcp_call("upload_doc_file",
                    {"file_name": file_name or os.path.basename(file_path),
                     "file_base64_content": b64}, timeout=180)


LOCAL_IMG_RE = re.compile(r'!\[([^\]]*)\]\(local:([^)]+)\)')


def sp_create_with_images(title, markdown, container_url=None, page_title="正文"):
    """
    SmartPage 带图四步法封装：
      1. markdown 里的 ![](local:/abs/path.png) 占位符逐个提取
      2. 上传到容器 SmartPage（container_url；不提供则自动创建一个持久容器）
      3. 占位符替换为 CDN URL（英文括号语法）
      4. 一次性创建正式 SmartPage
    返回 {"ok":..., "url":..., "container_url":...} — container_url 建议保存复用
    """
    # Step 1: 确保容器存在
    if not container_url:
        c = sp_create("图片上传容器（勿删，供脚本复用）",
                      [{"page_title": "容器", "content": "upload container"}])
        if not c.get("ok"):
            return {"ok": False, "error": f"创建图片容器失败: {c.get('error')}"}
        container_url = c.get("url")
        if not container_url:
            return {"ok": False, "error": "创建图片容器未返回 url", "raw": c}

    # Step 2: 提取 local: 占位符并上传
    replaced = markdown
    uploaded = {}
    for alt, path in LOCAL_IMG_RE.findall(markdown):
        path = path.strip()
        up = upload_image(path, doc_url=container_url)
        if not up.get("ok"):
            return {"ok": False, "error": f"上传图片 {path} 失败: {up.get('error')}",
                    "container_url": container_url}
        cdn = up.get("url")
        uploaded[path] = cdn
        # 注意：必须用英文括号 ()，中文括号（）不渲染
        replaced = replaced.replace(f"![{alt}](local:{path})", f"![{alt}]({cdn})")

    # Step 3: 检查是否还有未替换的 local: 占位
    leftover = LOCAL_IMG_RE.findall(replaced)
    if leftover:
        return {"ok": False, "error": f"仍有 {len(leftover)} 个 local: 占位未替换",
                "uploaded": uploaded}

    # Step 4: 一次性创建正式 SmartPage
    r = sp_create(title, [{"page_title": page_title, "content": replaced}])
    if not r.get("ok"):
        return {"ok": False, "error": f"创建正式 SmartPage 失败: {r.get('error')}",
                "container_url": container_url, "uploaded": uploaded}
    return {"ok": True, "url": r.get("url"), "docid": r.get("docid"),
            "container_url": container_url, "uploaded": uploaded}


# ---------- CLI ----------

def _load_json_arg(s):
    """支持 inline JSON 或 @file"""
    if s.startswith("@"):
        with open(s[1:]) as f:
            return json.load(f)
    return json.loads(s)


def _load_text_arg(s):
    """支持 inline 文本或 @file"""
    if s.startswith("@"):
        with open(s[1:]) as f:
            return f.read()
    return s


def main():
    ap = argparse.ArgumentParser(description="企微文档统一写工具（MCP JSON-RPC 直调）")
    sub = ap.add_subparsers(dest="category", required=True)

    def add_url(p):
        p.add_argument("--url", required=True, help="文档访问链接")

    # s3
    p = sub.add_parser("s3", help="智能表格")
    s3sub = p.add_subparsers(dest="action", required=True)
    a = s3sub.add_parser("sheets"); add_url(a)
    a = s3sub.add_parser("fields"); add_url(a); a.add_argument("--sheet-id", required=True)
    a = s3sub.add_parser("get"); add_url(a); a.add_argument("--sheet-id", required=True)
    a.add_argument("--limit", type=int, default=100)
    a = s3sub.add_parser("add"); add_url(a); a.add_argument("--sheet-id", required=True)
    a.add_argument("--records", required=True, help="JSON 数组或 @file")
    a = s3sub.add_parser("update"); add_url(a); a.add_argument("--sheet-id", required=True)
    a.add_argument("--records", required=True, help="JSON 数组（每条含 record_id）或 @file")
    a = s3sub.add_parser("delete"); add_url(a); a.add_argument("--sheet-id", required=True)
    a.add_argument("--record-ids", required=True, help="逗号分隔")

    # e3
    p = sub.add_parser("e3", help="电子表格")
    e3sub = p.add_subparsers(dest="action", required=True)
    a = e3sub.add_parser("info"); add_url(a)
    a = e3sub.add_parser("update-range"); add_url(a)
    a.add_argument("--sheet-id", required=True)
    a.add_argument("--start-row", type=int, default=0)
    a.add_argument("--start-col", type=int, default=0)
    a.add_argument("--data", required=True, help="2D JSON 数组或 @file")
    a = e3sub.add_parser("append"); add_url(a); a.add_argument("--sheet-id", required=True)
    a.add_argument("--row", required=True, help="1D JSON 数组或 @file")

    # w3
    p = sub.add_parser("w3", help="微文档")
    w3sub = p.add_subparsers(dest="action", required=True)
    a = w3sub.add_parser("create"); a.add_argument("--name", required=True)
    a.add_argument("--content", help="Markdown 或 @file（可选，先建空文档）")
    a = w3sub.add_parser("edit"); add_url(a)
    a.add_argument("--content", required=True, help="Markdown 或 @file")
    a = w3sub.add_parser("get"); add_url(a)

    # smartpage
    p = sub.add_parser("smartpage", help="SmartPage 智能文档")
    spsub = p.add_subparsers(dest="action", required=True)
    a = spsub.add_parser("create"); a.add_argument("--title", required=True)
    a.add_argument("--pages", required=True, help="JSON 数组或 @file")
    a = spsub.add_parser("create-with-images"); a.add_argument("--title", required=True)
    a.add_argument("--markdown", required=True, help="Markdown 或 @file，图片用 ![](local:/path) 占位")
    a.add_argument("--container-url", help="图片容器 SmartPage URL（不提供则自动创建）")
    a.add_argument("--page-title", default="正文")
    a = spsub.add_parser("export"); add_url(a)

    # upload
    p = sub.add_parser("upload-image", help="上传图片")
    p.add_argument("--file", required=True)
    p.add_argument("--doc-url", required=True, help="容器/文档访问链接")
    p = sub.add_parser("upload-file", help="上传文件（非图片）")
    p.add_argument("--file", required=True)
    p.add_argument("--file-name")

    args = ap.parse_args()
    cat, act = args.category, getattr(args, "action", None)
    r = {"ok": False, "error": f"未处理的命令: {cat} {act or ''}"}

    if cat == "s3":
        if act == "sheets":
            r = s3_sheets(args.url)
        elif act == "fields":
            r = s3_fields(args.url, args.sheet_id)
        elif act == "get":
            r = s3_get(args.url, args.sheet_id, args.limit)
        elif act == "add":
            r = s3_add(args.url, args.sheet_id, _load_json_arg(args.records))
        elif act == "update":
            r = s3_update(args.url, args.sheet_id, _load_json_arg(args.records))
        elif act == "delete":
            r = s3_delete(args.url, args.sheet_id, args.record_ids.split(","))
    elif cat == "e3":
        if act == "info":
            r = e3_info(args.url)
        elif act == "update-range":
            r = e3_update_range(args.url, args.sheet_id,
                                args.start_row, args.start_col,
                                _load_json_arg(args.data))
        elif act == "append":
            r = e3_append(args.url, args.sheet_id, _load_json_arg(args.row))
    elif cat == "w3":
        if act == "create":
            content = _load_text_arg(args.content) if args.content else None
            r = w3_create(args.name, content)
        elif act == "edit":
            r = w3_edit(args.url, _load_text_arg(args.content))
        elif act == "get":
            r = w3_get(args.url)
    elif cat == "smartpage":
        if act == "create":
            r = sp_create(args.title, _load_json_arg(args.pages))
        elif act == "create-with-images":
            r = sp_create_with_images(args.title, _load_text_arg(args.markdown),
                                      container_url=args.container_url,
                                      page_title=args.page_title)
        elif act == "export":
            r = sp_export(args.url)
    elif cat == "upload-image":
        r = upload_image(args.file, doc_url=args.doc_url)
    elif cat == "upload-file":
        r = upload_file(args.file, args.file_name)
    else:
        r = {"ok": False, "error": f"未知命令: {cat} {act or ''}"}

    print(json.dumps(r, ensure_ascii=False, indent=2))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
