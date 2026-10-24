#!/usr/bin/env python3
"""Build the preview page (asset table + game-like simulator) for a strip-game project.

Usage:
  python build_preview.py --project-dir output/novelai-imagegen/<project> [--title TITLE] [--out index.html]

Reads <project>/cells.json and looks for each cell's image (inpaint method: the cutout under
images/<character>/cutout/ when present, else the grey plate). Missing cells get a dashed frame
("ユーザー生成枠" for script-only cells), so topless / nude frames exist before the user fills them.
Per character and method: a simulator (event buttons from the preset; advancing plays the
transition frames, then shows the next stage), an onion-skin compare of any two cells, and the
stage x expression / special-pose table. With spec.method_by_kind (methods: mixed) a first tab
"mixed" combines each cell kind from its method.
"""
import argparse
import html
import json
import os
from pathlib import Path

from common import cell_image

METHOD_LABEL = {"mixed": "A+B 組み合わせ", "seed": "A: seed固定", "inpaint": "B: inpaint"}
VARIANT_LABEL = {"covered": "隠す", "open": "隠さない", "": ""}


def rel(p, start):
    return os.path.relpath(p, start).replace("\\", "/")


CSS = """
:root{--bg:#f6f4fa;--panel:#fff;--text:#1d1730;--muted:#6b6480;--line:#e3dfec;--accent:#e0207f;--chk1:#e9e6ef;--chk2:#f8f7fb}
@media (prefers-color-scheme:dark){:root{--bg:#120b22;--panel:#1c1433;--text:#f1eefb;--muted:#a59dbd;--line:#2e2550;--accent:#ff4fa3;--chk1:#241b3d;--chk2:#2c2248}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font-family:system-ui,-apple-system,"Segoe UI","Hiragino Sans","Yu Gothic UI",sans-serif;line-height:1.5}
main{max-width:1400px;margin:0 auto;padding:28px 16px 48px}h1{margin:0 0 4px;font-size:1.5rem}.lead{margin:0 0 14px;color:var(--muted);font-size:.9rem}
section{margin:0 0 40px}h2{margin:0 0 10px;font-size:1.3rem;border-bottom:4px solid var(--accent);padding-bottom:6px}
.tabs{display:flex;gap:6px;margin:0 0 12px;flex-wrap:wrap}.tabs button,.ctl button{font:inherit;padding:5px 12px;border-radius:8px;border:1px solid var(--line);background:var(--panel);color:var(--text);cursor:pointer}
.tabs button.on{background:var(--accent);color:#fff;border-color:var(--accent)}
.sim{display:grid;grid-template-columns:minmax(260px,520px) 1fr;gap:16px;padding:12px;border:1px solid var(--line);border-radius:12px;background:var(--panel);margin:0 0 16px}
@media (max-width:800px){.sim{grid-template-columns:1fr}}
.frame{position:relative;width:100%;border-radius:8px;overflow:hidden;display:flex;align-items:center;justify-content:center;color:var(--muted);font-size:.85rem;
background:repeating-conic-gradient(var(--chk1) 0 25%,var(--chk2) 0 50%) 0 0/24px 24px}
.frame img{position:absolute;inset:0;width:100%;height:100%;object-fit:contain}.frame .ph{padding:8px;text-align:center;border:2px dashed var(--line);border-radius:8px;margin:12%}
.status{font-weight:700;margin:6px 0 2px}.sub{color:var(--muted);font-size:.82rem}
.ctl{display:flex;flex-wrap:wrap;gap:6px;margin:8px 0}.ctl button.ev{border-color:var(--accent)}
.ctl label{font-size:.85rem;color:var(--muted);display:flex;align-items:center;gap:4px}
.log{font-size:.8rem;color:var(--muted);max-height:160px;overflow:auto;border-top:1px solid var(--line);margin-top:8px;padding-top:6px}
.cmp{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:10px 0}.cmp select{font:inherit;max-width:100%}
.cmpf{width:min(360px,100%)}
.tbl{overflow-x:auto;border:1px solid var(--line);border-radius:12px;background:var(--panel)}
table{border-collapse:collapse;font-size:.78rem}th,td{border-bottom:1px solid var(--line);padding:6px;vertical-align:top;text-align:center}
th{position:sticky;top:0;background:var(--panel)}td.st{text-align:left;white-space:nowrap;font-weight:600}td.st .sub{font-weight:400}
.cell{width:110px}.cell .frame{width:110px}.cell .ph{margin:6px;font-size:.7rem}.tr td{background:color-mix(in srgb,var(--accent) 6%,transparent)}
"""

