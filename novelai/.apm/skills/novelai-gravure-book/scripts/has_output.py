#!/usr/bin/env python3
"""Exit 0 if the output image for a request already exists, 1 otherwise.

Usage: python has_output.py --request <x.request.json> --out-dir <project>/images

Looks for <out-dir>/<output.character>/<output.basename>-seed<seed>[-N].png (superseded/ is not
searched). Used by the batch loops so an image that was already generated is never generated again
(the runner would otherwise write a second copy with a -2 suffix).
"""
import argparse
import json
import re
import sys
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--request", required=True)
    ap.add_argument("--out-dir", required=True)
    a = ap.parse_args()
    out = json.loads(Path(a.request).read_text(encoding="utf-8"))["output"]
    folder = Path(a.out_dir) / out.get("character", "")
    pat = re.compile(re.escape(out["basename"]) + r"-seed\d+(?:-\d+)?\.png")
    hit = folder.is_dir() and any(pat.fullmatch(p.name) for p in folder.iterdir())
    if hit:
        print(f"exists: {out['basename']}", file=sys.stderr)
    return 0 if hit else 1


if __name__ == "__main__":
    sys.exit(main())
