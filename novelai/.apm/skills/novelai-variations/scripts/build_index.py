#!/usr/bin/env python3
"""Build the project index page (one page, all characters, latest images only).

Usage:
  python build_index.py --project-dir output/novelai-imagegen/<project> [--title TITLE] [--lead TEXT] [--out index.html]

Reads <project-dir>/images/<character>/<character>-<outfit>-<pose>-<mode>[-note][-vN]-seed<seed>.png
(+ adjacent .json). Files under superseded/ are ignored; if several versions of the
same cell sit in the folder, the highest vN wins. Writes <project-dir>/index.html
(image paths relative to it). For old-vs-new comparison use build_compare.py.
"""
import argparse
import html
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

NAME = re.compile(
    r"^(?P<char>[^-]+)-(?P<outfit>[^-]+)-(?P<pose>[^-]+)-(?P<mode>bg|transparent)"
    r"(?P<note>(?:-(?!v\d+-|seed)[^-]+)*)(?:-v(?P<ver>\d+))?-seed(?P<seed>\d+)\.png$"
)
MODE_LABEL = {"bg": "背景あり", "transparent": "透過"}
PALETTE = ["#e0207f", "#1ea7c9", "#2e9e5b", "#d9822b", "#7a5af8", "#c9462c"]


def collect(images_dir, include_superseded=False):
    """-> {(char, outfit, pose, mode): [item sorted old->new]}"""
    groups = defaultdict(list)
    for png in sorted(Path(images_dir).rglob("*.png")):
        sup = "superseded" in png.parts
        if sup and not include_superseded:
            continue
        m = NAME.match(png.name)
        if not m:
            continue
        d = m.groupdict()
        meta = {}
        js = png.parent / "manifest" / f"{png.stem}.json"
        if not js.exists():  # legacy layout: sidecar next to the image
            js = png.with_suffix(".json")
        if js.exists():
            try:
                meta = json.loads(js.read_text(encoding="utf-8"))
            except Exception:
                pass
        groups[(d["char"], d["outfit"], d["pose"], d["mode"])].append({
            "path": png, "ver": int(d["ver"] or 1), "note": d["note"].strip("-"),
            "seed": d["seed"], "meta": meta, "superseded": sup,
        })
    for items in groups.values():
        items.sort(key=lambda x: (x["ver"], not x["superseded"]))
    return groups


def rel(path, base):
    return Path(path).resolve().relative_to(base).as_posix()


