# /// script
# requires-python = ">=3.10,<3.14"
# dependencies = ["rembg==2.0.67", "onnxruntime==1.22.1", "pillow", "numpy"]
# ///
"""Cut out the background of inpaint-method plate images (NovelAI inpainting cannot output alpha).

Usage:
  uv run remove_bg.py --request <x.request.json> --images <project>/images        # one image (user-run scripts)
  uv run remove_bg.py --cells <project>/cells.json [--character meru]            # every agent-generated plate
  python remove_bg.py --method chroma ...                                          # no extra packages

Writes <images>/<character>/cutout/<basename>-seed<seed>.png (RGBA). Existing cutouts are kept
unless --force. --cells mode skips script-only (topless / bottomless / nude) cells: those are cut
out by the user's run script, never by the agent.

Methods:
  rembg   (default) local segmentation with the isnet-anime model; first run downloads the model.
  chroma  key out the plate's flat border colour with a soft edge; no model, weaker on hair edges.
"""
import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import latest  # noqa: E402


def chroma(img, tol=28, soft=22):
    a = np.asarray(img.convert("RGB")).astype(np.int16)
    border = np.concatenate([a[0], a[-1], a[:, 0], a[:, -1]])
    bg = np.median(border, axis=0)
    dist = np.abs(a - bg).sum(axis=2).astype(np.float32)
    alpha = np.clip((dist - tol) / soft, 0, 1)
    out = np.dstack([a.astype(np.uint8), (alpha * 255).astype(np.uint8)])
    return Image.fromarray(out, "RGBA")


_session = None


def rembg_cut(img):
    global _session
    from rembg import new_session, remove
    if _session is None:
        _session = new_session("isnet-anime")
    return remove(img.convert("RGB"), session=_session)


def find_png(folder, basename):
    pat = re.compile(re.escape(basename) + r"-seed\d+(?:-\d+)?\.png")
    hits = sorted(p for p in folder.glob("*.png") if pat.fullmatch(p.name)) if folder.is_dir() else []
    return hits[-1] if hits else None


def cut(src, method, force):
    dst = src.parent / "cutout" / src.name
    if dst.exists() and not force:
        return dst, False
    dst.parent.mkdir(parents=True, exist_ok=True)
    img = Image.open(src)
    (chroma(img) if method == "chroma" else rembg_cut(img)).save(dst)
    return dst, True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--request")
    ap.add_argument("--images")
    ap.add_argument("--cells")
    ap.add_argument("--character")
    ap.add_argument("--method", choices=["rembg", "chroma"], default="rembg")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    jobs = []
    if a.request:
        out = json.loads(Path(a.request).read_text(encoding="utf-8"))["output"]
        src = find_png(Path(a.images) / out.get("character", ""), out["basename"])
        if src is None:
            sys.exit(f"error: image for {out['basename']} not found")
        jobs.append(src)
    elif a.cells:
        cells = json.loads(Path(a.cells).read_text(encoding="utf-8"))["cells"]
        for c in cells:
            if c["method"] != "inpaint" or c["script_only"]:
                continue
            if a.character and c["character"] != a.character:
                continue
            src = latest(Path(c["image"]).parent, c["basename"])
            if src:
                jobs.append(src)
    else:
        sys.exit("error: give --request + --images, or --cells")
    done = []
    for src in jobs:
        dst, new = cut(src, a.method, a.force)
        done.append({"src": str(src), "cutout": str(dst), "new": new})
    print(json.dumps({"method": a.method, "processed": done}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
