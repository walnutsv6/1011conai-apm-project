#!/usr/bin/env python3
"""Build the page-turning book viewer (index.html) for a gravure CG book.

Usage:
  python build_book.py --project-dir output/novelai-imagegen/<project> [--title TITLE] [--out index.html]

Reads <project-dir>/manifest.json (written by build_requests.py: every expected page cell, in order)
and looks for images in <project-dir>/images/<character>/<stem>[-note][-vN]-seed<seed>.png
(superseded/ is ignored; the highest vN wins). Cells without an image get a dashed placeholder frame
("ユーザー生成枠" for the body pages the user generates), so they appear once the PNGs are in place.
Standard library only; no API key needed. Safe to run any time (also from update-book.ps1 / .sh).

No per-cut captions are shown (the pages are just the pictures). The page: cover -> contents -> chapter title page -> spreads (2 cuts per spread; 1 on narrow screens,
landscape cuts alone). Arrow keys / swipe / edge click turn pages; a view switch filters the nude
compositions (all / covered / open); "images only" hides pages with no image yet.
"""
import argparse
import html
import json
import re
import sys
from pathlib import Path


def find_image(images_dir, character, stem):
    pat = re.compile(re.escape(stem) + r"(?:-(?!v\d+-|seed)[^-]+)*(?:-v(?P<ver>\d+))?-seed(?P<seed>\d+)\.png$")
    folder = images_dir / character
    best = None
    if not folder.is_dir():
        return None
    for png in folder.iterdir():
        if png.suffix != ".png":
            continue
        m = pat.fullmatch(png.name)
        if m:
            ver = int(m.group("ver") or 1)
            if best is None or ver > best[0]:
                best = (ver, png)
    return best


CSS = """
:root{--bg:#f4f1f7;--panel:#fff;--text:#1d1730;--muted:#6b6480;--line:#ddd7e8;--accent:#c2185b}
@media (prefers-color-scheme:dark){:root{--bg:#0f0a1d;--panel:#1a1230;--text:#f1eefb;--muted:#a59dbd;--line:#2e2550;--accent:#ff5aa8}}
*{box-sizing:border-box}html,body{height:100%}
body{margin:0;background:var(--bg);color:var(--text);font-family:system-ui,-apple-system,"Segoe UI","Hiragino Sans","Yu Gothic UI",sans-serif;display:flex;flex-direction:column}
header{display:flex;flex-wrap:wrap;align-items:center;gap:8px 16px;padding:10px 16px;border-bottom:1px solid var(--line);background:var(--panel)}
header h1{margin:0;font-size:1.05rem}header .grow{flex:1}
header label,header button,header select{font:inherit;font-size:.85rem;color:var(--text)}
button{border:1px solid var(--line);background:var(--bg);border-radius:8px;padding:5px 12px;cursor:pointer}
button:hover{border-color:var(--accent)}button:disabled{opacity:.4;cursor:default}
#stage{flex:1;min-height:0;display:flex;align-items:center;justify-content:center;padding:12px 16px;position:relative;touch-action:pan-y}
.page{width:100%;max-width:1100px;height:100%;display:flex;align-items:center;justify-content:center;gap:16px}
.fig{flex:1 1 0;min-width:0;height:100%;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:6px}
.frame{max-width:100%;max-height:100%;aspect-ratio:832/1216;height:100%;border-radius:8px;overflow:hidden;background:var(--panel);border:1px solid var(--line);display:flex;align-items:center;justify-content:center;color:var(--muted);text-align:center;font-size:.9rem}
.frame.land{aspect-ratio:1216/832;height:auto;width:100%}
.frame.empty{border:2px dashed var(--line)}
.frame img{width:100%;height:100%;object-fit:cover;display:block;cursor:zoom-in}
.cover{flex-direction:column}
.title-page{flex-direction:column;text-align:center;gap:8px}
.title-page h2{margin:0;font-size:2rem}.title-page p{margin:0;color:var(--muted)}
.toc{flex-direction:column;align-items:stretch;max-width:520px;gap:8px}
.toc h2{margin:0 0 4px}.toc button{text-align:left;padding:10px 14px;display:flex;justify-content:space-between;gap:12px}
nav.bar{display:flex;align-items:center;justify-content:center;gap:12px;padding:8px 16px;border-top:1px solid var(--line);background:var(--panel)}
#pos{min-width:6em;text-align:center;font-size:.85rem;color:var(--muted)}
#zoom{position:fixed;inset:0;background:rgba(0,0,0,.88);display:none;align-items:center;justify-content:center;z-index:10;cursor:zoom-out}
#zoom img{max-width:96vw;max-height:96vh;object-fit:contain}
@media (max-width:700px){.page{gap:8px}}
"""

