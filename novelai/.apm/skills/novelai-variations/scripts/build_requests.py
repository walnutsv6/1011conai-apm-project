#!/usr/bin/env python3
"""Build novelai-imagegen request JSON files for an outfit x pose matrix.

Usage:
  python build_requests.py --spec spec.json --out-dir requests [--only bay] [--rating sensitive] [--suffix v2]

Writes one request JSON per image, manifest.json, and prompts.md into --out-dir.
Never overwrites an existing request file.
"""
import argparse
import json
import re
import sys
from pathlib import Path

TRANSPARENT_BG = "transparent background, simple background, no background"
TRANSPARENT_NEG = "scenery, background, outdoors"


def join(*parts):
    return ", ".join(p.strip(" ,") for p in parts if p and p.strip(" ,"))


def remove_tags(csv, tags):
    drop = {t.strip() for t in tags}
    return ", ".join(t.strip() for t in csv.split(",") if t.strip() and t.strip() not in drop)


def find_override(char, outfit, pose, mode):
    merged = {}
    for ov in char.get("overrides", []):
        m = ov.get("match", {})
        if all(m.get(k) in (None, v) for k, v in
               (("outfit", outfit), ("pose", pose), ("mode", mode))):
            for k, v in ov.items():
                if k == "match":
                    continue
                if k.startswith("append_") and k in merged:
                    merged[k] = join(merged[k], v)
                else:
                    merged[k] = v
    return merged


def build(spec, cname, char, outfit, pose, mode, rating, suffix):
    d = spec["defaults"]
    outfit_def = spec["outfits"][outfit]
    pose_def = spec["poses"][pose]
    ov = find_override(char, outfit, pose, mode)

    background = TRANSPARENT_BG if mode == "transparent" else char["scene"]
    appearance = join(char["appearance"], ov.get("append_appearance", ""))
    pose_expr = ov.get("replace_pose_expression", pose_def.get("expression", ""))
    outfit_tags = join(ov.get("replace_outfit", char["outfits"][outfit]), ov.get("append_outfit", ""))
    body = join(char.get("body", ""), ov.get("append_body", ""))

    prompt = join(
        background, d["base_tags"], appearance, char.get("expression", ""),
        outfit_tags, ov.get("replace_composition", d["composition"]), pose_def["tags"], pose_expr, d["gaze"],
        body, d["style"], f"rating:{rating}",
    )

    outfit_neg = remove_tags(outfit_def.get("negative", ""), pose_def.get("negative_remove", []))
    negative = join(
        char.get("negative", ""), ov.get("append_negative", ""), outfit_neg,
        TRANSPARENT_NEG if mode == "transparent" else "", d["common_negative"],
    )

    note = re.sub(r"[^A-Za-z0-9_-]+", "-", ov["note"]).strip("-") if ov.get("note") else None
    parts = [cname, outfit, pose, mode] + ([note] if note else []) + ([suffix] if suffix else [])
    basename = "-".join(parts)

    req = {
        "schema_version": 1,
        "operation": "generate",
        "prompt": prompt,
        "negative_prompt": negative,
        "model": d["model"],
        "orientation": d["orientation"],
        "seed": ov.get("seed", char["seed"]),
        "steps": d["steps"],
        "scale": d["scale"],
        "samples": 1,
        "cost_policy": {
            "subscription_plan": "auto",
            "prefer_zero_anlas": True,
            "require_zero_anlas": d.get("require_zero_anlas", True),
            "confirm_above_anlas": 100,
            "confirmed_paid": False,
        },
        "output": {"basename": basename, "format": "png"},
    }
    if mode == "transparent":
        req["straight_alpha"] = True
        req["tag_hint_transparent_background"] = True
    return basename, req


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--only", help="comma-separated character names")
    ap.add_argument("--outfit", help="comma-separated outfit ids")
    ap.add_argument("--rating", help="override defaults.rating")
    ap.add_argument("--suffix", default="", help="revision suffix, e.g. v2")
    args = ap.parse_args()

    spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    rating = args.rating or spec["defaults"].get("rating", "sensitive")
    modes = spec["defaults"].get("modes", ["bg", "transparent"])
    only = set(args.only.split(",")) if args.only else None
    only_outfit = set(args.outfit.split(",")) if args.outfit else None

    manifest, md = [], []
    skipped = 0
    for cname, char in spec["characters"].items():
        if only and cname not in only:
            continue
        if "bangs" not in char["appearance"]:
            print(f"warning: {cname}: appearance has no bangs tag (e.g. 'side swept bangs'); fringe may vary between images", file=sys.stderr)
        md += [f"## {cname} (seed `{char['seed']}`)", ""]
        for outfit, poses in char["pairs"].items():
            if only_outfit and outfit not in only_outfit:
                continue
            for pose in poses:
                for mode in modes:
                    base, req = build(spec, cname, char, outfit, pose, mode, rating, args.suffix)
                    path = out / f"{base}.request.json"
                    if path.exists():
                        skipped += 1
                    else:
                        path.write_text(json.dumps(req, ensure_ascii=False, indent=2), encoding="utf-8")
                    manifest.append({"character": cname, "outfit": outfit, "pose": pose,
                                     "mode": mode, "request": path.name, "seed": char["seed"]})
                    md += [f"### {base}", "", "```", req["prompt"], "```", "",
                           f"negative: `{req['negative_prompt']}`", ""]

    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "prompts.md").write_text("# Prompts\n\n" + "\n".join(md), encoding="utf-8")
    print(json.dumps({"requests": len(manifest), "skipped_existing": skipped, "out_dir": str(out)}))


if __name__ == "__main__":
    sys.exit(main())
