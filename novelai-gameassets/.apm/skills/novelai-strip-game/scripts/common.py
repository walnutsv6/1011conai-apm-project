"""Shared helpers for the novelai-strip-game scripts."""
import re
from pathlib import Path


def latest(folder, basename):
    """Newest image of a cell: <basename>[-vN]-seed<seed>[-K].png in folder (highest vN, then K)."""
    folder = Path(folder)
    if not folder.is_dir():
        return None
    pat = re.compile(re.escape(basename) + r"(?:-v(?P<v>\d+))?-seed\d+(?:-(?P<k>\d+))?\.png")
    best = None
    for p in folder.glob("*.png"):
        m = pat.fullmatch(p.name)
        if m:
            key = (int(m.group("v") or 1), int(m.group("k") or 1))
            if best is None or key > best[0]:
                best = (key, p)
    return best[1] if best else None


def cell_image(cell):
    """Best image for a cells.json entry: the inpaint cut-out if any, else the generated image."""
    img = Path(cell["image"])
    if cell.get("cutout"):
        cut = latest(Path(cell["cutout"]).parent, cell["basename"])
        if cut:
            return cut
    return latest(img.parent, cell["basename"])