JS = r"""
const D = JSON.parse(document.getElementById('data').textContent);
const stage = document.getElementById('stage');
const pos = document.getElementById('pos');
const prevB = document.getElementById('prev'), nextB = document.getElementById('next');
const viewSel = document.getElementById('view'), onlyImg = document.getElementById('onlyimg');
let pages = [], idx = 0;
function pref(k, v){ try { if (v === undefined) return localStorage.getItem('gb-' + k); localStorage.setItem('gb-' + k, v); } catch (e) {} return null; }
function esc(s){ return String(s).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c])); }
function fig(c){
  const land = c.orientation === 'landscape';
  const inner = c.image
    ? `<img src="${esc(c.image)}" alt="${esc(c.label)}" loading="lazy">`
    : `<span>${c.script_only ? 'ユーザー生成枠' : '未生成'}<br><small>${esc(c.stem)}</small></span>`;
  return `<div class="fig"><div class="frame${land ? ' land' : ''}${c.image ? '' : ' empty'}">${inner}</div></div>`;
}
function visible(c){
  if (viewSel.value === 'covered' && c.variant === 'open') return false;
  if (viewSel.value === 'open' && c.variant === 'covered') return false;
  return !onlyImg.checked || !!c.image;
}
function build(){
  pages = [];
  const cover = D.cells.find(c => c.kind === 'cover');
  if (cover) pages.push({t: 'cover', cells: [cover]});
  const body = D.chapters.map(ch => ({ch, cells: D.cells.filter(c => c.kind === 'cut' && c.chapter === ch.id && visible(c))})).filter(x => x.cells.length);
  pages.push({t: 'toc', body});
  body.forEach(x => {
    pages.push({t: 'chapter', ch: x.ch, n: x.cells.length});
    const narrow = window.matchMedia('(max-width:700px)').matches;
    let row = [];
    const flush = () => { if (row.length) pages.push({t: 'spread', ch: x.ch, cells: row}); row = []; };
    x.cells.forEach(c => {
      if (narrow || c.orientation === 'landscape') { flush(); pages.push({t: 'spread', ch: x.ch, cells: [c]}); return; }
      row.push(c); if (row.length === 2) flush();
    });
    flush();
  });
  idx = Math.min(idx, pages.length - 1);
}
function render(){
  const p = pages[idx]; let h = '';
  if (p.t === 'cover') h = `<div class="page cover">${fig(p.cells[0])}</div>`;
  else if (p.t === 'toc') h = `<div class="page toc"><h2>${esc(D.title)}</h2>` + p.body.map(x => `<button data-go="${esc(x.ch.id)}"><span>${esc(x.ch.title)}</span><span>${x.cells.length}</span></button>`).join('') + '</div>';
  else if (p.t === 'chapter') h = `<div class="page title-page"><p>Chapter</p><h2>${esc(p.ch.title)}</h2><p>${p.n} cuts</p></div>`;
  else h = `<div class="page">${p.cells.map(fig).join('')}</div>`;
  stage.innerHTML = h;
  pos.textContent = `${idx + 1} / ${pages.length}`;
  prevB.disabled = idx === 0; nextB.disabled = idx === pages.length - 1;
  pref('idx', idx);
}
function go(n){ idx = Math.max(0, Math.min(pages.length - 1, n)); render(); }
prevB.onclick = () => go(idx - 1); nextB.onclick = () => go(idx + 1);
document.addEventListener('keydown', e => {
  if (e.key === 'ArrowRight' || e.key === 'PageDown') go(idx + 1);
  if (e.key === 'ArrowLeft' || e.key === 'PageUp') go(idx - 1);
  if (e.key === 'Escape') document.getElementById('zoom').style.display = 'none';
});
let sx = null;
stage.addEventListener('touchstart', e => { sx = e.touches[0].clientX; }, {passive: true});
stage.addEventListener('touchend', e => { if (sx === null) return; const dx = e.changedTouches[0].clientX - sx; sx = null; if (Math.abs(dx) > 50) go(idx + (dx < 0 ? 1 : -1)); });
stage.addEventListener('click', e => {
  const img = e.target.closest('img');
  if (img) { const z = document.getElementById('zoom'); z.querySelector('img').src = img.src; z.style.display = 'flex'; return; }
  const b = e.target.closest('[data-go]');
  if (b) { const i = pages.findIndex(p => p.t === 'chapter' && p.ch.id === b.dataset.go); if (i >= 0) go(i); }
});
document.getElementById('zoom').onclick = e => { e.currentTarget.style.display = 'none'; };
viewSel.value = pref('view') || 'all'; onlyImg.checked = pref('only') === '1';
viewSel.onchange = () => { pref('view', viewSel.value); build(); render(); };
onlyImg.onchange = () => { pref('only', onlyImg.checked ? '1' : '0'); build(); render(); };
window.addEventListener('resize', () => { const n = pages.length; build(); if (pages.length !== n) render(); });
build(); idx = Math.min(parseInt(pref('idx') || '0', 10) || 0, pages.length - 1); render();
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-dir", required=True)
    ap.add_argument("--title")
    ap.add_argument("--out", default="index.html")
    a = ap.parse_args()
    base = Path(a.project_dir)
    mf = base / "manifest.json"
    if not mf.exists():
        print("manifest.json not found; run build_requests.py first", file=sys.stderr)
        return 2
    manifest = json.loads(mf.read_text(encoding="utf-8"))
    images = base / "images"
    title = a.title or manifest.get("title") or manifest.get("project", base.name)

    found = 0
    for c in manifest["cells"]:
        hit = find_image(images, c["character"], c["stem"])
        c["image"] = hit[1].relative_to(base).as_posix() if hit else ""
        found += bool(hit)
    data = {"title": title, "chapters": manifest["chapters"], "cells": manifest["cells"]}
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")

    page = f"""<!doctype html>
<html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title><style>{CSS}</style></head>
<body>
<header><h1>{html.escape(title)}</h1><span class="grow"></span>
<label>表示 <select id="view"><option value="all">すべて</option><option value="covered">隠す構図</option><option value="open">隠さない構図</option></select></label>
<label><input type="checkbox" id="onlyimg"> 画像のあるページのみ</label></header>
<div id="stage"></div>
<nav class="bar"><button id="prev">&larr; 前へ</button><span id="pos"></span><button id="next">次へ &rarr;</button></nav>
<div id="zoom"><img alt=""></div>
<script id="data" type="application/json">{payload}</script>
<script>{JS}</script>
</body></html>
"""
    out = base / a.out
    out.write_text(page, encoding="utf-8")
    print(json.dumps({"out": str(out), "cells": len(manifest["cells"]), "images": found}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