JS = r"""
const D = JSON.parse(document.getElementById('data').textContent);
const AR = {portrait:'832/1216', square:'1/1', landscape:'1216/832'};
function cellsOf(ch, m){
  if (m==='mixed') return D.cells.filter(c => c.character===ch && D.method_by_kind[c.kind]===c.method);
  return D.cells.filter(c => c.character===ch && c.method===m);
}
function pick(list, q){ return list.filter(c => Object.entries(q).every(([k,v]) => v===undefined || c[k]===v)); }
function frameHTML(c, ar){
  const style = `aspect-ratio:${ar}`;
  if (c && c.src) return `<div class="frame" style="${style}"><img loading="lazy" src="${c.src}" alt="${c.basename}"></div>`;
  const t = !c ? '素材なし' : (c.script_only ? 'ユーザー生成枠' : '未生成');
  return `<div class="frame" style="${style}"><div class="ph">${t}${c ? '<br>'+c.basename : ''}</div></div>`;
}
function mains(){ return D.stages.filter(s => s.role==='main'); }
function setup(root){
  const ch = root.dataset.char;
  const methods = [...new Set(D.cells.filter(c=>c.character===ch && c.kind!=='oneshot').map(c=>c.method))];
  if (D.method_by_kind) methods.unshift('mixed');
  const tabs = root.querySelector('.tabs'), body = root.querySelector('.body');
  methods.forEach((m,i) => {
    const b = document.createElement('button'); b.textContent = D.method_labels[m]||m;
    b.onclick = () => { tabs.querySelectorAll('button').forEach(x=>x.classList.remove('on')); b.classList.add('on'); render(m); };
    tabs.appendChild(b); if (i===0) { b.classList.add('on'); }
  });
  function render(m){
    const all = cellsOf(ch, m);
    const modes = [...new Set(all.filter(c=>c.kind==='sprite'||c.kind==='transition').map(c=>c.mode).filter(x=>x!=='plate'))];
    if (!modes.length) modes.push('plate');
    let mode = modes.includes('transparent') ? 'transparent' : modes[0];
    // inpaint kinds only have plate cells (shown as cut-outs); seed kinds follow the mode selector
    const md = k => k==='special' ? undefined : (pick(all, {kind:k}).every(c=>c.mode==='plate') ? 'plate' : mode);
    let pref = 'covered', si = 0, expr = 'normal', timer = null, busy = false;
    body.innerHTML = `
      <div class="sim"><div><div class="simf"></div><div class="status"></div><div class="sub info"></div></div>
      <div><div class="ctl evs"></div>
      <div class="ctl"><button class="reset">最初から</button><button class="next">次の段階へ（演出なし）</button>
      <label>隠す/隠さない <select class="pref"><option value="covered">隠す</option><option value="open">隠さない</option></select></label>
      ${modes.length>1 ? `<label>モード <select class="mode">${modes.map(x=>`<option>${x}</option>`).join('')}</select></label>` : ''}</div>
      <div class="ctl exprs"></div><div class="log"></div></div></div>
      <div class="cmp"><b>重ねて比較</b><select class="ca"></select><select class="cb"></select>
        <label>B の不透明度 <input class="op" type="range" min="0" max="100" value="50"></label></div>
      <div class="cmpf"></div>
      <div class="tbl"></div>`;
    const $ = s => body.querySelector(s);
    const ar = AR[D.orientation] || AR.portrait;
    function cellFor(stageId, kind, q){
      let l = pick(all, {stage: stageId, kind, mode: md(kind), ...q});
      if (l.length>1) l = l.filter(c => !c.variant || c.variant===pref).concat(l);
      return l[0];
    }
    function show(c, note){
      $('.simf').innerHTML = frameHTML(c, ar);
      const st = mains()[si];
      $('.status').textContent = `${st.label}（${si+1}/${mains().length}）` + (note ? ' — ' + note : '');
      $('.info').textContent = c ? `${c.basename} / ${D.age_labels[c.age_class]||''}` : '';
    }
    function sprite(e){
      const st = mains()[si];
      let c = cellFor(st.id, 'sprite', {expression: e});
      if (!c || !c.src) { const f = cellFor(st.id, 'sprite', {expression: 'normal'}); if (f && f.src) c = f; }
      return c;
    }
    function log(t){ $('.log').insertAdjacentHTML('afterbegin', `<div>${t}</div>`); }
    const wait = ms => new Promise(r => setTimeout(r, ms));
    async function advance(ev){
      const ms = mains(); if (si >= ms.length-1) { log('最終段階です'); return; }
      const from = D.stages.findIndex(s => s.id===ms[si].id), to = D.stages.findIndex(s => s.id===ms[si+1].id);
      for (const s of D.stages.slice(from+1, to)) {
        const c = cellFor(s.id, 'transition', {});
        $('.simf').innerHTML = frameHTML(c, ar); $('.status').textContent = `${s.label}（途中段階）`;
        await wait(s.duration_ms || 450);
      }
      si += 1; expr = (D.events.after_strip && D.events.after_strip.expression) || 'normal';
      show(sprite(expr), '脱いだ直後');
      if (si === ms.length-1) log('クリア（ご褒美CGへ）');
    }
    async function fire(name){
      if (busy) return; busy = true;
      const ev = D.events[name]; log(ev.label);
      try {
        if (ev.special && ev.special.length) {
          const pid = ev.special[Math.floor(Math.random()*ev.special.length)];
          const c = pick(all, {stage: mains()[si].id, kind:'special', pose: pid})[0];
          show(c, D.special_poses[pid] || pid);
          if (ev.random_special) { busy = false; return; }
          await wait(1100);
        }
        if (ev.expression) { expr = ev.expression; show(sprite(expr), D.expressions[expr] || expr); }
        if (ev.advance > 0) { await wait(700); await advance(ev); }
      } finally { busy = false; }
    }
    Object.entries(D.events).forEach(([k, ev]) => {
      const b = document.createElement('button'); b.className = 'ev'; b.textContent = ev.label; b.onclick = () => fire(k);
      $('.evs').appendChild(b);
    });
    Object.entries(D.expressions).forEach(([k, l]) => {
      const b = document.createElement('button'); b.textContent = l; b.onclick = () => { expr = k; show(sprite(k), l); };
      $('.exprs').appendChild(b);
    });
    $('.reset').onclick = () => { si = 0; expr = 'normal'; show(sprite(expr)); };
    $('.next').onclick = () => { if (si < mains().length-1) { si++; show(sprite(expr)); } };
    $('.pref').onchange = e => { pref = e.target.value; show(sprite(expr)); };
    if ($('.mode')) $('.mode').onchange = e => { mode = e.target.value; show(sprite(expr)); renderTable(); };
    show(sprite('normal'));
    // compare
    const opts = all.filter(c => c.kind!=='oneshot').map((c,i) => `<option value="${i}">${c.basename}</option>`).join('');
    const list = all.filter(c => c.kind!=='oneshot');
    $('.ca').innerHTML = opts; $('.cb').innerHTML = opts; if (list.length>1) $('.cb').value = '1';
    function cmp(){
      const a = list[+$('.ca').value], b = list[+$('.cb').value], op = $('.op').value/100;
      $('.cmpf').innerHTML = `<div class="frame" style="aspect-ratio:${ar}">${a&&a.src?`<img src="${a.src}">`:''}${b&&b.src?`<img src="${b.src}" style="opacity:${op}">`:''}${!(a&&a.src)&&!(b&&b.src)?'<div class="ph">画像なし</div>':''}</div>`;
    }
    ['.ca','.cb','.op'].forEach(s => $(s).oninput = cmp); cmp();
    function renderTable(){
      const exprs = Object.keys(D.expressions), sps = Object.keys(D.special_poses);
      let h = '<table><tr><th>段階</th>' + exprs.map(e=>`<th>${D.expressions[e]}</th>`).join('') + sps.map(p=>`<th>${D.special_poses[p]}</th>`).join('') + '</tr>';
      for (const s of D.stages) {
        const isTr = s.role==='transition';
        const variants = [...new Set(pick(all, {stage:s.id}).map(c=>c.variant))];
        for (const v of variants) {
          h += `<tr class="${isTr?'tr':''}"><td class="st">${s.label}${v?'（'+(D.variant_labels[v]||v)+'）':''}<div class="sub">${s.id} / ${D.age_labels[s.age_class]}${isTr?' / 途中':''}${s.facing==='back'?' / 背面':''}</div></td>`;
          for (const e of exprs) {
            const k = isTr?'transition':'sprite';
            const c = pick(all, {stage:s.id, kind:k, expression:e, variant:v, mode:md(k)})[0];
            h += `<td class="cell">${c ? frameHTML(c, ar) : ''}</td>`;
          }
          for (const p of sps) {
            const c = pick(all, {stage:s.id, kind:'special', pose:p, variant:v})[0];
            h += `<td class="cell">${c ? frameHTML(c, AR[c.orientation]||ar) : ''}</td>`;
          }
          h += '</tr>';
        }
      }
      const os = cellsOf(ch, 'seed').filter(c=>c.kind==='oneshot');
      if (os.length && (m==='seed' || m==='mixed')) {
        h += `<tr><td class="st">一枚絵</td><td class="cell" colspan="${exprs.length+sps.length}" style="text-align:left"><div style="display:flex;gap:8px;flex-wrap:wrap">` +
          os.map(c => `<div class="cell" style="width:160px">${frameHTML(c, AR[c.orientation]||ar).replace('class="frame"','class="frame" style="width:160px"')}<div class="sub">${c.label}${c.variant?'（'+D.variant_labels[c.variant]+'）':''}</div></div>`).join('') + '</div></td></tr>';
      }
      $('.tbl').innerHTML = h + '</table>';
    }
    renderTable();
  }
  if (methods.length) render(methods[0]);
}
document.querySelectorAll('section[data-char]').forEach(setup);
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-dir", required=True)
    ap.add_argument("--title")
    ap.add_argument("--out", default="index.html")
    a = ap.parse_args()
    project = Path(a.project_dir)
    data = json.loads((project / "cells.json").read_text(encoding="utf-8"))
    spec = json.loads(Path(data["spec"]).read_text(encoding="utf-8")) if Path(data.get("spec", "")).is_file() else {}
    cells, found = [], 0
    for c in data["cells"]:
        c = dict(c)
        img = cell_image(c)
        c["src"] = rel(img, project) if img else None
        found += bool(img)
        c["orientation"] = "portrait"
        for st in spec.get("special_poses", {}).items():
            if c["kind"] == "special" and c["pose"] == st[0]:
                c["orientation"] = st[1].get("orientation", spec.get("defaults", {}).get("orientation", "portrait"))
        for os_ in data.get("oneshots", []):
            if c.get("oneshot") == os_["id"]:
                c["orientation"] = os_.get("orientation", "portrait")
                c["label"] = os_.get("label", os_["id"])
        cells.append(c)
    payload = {
        "stages": data["stages"], "expressions": data["expressions"], "special_poses": data["special_poses"],
        "events": data["events"], "age_labels": data["age_labels"], "cells": cells,
        "orientation": spec.get("defaults", {}).get("orientation", "portrait"),
        "method_labels": METHOD_LABEL, "variant_labels": VARIANT_LABEL,
        "method_by_kind": data.get("method_by_kind"),
    }
    chars = list(dict.fromkeys(c["character"] for c in cells))
    title = a.title or f"{data['project']} 素材プレビュー"
    sections = "".join(
        f'<section data-char="{html.escape(ch)}"><h2>{html.escape(ch)}</h2><div class="tabs"></div><div class="body"></div></section>'
        for ch in chars)
    page = f"""<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title><style>{CSS}</style></head><body><main>
<h1>{html.escape(title)}</h1><p class="lead">ゲーム: {html.escape(data.get('game', ''))} / 素材 {found}/{len(cells)} 枚。
破線枠は未生成（「ユーザー生成枠」はユーザーがスクリプトで生成する枠）。年齢区分は制作上の自主区分で、正式なレーティングではありません。</p>
{sections}</main><script type="application/json" id="data">{json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")}</script>
<script>{JS}</script></body></html>"""
    out = project / a.out
    out.write_text(page, encoding="utf-8")
    print(json.dumps({"index": str(out), "images_found": found, "cells": len(cells)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
