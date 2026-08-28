#!/usr/bin/env python3
"""企微扫码授权二维码 → 企微客户端可用的 JPEG。

坑（两个都要避开）：
1. wecom_auth_flow.py 拦截到的 QR 是 1-bit grayscale PNG，企微客户端渲染成裂图。
2. 企微聊天里二维码 URL/链接打不开；只有图片能长按识别。

用法:
    python3 qr_to_wecom.py <qr.png> [out.jpg]
输出 1160×1160 带白边 RGB JPEG，打印输出路径（供 MEDIA: 直发）。
"""
import sys
from pathlib import Path

from PIL import Image

CANVAS = 1160  # 8-27 实测：1160×1160 带白边，企微长按识别一次成功
PAD = 80


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        return 2
    src = Path(sys.argv[1])
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else src.with_suffix(".wecom.jpg")

    qr = Image.open(src).convert("RGB")
    inner = CANVAS - 2 * PAD
    qr = qr.resize((inner, inner), Image.Resampling.NEAREST)
    canvas = Image.new("RGB", (CANVAS, CANVAS), "white")
    canvas.paste(qr, (PAD, PAD))
    canvas.save(out, "JPEG", quality=95)
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
