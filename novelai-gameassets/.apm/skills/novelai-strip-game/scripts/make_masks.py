#!/usr/bin/env python3
"""Make inpaint masks for the inpaint method from the character's base plate image.

Usage:
  python make_masks.py --project-dir output/novelai-imagegen/<project> --character meru [--group dressed]

Reads <project>/cells.json. Masks are grouped by base plate: a group is named after the stage whose
plate starts an inpaint chain (the first main stage, and every stage whose facing changes). For each
group whose base plate exists it writes <project>/masks/<character>/<group>/<region>[+<region>...].png
(run it again after a new base plate is generated): white = repaint,
black = keep, same size as the base. Regions are boxes relative to the figure's bounding box,
found by comparing every pixel with the plate's grey border. Override or add regions with
defaults.mask_regions in the spec: {"name": [y0, y1, x0, x1]} (fractions of the bbox; x may go
below 0 / above 1 for a margin). "face" is special: it is centred on the head columns.
Also writes _overlay-<name>.png (mask in red over the base) so the masks can be checked by eye.
Masks are rough on purpose; replace any file with a hand-painted one of the same name if needed.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

from common import latest

REGIONS = {  # calibrated on a cowboy-shot portrait plate (head ~0-25% of the bbox, wrists ~78%)
    "face": [0.09, 0.25, None, None],      # brows to chin; hair top and ahoge stay
    "upper": [0.27, 0.80, -0.06, 1.06],    # below the chin to the wrists (sleeves)
    "chest": [0.30, 0.55, -0.04, 1.04],
    "lower": [0.50, 1.00, -0.06, 1.06],    # waist down
    "torso": [0.27, 1.00, -0.06, 1.06],
}
FACE_HALF_WIDTH = 0.12  # of image width


def figure_bbox(img):
    a = np.asarray(img.convert("RGB")).astype(np.int16)
    border = np.concatenate([a[0], a[-1], a[:, 0], a[:, -1]])
    bg = np.median(border, axis=0)
    fg = np.abs(a - bg).sum(axis=2) > 36
    rows = np.where(fg.mean(axis=1) > 0.004)[0]
    cols = np.where(fg.mean(axis=0) > 0.004)[0]
    if not len(rows) or not len(cols):
        sys.exit("error: no figure found on the plate (is the background a flat colour?)")
    return fg, (cols[0], rows[0], cols[-1] + 1, rows[-1] + 1)


def region_box(name, fg, bbox, size, regions):
    w, h = size
    x0, y0, x1, y1 = bbox
    bw, bh = x1 - x0, y1 - y0
    ry0, ry1, rx0, rx1 = regions[name]
    top, bottom = y0 + ry0 * bh, y0 + ry1 * bh
    if name == "face" and rx0 is None:
        band = fg[int(y0 + 0.09 * bh):int(y0 + 0.25 * bh)]
        cols = np.where(band.any(axis=0))[0]
        cx = cols.mean() if len(cols) else (x0 + x1) / 2
        left, right = cx - FACE_HALF_WIDTH * w, cx + FACE_HALF_WIDTH * w
    else:
        left, right = x0 + rx0 * bw, x0 + rx1 * bw
    return [int(max(0, left)), int(max(0, top)), int(min(w, right)), int(min(h, bottom))]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-dir", required=True)
    ap.add_argument("--character", required=True)
    ap.add_argument("--group", help="only this mask group (= id of the stage whose plate starts a chain)")
    a = ap.parse_args()
    project = Path(a.project_dir)
    cells = json.loads((project / "cells.json").read_text(encoding="utf-8"))
    regions = dict(REGIONS)
    spec_path = Path(cells.get("spec", ""))
    if spec_path.is_file():
        regions.update(json.loads(spec_path.read_text(encoding="utf-8"))["defaults"].get("mask_regions", {}))
    mine = [c for c in cells["cells"] if c["character"] == a.character and c["method"] == "inpaint"]
    needed = sorted({c["mask"] for c in mine if c.get("mask")})
    groups = sorted({m.split("/")[0] for m in needed})
    if a.group:
        groups = [g for g in groups if g == a.group]
    report = {}
    for group in groups:
        base_cell = next((c for c in mine if not c.get("parent") and c["stage"] == group), None)
        if base_cell is None:
            sys.exit(f"error: no base plate cell for mask group '{group}'")
        found = latest(Path(base_cell["image"]).parent, base_cell["basename"])
        base = str(found) if found else base_cell["image"]
        if not found:
            report[group] = {"base": base, "skipped": "base plate not generated yet"}
            continue
        img = Image.open(base).convert("RGB")
        fg, bbox = figure_bbox(img)
        out = project / "masks" / a.character / group
        out.mkdir(parents=True, exist_ok=True)
        rep = {"base": base, "bbox": [int(v) for v in bbox], "masks": {}}
        for name in needed:
            g, combo = name.split("/", 1)
            if g != group:
                continue
            parts = combo.split("+")
            unknown = [p for p in parts if p not in regions]
            if unknown:
                sys.exit(f"error: unknown mask region(s) {unknown}; define them in defaults.mask_regions")
            arr = np.zeros((img.height, img.width), dtype=np.uint8)
            boxes = []
            for p in parts:
                l, t, r, b = region_box(p, fg, bbox, img.size, regions)
                arr[t:b, l:r] = 255
                boxes.append([l, t, r, b])
            Image.fromarray(arr).save(out / f"{combo}.png")
            over = np.asarray(img).copy()
            sel = arr > 0
            over[sel] = (over[sel] * 0.5 + np.array([255, 0, 0]) * 0.5).astype(np.uint8)
            Image.fromarray(over).save(out / f"_overlay-{combo}.png")
            rep["masks"][combo] = boxes
        report[group] = rep
    print(json.dumps(report, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
