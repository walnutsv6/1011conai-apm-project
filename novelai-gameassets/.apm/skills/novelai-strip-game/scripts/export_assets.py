#!/usr/bin/env python3
"""Export a strip-game project as engine-independent PNG + JSON, capped at an age class.

Usage:
  python export_assets.py --project-dir output/novelai-imagegen/<project> --method seed|inpaint|mixed
         [--max-age all|12rec|15rec|15|18] [--mode transparent] [--out <dir>]

Copies the latest image of every cell at or below --max-age into <out>/<character>/ and writes
<out>/assets.json (stages in order with sprites per expression, special poses, transition frames
with durations, one-shots, events from the preset, cap_stage, missing cells). The inpaint method
exports the cutout (transparent) images; mixed takes each cell kind from cells.json method_by_kind. Stages above the cap are left out, and so is every
transition whose destination stage is left out. The age class is a self-imposed production
category, not an official rating: the person publishing the game makes the final check.
The icon one-shot is cropped from its source sprite here (it is not generated).
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

import numpy as np
from PIL import Image

from common import cell_image, latest

AGE_ORDER = ["all", "12rec", "15rec", "15", "18"]
NOTE = ("age_class は制作上の自主規制区分であり、審査機関による正式なレーティングではない。"
        "公開・配布前の確認は公開責任者（人間）が行う。")


def icon_from(src, dst, size=256):
    img = Image.open(src).convert("RGBA")
    a = np.asarray(img)[:, :, 3]
    if a.min() == 255:  # no alpha: use the whole width
        top, cx = 0, img.width / 2
    else:
        rows = np.where((a > 16).mean(axis=1) > 0.004)[0]
        top = rows[0] if len(rows) else 0
        band = a[top:top + int(img.height * 0.15)] > 16
        cols = np.where(band.any(axis=0))[0]
        cx = cols.mean() if len(cols) else img.width / 2
    side = int(img.width * 0.46)
    left = int(min(max(0, cx - side / 2), img.width - side))
    top = int(max(0, top - side * 0.04))
    img.crop((left, top, left + side, top + side)).resize((size, size), Image.LANCZOS).save(dst)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-dir", required=True)
    ap.add_argument("--method", required=True, choices=["seed", "inpaint", "mixed"])
    ap.add_argument("--max-age", default="18", choices=AGE_ORDER)
    ap.add_argument("--mode", default="transparent", help="seed method sprite mode (inpaint is always cutout)")
    ap.add_argument("--out")
    a = ap.parse_args()
    project = Path(a.project_dir)
    data = json.loads((project / "cells.json").read_text(encoding="utf-8"))
    cap = AGE_ORDER.index(a.max_age)
    mix = data.get("method_by_kind")
    if a.method == "mixed" and not mix:
        sys.exit("error: cells.json has no method_by_kind (build the spec with methods: [\"mixed\"])")
    real = lambda c: mix[c["kind"]] if a.method == "mixed" else a.method  # noqa: E731
    out = Path(a.out or project / "export" / f"{a.method}-{a.max_age}")
    out.mkdir(parents=True, exist_ok=True)
    ok = lambda age: AGE_ORDER.index(age) <= cap  # noqa: E731
    kept = [s for s in data["stages"] if ok(s["age_class"])]
    kept_main = [s["id"] for s in kept if s["role"] == "main"]
    if not kept_main:
        sys.exit("error: no main stage is at or below --max-age")
    chars = sorted({c["character"] for c in data["cells"]})
    result = {"schema": "strip-game-assets/1", "project": data["project"], "game": data["game"],
              "method": a.method, "max_age": a.max_age, "age_labels": data["age_labels"], "rating_note": NOTE,
              "expressions": data["expressions"], "transition_expression": data["transition_expression"],
              "special_poses": data["special_poses"], "events": data["events"], "characters": {}}

    def copy(cell, cdir):
        src = cell_image(cell)
        if src and cell["method"] == "inpaint" and "cutout" not in src.parts:
            src = None  # inpaint exports cut-outs only (plates have a grey background)
        if not src:
            return None
        dst = cdir / src.name
        shutil.copy2(src, dst)
        return f"{cdir.name}/{dst.name}"

    for ch in chars:
        cdir = out / ch
        cdir.mkdir(exist_ok=True)
        cells = [c for c in data["cells"] if c["character"] == ch and c["method"] in (a.method, "seed")
                 or c["character"] == ch and a.method == "mixed"]
        mine = [c for c in cells if c["method"] == real(c)]
        missing, stages, transitions = [], [], []
        mode_ok = lambda c: c["method"] == "inpaint" or c["kind"] == "special" or c["mode"] == a.mode  # noqa: E731
        order = [s["id"] for s in data["stages"]]
        for s in kept:
            if s["role"] != "main":
                continue
            entry = {k: s[k] for k in ("id", "label", "class", "age_class", "facing")}
            entry["sprites"], entry["special"] = {}, {}
            for c in mine:
                if c["stage"] != s["id"] or not mode_ok(c) or c["kind"] not in ("sprite", "special"):
                    continue
                f = copy(c, cdir)
                if not f:
                    missing.append(c["basename"])
                    continue
                key = c["expression"] if c["kind"] == "sprite" else c["pose"]
                bucket = entry["sprites"] if c["kind"] == "sprite" else entry["special"]
                if c["variant"]:
                    bucket.setdefault(key, {})[c["variant"]] = f
                else:
                    bucket[key] = f
            entry["fallback_expression"] = "normal"
            stages.append(entry)
        for i in range(len(kept_main) - 1):
            lo, hi = order.index(kept_main[i]), order.index(kept_main[i + 1])
            frames = []
            for sid in order[lo + 1:hi]:
                st = next(x for x in data["stages"] if x["id"] == sid)
                if not ok(st["age_class"]):
                    continue
                for c in mine:
                    if c["stage"] == sid and c["kind"] == "transition" and mode_ok(c):
                        f = copy(c, cdir)
                        if f:
                            frames.append({"stage": sid, "label": st["label"], "file": f, "variant": c["variant"],
                                           "duration_ms": st.get("duration_ms", 450)})
                        else:
                            missing.append(c["basename"])
            transitions.append({"from": kept_main[i], "to": kept_main[i + 1], "frames": frames})
        oneshots = {}
        for os_ in data.get("oneshots", []):
            if os_["kind"] == "icon":
                fr = os_.get("from", {"stage": "dressed", "expression": "normal"})
                src_cell = next((c for c in mine if c["kind"] == "sprite" and c["stage"] == fr["stage"]
                                 and c["expression"] == fr["expression"] and mode_ok(c)), None)
                src = cell_image(src_cell) if src_cell else None
                if src:
                    icon_from(src, cdir / f"{ch}-icon.png")
                    oneshots["icon"] = f"{ch}/{ch}-icon.png"
                continue
            for c in cells:
                if c.get("oneshot") == os_["id"] and ok(c["age_class"]):  # one-shots: seed method, bg mode
                    src = latest(Path(c["image"]).parent, c["basename"])
                    f = None
                    if src:
                        shutil.copy2(src, cdir / src.name)
                        f = f"{ch}/{src.name}"
                    if not f:
                        missing.append(c["basename"])
                    elif c["variant"]:
                        oneshots.setdefault(os_["id"], {})[c["variant"]] = f
                    else:
                        oneshots[os_["id"]] = f
        result["characters"][ch] = {"stages": stages, "transitions": transitions, "cap_stage": kept_main[-1],
                                    "oneshots": oneshots, "missing": missing}
    (out / "assets.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"out": str(out), "max_age": a.max_age,
                      "stages": kept_main, "missing": {k: len(v["missing"]) for k, v in result["characters"].items()}},
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
