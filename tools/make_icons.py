"""PWA 아이콘 생성기 (Pillow 사용 — 빌드 타임 전용, 런타임 의존성 아님).

실행:  python tools/make_icons.py server/static/icons
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw

try:  # Windows 콘솔에서도 한글 출력이 깨지지 않도록
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

BG = (15, 23, 42)      # slate-950
BLUE = (56, 189, 248)  # sky-400
ROSE = (251, 113, 133) # rose-400


def make(size: int, maskable: bool = False) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    if maskable:
        d.rectangle([0, 0, size, size], fill=BG)
        pad = size * 0.26
    else:
        d.rounded_rectangle([0, 0, size - 1, size - 1], radius=int(size * 0.18), fill=BG)
        pad = size * 0.17

    cx, cy = size / 2, size / 2
    r = size / 2 - pad
    ring = max(2, int(size * 0.045))
    # 시계 테두리 (= 기록/시간 모티프)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=BLUE, width=ring)
    # 눈금
    for deg in range(0, 360, 30):
        a = math.radians(deg)
        d.line([cx + math.cos(a) * r * 0.80, cy + math.sin(a) * r * 0.80,
                cx + math.cos(a) * r * 0.92, cy + math.sin(a) * r * 0.92],
               fill=BLUE, width=max(1, int(size * 0.022)))
    # 바늘
    w = max(2, int(size * 0.05))
    d.line([cx, cy, cx, cy - r * 0.55], fill=ROSE, width=w)
    d.line([cx, cy, cx + r * 0.42, cy + r * 0.10], fill=ROSE, width=w)
    d.ellipse([cx - w, cy - w, cx + w, cy + w], fill=ROSE)
    return img


def main(argv=None):
    out = Path((argv or sys.argv[1:] or ["server/static/icons"])[0])
    out.mkdir(parents=True, exist_ok=True)
    make(192).save(out / "icon-192.png")
    make(512).save(out / "icon-512.png")
    make(512, maskable=True).save(out / "icon-512-maskable.png")
    make(180).save(out / "apple-touch-icon-180.png")
    make(32).save(out / "favicon-32.png")
    print("아이콘 생성 완료 →", out)


if __name__ == "__main__":
    main()