CSS = """
:root{--bg:#f6f4fa;--panel:#fff;--text:#1d1730;--muted:#6b6480;--line:#e3dfec;--accent:#e0207f}
@media (prefers-color-scheme:dark){:root{--bg:#120b22;--panel:#1c1433;--text:#f1eefb;--muted:#a59dbd;--line:#2e2550;--accent:#ff4fa3}}
*{box-sizing:border-box}html{scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:var(--text);font-family:system-ui,-apple-system,"Segoe UI","Hiragino Sans","Yu Gothic UI",sans-serif;line-height:1.5}
main{max-width:1400px;margin:0 auto;padding:32px 16px 48px}
h1{margin:0 0 4px;font-size:1.6rem}.lead{margin:0 0 12px;color:var(--muted);font-size:.92rem}
nav{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 16px}
nav a{display:inline-flex;align-items:center;gap:6px;padding:4px 12px;border-radius:999px;border:1px solid var(--line);background:var(--panel);color:var(--text);text-decoration:none;font-weight:600;font-size:.9rem}
nav a span{width:10px;height:10px;border-radius:50%}
section{margin:0 0 40px;scroll-margin-top:16px}
.char-head{display:flex;align-items:baseline;gap:12px;flex-wrap:wrap;padding:0 0 10px;margin:0 0 12px;border-bottom:4px solid var(--c)}
.char-head h2{margin:0;font-size:1.5rem}.char-head .meta{color:var(--muted);font-size:.85rem}
.wrap{overflow-x:auto;border:1px solid var(--line);border-radius:12px;background:var(--panel)}
table{border-collapse:collapse;width:100%;min-width:900px}
th,td{border-bottom:1px solid var(--line);padding:10px;vertical-align:top}
tr:last-child td,tr:last-child th{border-bottom:0}
tr.outfit-start>*{border-top:2px solid var(--line)}tr:first-child>*{border-top:0}
th.row{text-align:left;width:150px;font-weight:400}
.outfit{font-weight:700}.mode{display:inline-block;margin-top:2px;padding:0 8px;border-radius:999px;font-size:.72rem;font-weight:600;background:color-mix(in srgb,var(--muted) 16%,transparent);color:var(--muted)}
figure{margin:0;text-align:center}figure button{padding:0;border:0;background:none;cursor:zoom-in;display:block;width:100%}
figure img{width:100%;max-width:260px;aspect-ratio:832/1216;object-fit:cover;border-radius:8px;display:block;margin:0 auto}
.ver{font-size:.7rem;color:var(--muted)}
.checker{background-color:#fff;background-image:linear-gradient(45deg,#d4d4d8 25%,transparent 25%,transparent 75%,#d4d4d8 75%),linear-gradient(45deg,#d4d4d8 25%,transparent 25%,transparent 75%,#d4d4d8 75%);background-size:16px 16px;background-position:0 0,8px 8px}
footer{color:var(--muted);font-size:.8rem;border-top:1px solid var(--line);padding-top:16px}footer a{color:var(--accent)}
dialog{border:0;padding:0;background:transparent;max-width:96vw;max-height:96vh}dialog::backdrop{background:rgba(8,4,18,.85)}
dialog img{max-width:96vw;max-height:90vh;display:block;border-radius:8px}dialog p{color:#fff;text-align:center;margin:8px 0 0;font-size:.85rem}
"""
JS = """
const dlg=document.getElementById('dlg'),di=dlg.querySelector('img'),dc=dlg.querySelector('p');
document.addEventListener('click',e=>{const b=e.target.closest('figure button');
if(b){di.src=b.dataset.src;dc.textContent=b.dataset.cap;dlg.showModal()}else if(e.target===dlg){dlg.close()}});
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-dir", required=True)
    ap.add_argument("--title", default=None)
    ap.add_argument("--lead", default=None)
    ap.add_argument("--out", default="index.html", help="file name inside the project dir")
    a = ap.parse_args()

    base = Path(a.project_dir).resolve()
    groups = collect(base / "images")
    if not groups:
        print("no images matched the naming pattern under images/", file=sys.stderr)
        return 1

    # char -> outfit -> mode -> pose -> latest item
    chars = defaultdict(lambda: defaultdict(lambda: defaultdict(dict)))
    for (c, o, p, m), items in groups.items():
        chars[c][o][m][p] = items[-1]

    title = a.title or f"{base.name} 一覧"
    req = next(iter(groups.values()))[-1]["meta"].get("request", {})
    lead = a.lead or (f"NovelAI（{req.get('model', '')} / {req.get('orientation', '')} / {req.get('steps', '')} steps / "
                      f"scale {req.get('scale', '')}）で生成。キャラクターごとに同じseedを使用。画像をクリックすると拡大表示します。")

    nav, secs = [], []
    for idx, (c, outfits) in enumerate(chars.items()):
        color = PALETTE[idx % len(PALETTE)]
        nav.append(f'<a href="#{html.escape(c)}"><span style="background:{color}"></span>{html.escape(c)}</a>')
        poses = list(dict.fromkeys(p for o in outfits.values() for m in o.values() for p in m))
        seed = next(i["seed"] for o in outfits.values() for m in o.values() for i in m.values())
        rows = ["<thead><tr><th class='row'>衣装</th>" + "".join(f"<th>{html.escape(p)}</th>" for p in poses) + "</tr></thead><tbody>"]
        for o, modes in outfits.items():
            first = True
            for mode in ("bg", "transparent"):
                if mode not in modes:
                    continue
                cls = " class='outfit-start'" if first else ""
                head = (f"<div class='outfit'>{html.escape(o)}</div>" if first else "") + f"<span class='mode'>{MODE_LABEL[mode]}</span>"
                tds = []
                for p in poses:
                    it = modes[mode].get(p)
                    if not it:
                        tds.append("<td></td>")
                        continue
                    src = rel(it["path"], base)
                    cap = f"{c} / {o} / {p} / {MODE_LABEL[mode]} (v{it['ver']})"
                    chk = ' class="checker"' if mode == "transparent" else ""
                    ver = f"<div class='ver'>v{it['ver']}</div>" if it["ver"] > 1 else ""
                    tds.append(f"<td><figure><button type='button' data-src='{html.escape(src)}' data-cap='{html.escape(cap)}'>"
                               f"<img src='{html.escape(src)}' alt='{html.escape(cap)}' loading='lazy'{chk}></button>{ver}</figure></td>")
                rows.append(f"<tr{cls}><th class='row'>{head}</th>{''.join(tds)}</tr>")
                first = False
        rows.append("</tbody>")
        secs.append(f"<section id='{html.escape(c)}' style='--c:{color}'><div class='char-head'><h2>{html.escape(c)}</h2>"
                    f"<span class='meta'>seed {html.escape(seed)} / 衣装 {len(outfits)}種 × ポーズ {len(poses)}種</span></div>"
                    f"<div class='wrap'><table>{''.join(rows)}</table></div></section>")

    links = ["<a href='prompts.md'>prompts.md</a>"] if (base / "prompts.md").exists() else []
    if (base / "compare.html").exists():
        links.append("<a href='compare.html'>新旧比較</a>")
    foot = f"<footer>{' ／ '.join(links)}</footer>" if links else ""
    doc = (f"<!doctype html><html lang='ja'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
           f"<title>{html.escape(title)}</title><style>{CSS}</style></head><body><main><h1>{html.escape(title)}</h1>"
           f"<p class='lead'>{html.escape(lead)}</p><nav>{''.join(nav)}</nav>{''.join(secs)}{foot}</main>"
           f"<dialog id='dlg'><img alt=''><p></p></dialog><script>{JS}</script></body></html>")
    out = base / a.out
    out.write_text(doc, encoding="utf-8")
    print(json.dumps({"out": str(out), "characters": len(chars), "images": len(groups)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
