#!/usr/bin/env python3
"""Build an old-vs-new comparison page. Run only when a comparison is needed.

Usage:
  python build_compare.py --project-dir <project> [--character mia] [--outfit bunny] [--pose lean] [--mode bg]
                          [--out compare.html] [--title TITLE]

Collects every version of each cell (files in images/<char>/ plus images/<char>/superseded/),
keeps cells that have 2+ versions, and shows them oldest -> newest with a prompt tag diff
(+added / -removed) between consecutive versions. Writes <project>/compare.html
(or the --out name), separate from index.html.
"""
import argparse
import html
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_index import collect, rel, MODE_LABEL  # noqa: E402

CSS = """
:root{--bg:#fff;--fg:#1d1d1f;--mut:#6b6b70;--card:#f4f4f6;--line:#d8d8de;--add:#1a7f37;--del:#c62828;--acc:#2f6fed}
@media (prefers-color-scheme:dark){:root{--bg:#141416;--fg:#ececf0;--mut:#9a9aa3;--card:#1d1d21;--line:#34343a;--add:#5fd37f;--del:#ff7b7b;--acc:#6b9bff}}
*{box-sizing:border-box}body{margin:0;padding:16px;background:var(--bg);color:var(--fg);font:14px/1.5 system-ui,sans-serif}
h1{font-size:20px;margin:0 0 4px}.sub{color:var(--mut);margin:0 0 16px}a{color:var(--acc)}
.case{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:10px;margin:0 0 16px}
.case h2{font-size:15px;margin:0 0 8px}
.vers{display:flex;gap:10px;overflow-x:auto;align-items:flex-start}
.v{flex:0 0 260px;margin:0}.v img{width:100%;aspect-ratio:832/1216;object-fit:cover;border-radius:6px;display:block;cursor:zoom-in}
.v figcaption{font-size:12px;color:var(--mut);margin-top:4px}
.diff{font-size:12px;margin-top:6px;word-break:break-word}.add{color:var(--add)}.del{color:var(--del)}
.checker{background-color:#fff;background-image:linear-gradient(45deg,#d4d4d8 25%,transparent 25%,transparent 75%,#d4d4d8 75%),linear-gradient(45deg,#d4d4d8 25%,transparent 25%,transparent 75%,#d4d4d8 75%);background-size:16px 16px;background-position:0 0,8px 8px}
dialog{border:0;padding:0;background:transparent;max-width:96vw;max-height:96vh}dialog::backdrop{background:#000d}dialog img{max-width:96vw;max-height:94vh;display:block}
"""
JS = ("const d=document.getElementById('dlg'),i=d.querySelector('img');"
      "document.addEventListener('click',e=>{const t=e.target.closest('.v img');"
      "if(t){i.src=t.src;d.showModal()}else if(e.target===d){d.close()}});")


def tags(meta, key):
    s = meta.get("request", {}).get(key, "")
    return [t.strip() for t in s.split(",") if t.strip()]


def diff_html(prev, cur):
    out = []
    for key, label in (("prompt", "prompt"), ("negative_prompt", "negative")):
        a, b = tags(prev["meta"], key), tags(cur["meta"], key)
        add = [t for t in b if t not in a]
        dele = [t for t in a if t not in b]
        if add or dele:
            out.append(f"<div class='diff'><b>{label}</b> " + " ".join(
                [f"<span class='add'>+{html.escape(t)}</span>" for t in add] +
                [f"<span class='del'>−{html.escape(t)}</span>" for t in dele]) + "</div>")
    if prev["seed"] != cur["seed"]:
        out.append(f"<div class='diff'>seed {prev['seed']} → {cur['seed']}</div>")
    return "".join(out) or "<div class='diff'>(タグ差分なし)</div>"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-dir", required=True)
    ap.add_argument("--character")
    ap.add_argument("--outfit")
    ap.add_argument("--pose")
    ap.add_argument("--mode", choices=["bg", "transparent"])
    ap.add_argument("--out", default="compare.html")
    ap.add_argument("--title")
    a = ap.parse_args()

    base = Path(a.project_dir).resolve()
    groups = collect(base / "images", include_superseded=True)
    flt = [a.character, a.outfit, a.pose, a.mode]
    cases = []
    for key, items in groups.items():
        if any(v and key[i] != v for i, v in enumerate(flt)):
            continue
        byver = {}
        for it in items:  # one item per version number
            byver[it["ver"]] = it
        vers = [byver[v] for v in sorted(byver)]
        if len(vers) >= 2:
            cases.append((key, vers))
    if not cases:
        print("no cells with 2+ versions matched", file=sys.stderr)
        return 1

    body = []
    for (c, o, p, m), vers in sorted(cases, key=lambda x: x[0]):
        figs = []
        for n, v in enumerate(vers):
            src = rel(v["path"], base)
            chk = ' class="checker"' if m == "transparent" else ""
            label = f"v{v['ver']}" + (" (最新)" if n == len(vers) - 1 else "") + (f" {v['note']}" if v["note"] else "")
            d = diff_html(vers[n - 1], v) if n else ""
            figs.append(f"<figure class='v'><img src='{html.escape(src)}' alt='{html.escape(label)}' loading='lazy'{chk}>"
                        f"<figcaption>{html.escape(label)}</figcaption>{d}</figure>")
        body.append(f"<div class='case'><h2>{html.escape(c)} / {html.escape(o)} / {html.escape(p)} / {MODE_LABEL[m]}</h2>"
                    f"<div class='vers'>{''.join(figs)}</div></div>")

    title = a.title or f"{base.name} 新旧比較"
    back = "<a href='index.html'>← 一覧に戻る</a>" if (base / "index.html").exists() else ""
    doc = (f"<!doctype html><html lang='ja'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
           f"<title>{html.escape(title)}</title><style>{CSS}</style></head><body><h1>{html.escape(title)}</h1>"
           f"<p class='sub'>古い版 → 新しい版。差分は直前の版とのタグ比較（<span class='add'>+追加</span> / <span class='del'>−削除</span>）。 {back}</p>"
           f"{''.join(body)}<dialog id='dlg'><img alt=''></dialog><script>{JS}</script></body></html>")
    out = base / a.out
    out.write_text(doc, encoding="utf-8")
    print(json.dumps({"out": str(out), "cases": len(cases)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
