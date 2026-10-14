#!/usr/bin/env python3
"""Build the project index page for an undressing sequence.

Usage:
  python build_index.py --project-dir output/novelai-imagegen/<project> [--title TITLE] [--out index.html]

Reads <project-dir>/manifest.json (written by build_requests.py: every expected stage cell, in order)
and looks for images in <project-dir>/images/<character>/<stem>[-note][-vN]-seed<seed>.png
(superseded/ is ignored; the highest vN wins). Cells without an image get a placeholder frame, so
topless / nude stages the user generates later simply appear once the PNGs are in place.
The page has one section per character: a slideshow viewer (play / pause / step / speed, mode and
variant switches; missing frames are skipped) and a stage table.
"""
import argparse
import html
import json
import re
import sys
from pathlib import Path

PALETTE = ["#e0207f", "#1ea7c9", "#2e9e5b", "#d9822b", "#7a5af8", "#c9462c"]
MODE_LABEL = {"bg": "背景あり", "transparent": "透過"}
VARIANT_LABEL = {"covered": "隠す", "open": "隠さない", "": ""}


def find_image(images_dir, character, stem):
    pat = re.compile(re.escape(stem) + r"(?:-(?!v\d+-|seed)[^-]+)*(?:-v(?P<ver>\d+))?-seed(?P<seed>\d+)\.png$")
    best = None
    folder = images_dir / character
    if not folder.exists():
        return None
    for png in folder.iterdir():
        if png.suffix != ".png" or "superseded" in png.parts:
            continue
        m = pat.fullmatch(png.name)
        if m:
            ver = int(m.group("ver") or 1)
            if best is None or ver > best[0]:
                best = (ver, png)
    return best


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
section{margin:0 0 48px;scroll-margin-top:16px}
.char-head{display:flex;align-items:baseline;gap:12px;flex-wrap:wrap;padding:0 0 10px;margin:0 0 12px;border-bottom:4px solid var(--c)}
.char-head h2{margin:0;font-size:1.5rem}.char-head .meta{color:var(--muted);font-size:.85rem}
.viewer{display:flex;gap:16px;flex-wrap:wrap;margin:0 0 16px;padding:12px;border:1px solid var(--line);border-radius:12px;background:var(--panel)}
.stage-box{flex:0 0 auto;width:min(320px,100%)}
.stage-box .frame{width:100%;aspect-ratio:832/1216;border-radius:8px;overflow:hidden;background:var(--bg);display:flex;align-items:center;justify-content:center;color:var(--muted)}
.stage-box .frame img{width:100%;height:100%;object-fit:cover;display:block}
.stage-box .cap{margin:6px 0 0;text-align:center;font-weight:700}.stage-box .sub{text-align:center;color:var(--muted);font-size:.8rem}
.ctrl{flex:1 1 220px;display:flex;flex-direction:column;gap:10px;justify-content:center}
.ctrl .row{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
.ctrl button,.ctrl select{font:inherit;padding:6px 12px;border:1px solid var(--line);border-radius:8px;background:var(--bg);color:var(--text);cursor:pointer}
.ctrl button.on{background:var(--accent);color:#fff;border-color:var(--accent)}
.ctrl input[type=range]{width:100%}.ctrl label{font-size:.85rem;color:var(--muted)}
.wrap{overflow-x:auto;border:1px solid var(--line);border-radius:12px;background:var(--panel)}
table{border-collapse:collapse;min-width:100%}
th,td{border-bottom:1px solid var(--line);border-right:1px solid var(--line);padding:10px;vertical-align:top;min-width:170px}
th.row{text-align:left;min-width:100px;position:sticky;left:0;background:var(--panel)}
tr:last-child td,tr:last-child th{border-bottom:0}td:last-child,th:last-child{border-right:0}
thead th{text-align:center;font-size:.85rem}
.badge{display:inline-block;margin-top:2px;padding:0 8px;border-radius:999px;font-size:.7rem;font-weight:600;background:color-mix(in srgb,var(--muted) 16%,transparent);color:var(--muted)}
figure{margin:0;text-align:center}figure button{padding:0;border:0;background:none;cursor:zoom-in;display:block;width:100%}
figure img{width:100%;max-width:240px;aspect-ratio:832/1216;object-fit:cover;border-radius:8px;display:block;margin:0 auto}
.ph{width:100%;max-width:240px;aspect-ratio:832/1216;margin:0 auto;border:2px dashed var(--line);border-radius:8px;display:flex;align-items:center;justify-content:center;text-align:center;padding:8px;color:var(--muted);font-size:.8rem}
.ver{font-size:.7rem;color:var(--muted)}
.checker{background-color:#fff;background-image:linear-gradient(45deg,#d4d4d8 25%,transparent 25%,transparent 75%,#d4d4d8 75%),linear-gradient(45deg,#d4d4d8 25%,transparent 25%,transparent 75%,#d4d4d8 75%);background-size:16px 16px;background-position:0 0,8px 8px}
footer{color:var(--muted);font-size:.8rem;border-top:1px solid var(--line);padding-top:16px}footer a{color:var(--accent)}
dialog{border:0;padding:0;background:transparent;max-width:96vw;max-height:96vh}dialog::backdrop{background:rgba(8,4,18,.85)}
dialog img{max-width:96vw;max-height:90vh;display:block;border-radius:8px}dialog p{color:#fff;text-align:center;margin:8px 0 0;font-size:.85rem}
"""

JS = """
const DATA=JSON.parse(document.getElementById('data').textContent);
const dlg=document.getElementById('dlg'),di=dlg.querySelector('img'),dc=dlg.querySelector('p');
document.addEventListener('click',e=>{const b=e.target.closest('figure button');
if(b){di.src=b.dataset.src;dc.textContent=b.dataset.cap;dlg.showModal()}else if(e.target===dlg){dlg.close()}});
document.querySelectorAll('.viewer').forEach(v=>{
  const c=v.dataset.char,frame=v.querySelector('.frame'),cap=v.querySelector('.cap'),sub=v.querySelector('.sub'),
    play=v.querySelector('.play'),range=v.querySelector('input[type=range]'),pos=v.querySelector('.pos'),
    modeSel=v.querySelector('.mode'),varSel=v.querySelector('.variant'),spd=v.querySelector('.speed');
  let frames=[],i=0,timer=null;
  function build(){
    const all=DATA[c].filter(f=>f.mode===modeSel.value&&f.src),pref=varSel.value;
    const byStage=new Map();all.forEach(f=>{if(!byStage.has(f.stage))byStage.set(f.stage,[]);byStage.get(f.stage).push(f)});
    frames=[];byStage.forEach(list=>{
      if(pref==='all'||!list.some(f=>f.variant))list.forEach(f=>frames.push(f));
      else{const m=list.filter(f=>f.variant===pref);(m.length?m:list).forEach(f=>frames.push(f))}});
    range.max=Math.max(frames.length-1,0);i=Math.min(i,Math.max(frames.length-1,0));show()}
  function show(){
    if(!frames.length){frame.textContent='表示できる画像がありません';cap.textContent='';sub.textContent='';pos.textContent='0 / 0';return}
    const f=frames[i];frame.className='frame'+(f.mode==='transparent'?' checker':'');
    frame.innerHTML='';const im=document.createElement('img');im.src=f.src;im.alt=f.label;frame.appendChild(im);
    cap.textContent=f.label+(f.variant_label?'（'+f.variant_label+'）':'');sub.textContent=f.class_label;
    range.value=i;pos.textContent=(i+1)+' / '+frames.length}
  function step(d){if(!frames.length)return;i=(i+d+frames.length)%frames.length;show()}
  function stop(){clearInterval(timer);timer=null;play.textContent='▶ 再生';play.classList.remove('on')}
  function start(){stop();play.textContent='⏸ 一時停止';play.classList.add('on');timer=setInterval(()=>step(1),+spd.value)}
  v.querySelector('.prev').onclick=()=>{stop();step(-1)};v.querySelector('.next').onclick=()=>{stop();step(1)};
  play.onclick=()=>timer?stop():start();range.oninput=()=>{stop();i=+range.value;show()};
  spd.onchange=()=>{if(timer)start()};modeSel.onchange=varSel.onchange=()=>{i=0;build()};build()});
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-dir", required=True)
    ap.add_argument("--title", default=None)
    ap.add_argument("--lead", default=None)
    ap.add_argument("--out", default="index.html")
    a = ap.parse_args()

    base = Path(a.project_dir).resolve()
    mf = base / "manifest.json"
    if not mf.exists():
        print("manifest.json not found; run build_requests.py first", file=sys.stderr)
        return 1
    manifest = json.loads(mf.read_text(encoding="utf-8"))
    images = base / "images"

    chars = {}
    for c in manifest["cells"]:
        chars.setdefault(c["character"], []).append(c)

    title = a.title or f"{manifest.get('project', base.name)} 脱衣シーケンス"
    lead = a.lead or ("NovelAIで生成。キャラクターごとに同じseedを使用し、ステージ順に並べています。"
                      "点線枠は未生成のステージです（トップレス・ヌード系はユーザー実行用スクリプトで生成し、"
                      "画像を images/ に置いて再ビルドすると表示されます）。画像をクリックすると拡大します。")

    nav, secs, data, found, total = [], [], {}, 0, 0
    for idx, (cname, cells) in enumerate(chars.items()):
        color = PALETTE[idx % len(PALETTE)]
        nav.append(f'<a href="#{html.escape(cname)}"><span style="background:{color}"></span>{html.escape(cname)}</a>')
        modes = list(dict.fromkeys(c["mode"] for c in cells))
        cols = list(dict.fromkeys((c["stage"], c["variant"]) for c in cells))
        by_key = {(c["stage"], c["variant"], c["mode"]): c for c in cells}
        frames, rows = [], []
        for mode in modes:
            tds = []
            for stage, variant in cols:
                c = by_key[(stage, variant, mode)]
                total += 1
                hit = find_image(images, cname, c["stem"])
                label = c["label"]
                vlab = VARIANT_LABEL.get(variant, variant)
                cap = f"{cname} / {label}" + (f"（{vlab}）" if vlab else "") + f" / {MODE_LABEL[mode]}"
                src = None
                if hit:
                    found += 1
                    ver, png = hit
                    src = png.relative_to(base).as_posix()
                    chk = ' class="checker"' if mode == "transparent" else ""
                    vv = f"<div class='ver'>v{ver}</div>" if ver > 1 else ""
                    tds.append(f"<td><figure><button type='button' data-src='{html.escape(src)}' data-cap='{html.escape(cap)}'>"
                               f"<img src='{html.escape(src)}' alt='{html.escape(cap)}' loading='lazy'{chk}></button>{vv}</figure></td>")
                else:
                    msg = "ユーザー生成枠<br>（未生成）" if c["script_only"] else "未生成"
                    tds.append(f"<td><div class='ph'>{msg}</div></td>")
                frames.append({"stage": stage, "label": label, "variant": variant, "variant_label": vlab,
                               "class_label": c["class_label"], "mode": mode, "src": src})
            rows.append(f"<tr><th class='row'>{MODE_LABEL[mode]}</th>{''.join(tds)}</tr>")
        # frames are mode-major in the table; the viewer needs stage order within a mode
        order = {k: n for n, k in enumerate(cols)}
        frames.sort(key=lambda f: (f["mode"], order[(f["stage"], f["variant"])]))
        data[cname] = frames
        head = "".join(
            f"<th>{html.escape(next(c['label'] for c in cells if c['stage'] == s))}"
            + (f" <span class='badge'>{html.escape(VARIANT_LABEL.get(v, v))}</span>" if v else "")
            + f"<br><span class='badge'>{html.escape(next(c['class_label'] for c in cells if c['stage'] == s))}</span></th>"
            for s, v in cols)
        seed = cells[0]["seed"]
        has_variant = any(v for _, v in cols)
        viewer = (
            f"<div class='viewer' data-char='{html.escape(cname)}'>"
            f"<div class='stage-box'><div class='frame'></div><div class='cap'></div><div class='sub'></div></div>"
            f"<div class='ctrl'><div class='row'><button class='prev'>◀</button><button class='play'>▶ 再生</button>"
            f"<button class='next'>▶|</button><span class='pos'></span></div>"
            f"<input type='range' min='0' max='0' value='0'>"
            f"<div class='row'><label>モード <select class='mode'>"
            + "".join(f"<option value='{m}'>{MODE_LABEL[m]}</option>" for m in modes) + "</select></label>"
            f"<label>ヌード構図 <select class='variant'><option value='covered'>隠す優先</option>"
            f"<option value='open'>隠さない優先</option><option value='all'>両方</option></select></label>"
            f"<label>間隔 <select class='speed'><option value='2000'>ゆっくり</option><option value='1200' selected>標準</option>"
            f"<option value='600'>はやい</option></select></label></div></div></div>"
        )
        secs.append(f"<section id='{html.escape(cname)}' style='--c:{color}'><div class='char-head'><h2>{html.escape(cname)}</h2>"
                    f"<span class='meta'>seed {html.escape(str(seed))} / ステージ {len(manifest['stages'])} / ポーズ: "
                    f"{'固定' if manifest.get('pose_mode') == 'fixed' else 'ステージごと'}</span></div>{viewer}"
                    f"<div class='wrap'><table><thead><tr><th class='row'></th>{head}</tr></thead>"
                    f"<tbody>{''.join(rows)}</tbody></table></div></section>")

    links = ["<a href='prompts.md'>prompts.md</a>"] if (base / "prompts.md").exists() else []
    foot = f"<footer>{' ／ '.join(links)}</footer>" if links else ""
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    doc = (f"<!doctype html><html lang='ja'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
           f"<title>{html.escape(title)}</title><style>{CSS}</style></head><body><main><h1>{html.escape(title)}</h1>"
           f"<p class='lead'>{html.escape(lead)}</p><nav>{''.join(nav)}</nav>{''.join(secs)}{foot}</main>"
           f"<dialog id='dlg'><img alt=''><p></p></dialog><script id='data' type='application/json'>{payload}</script>"
           f"<script>{JS}</script></body></html>")
    out = base / a.out
    out.write_text(doc, encoding="utf-8")
    print(json.dumps({"out": str(out), "characters": len(chars), "images": found, "cells": total,
                      "missing": total - found}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
