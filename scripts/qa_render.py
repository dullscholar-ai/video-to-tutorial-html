#!/usr/bin/env python3
"""Visual QA for single-file HTML tutorials via headless Chrome.

Covers the traps hit in practice:
  * --screenshot needs an ABSOLUTE Windows path; relative silently fails.
  * Chrome caps window height (~16384 px) -> tall pages get truncated.
    Workaround: render a temp copy with earlier sections display:none.
  * URL-fragment scrolling does not work in --screenshot mode.
  * Tiny PNG (<20 KB) == blank render.

Usage:
  python qa_render.py tutorial.html --out render/ [--w 1440 --seg 2400]
                                      [--hide c1,c2] [--chrome "C:\\...\\chrome.exe"]
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

CHROME_CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
]


def find_chrome(explicit: str | None) -> str:
    if explicit:
        return explicit
    for c in CHROME_CANDIDATES:
        if Path(c).exists():
            return c
    found = shutil.which("chrome") or shutil.which("msedge")
    if not found:
        sys.exit("[qa] no Chrome/Edge found; pass --chrome")
    return found


def chrome_screenshot(chrome: str, url: str, out_png: Path, w: int, h: int) -> None:
    out_png.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(
        [chrome, "--headless=new", "--disable-gpu", "--hide-scrollbars",
         "--force-device-scale-factor=1", f"--window-size={w},{h}",
         f"--screenshot={out_png}", url],
        capture_output=True, timeout=120,
    )
    if not out_png.exists():
        sys.exit(f"[qa] screenshot failed: {r.stderr.decode(errors='ignore')[-400:]}")


def content_bottom(png: Path, min_delta: int = 10) -> int:
    """Last row that differs from the trailing background row."""
    import numpy as np
    from PIL import Image

    a = np.asarray(Image.open(png).convert("L"))
    rows = np.where(np.abs(a.astype(int) - int(a[-1, 0])).max(axis=1) > min_delta)[0]
    return int(rows.max()) + 40 if len(rows) else a.shape[0]


def slice_png(png: Path, out_dir: Path, seg: int, bottom: int | None = None) -> list[Path]:
    from PIL import Image

    im = Image.open(png).convert("RGB")
    h = min(bottom or im.height, im.height)
    n = (h + seg - 1) // seg
    parts = []
    for i in range(n):
        p = out_dir / f"{png.stem}_s{i:02d}.png"
        im.crop((0, i * seg, im.width, min(h, (i + 1) * seg))).save(p)
        parts.append(p)
    return parts


def make_hidden_copy(html: Path, hide: list[str]) -> Path:
    """Inject <style> hiding the given ids so the tail fits the window cap."""
    text = html.read_text(encoding="utf-8")
    style = f"<style>{','.join(hide)}{{display:none!important}}</style></head>"
    tmp = html.with_name(f"_{html.stem}_tailonly.html")
    tmp.write_text(text.replace("</head>", style, 1), encoding="utf-8")
    return tmp


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("html", type=Path)
    ap.add_argument("--out", type=Path, default=Path("render"))
    ap.add_argument("--w", type=int, default=1440)
    ap.add_argument("--h", type=int, default=16000, help="window height (cap ~16384)")
    ap.add_argument("--seg", type=int, default=2400, help="slice height")
    ap.add_argument("--chrome", default=None)
    ap.add_argument("--hide", default="", help="comma-separated ids to hide for the tail shot")
    ap.add_argument("--tail-h", type=int, default=6000)
    args = ap.parse_args()

    chrome = find_chrome(args.chrome)
    html = args.html.resolve()
    url = html.as_uri()
    args.out.mkdir(parents=True, exist_ok=True)

    full = args.out / "full.png"
    chrome_screenshot(chrome, url, full, args.w, args.h)
    if full.stat().st_size < 20_000:
        print(f"[qa] WARN: {full.name} is only {full.stat().st_size} B — likely blank")

    bottom = content_bottom(full)
    truncated = bottom >= args.h - 200
    print(f"[qa] content bottom ≈ {bottom}px / window {args.h}px"
          + ("  (TRUNCATED — rerun with --hide)" if truncated else ""))

    parts = slice_png(full, args.out, args.seg, bottom)
    print(f"[qa] {len(parts)} slices -> {args.out}/")

    if args.hide and truncated:
        tmp = make_hidden_copy(html, [x.strip() for x in args.hide.split(",") if x.strip()])
        tail = args.out / "tail.png"
        chrome_screenshot(chrome, tmp.as_uri(), tail, args.w, args.tail_h)
        tb = content_bottom(tail)
        tparts = slice_png(tail, args.out, args.seg, tb)
        print(f"[qa] tail: {len(tparts)} slices (bottom {tb}px)")
        tmp.unlink(missing_ok=True)

    print("[qa] read the top / middle / tail slices before shipping.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
