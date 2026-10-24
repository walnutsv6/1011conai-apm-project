#!/usr/bin/env python3
"""Build novelai-imagegen request files for strip-game assets (sprites x expressions, transitions,
special poses, one-shot CGs) on top of novelai-strip-sequence.

Usage:
  python build_game_requests.py --spec spec.json --project-dir output/novelai-imagegen/<project>
         [--user-run-dir user-run-scripts] [--method seed|inpaint|mixed] [--only meru] [--stage s1,s2]
         [--suffix v2] [--refresh-unrun]

Prompts are assembled by novelai-strip-sequence/scripts/build_requests.py (validate() and build()),
so the adult-tag guards, the private-scene check and the class -> rating-tag rules are the same.
This script only adds the game axes and writes:
  <project>/requests/<method>/*.request.json + order.txt     (clothed / partial / underwear; agent)
  <user-run-dir>/<character>-<theme>[-inpaint]/requests/ + order.txt + run.ps1 / run.sh
                                                               (topless / bottomless / nude; user only)
  <project>/cells.json   every expected cell (read by make_masks / build_preview / export_assets)
  <project>/prompts-<method>.md
Existing request files are never overwritten (use --suffix v2 for a revision).

Methods:
  seed     regenerate every cell with the character's fixed seed (transparent mode = straight alpha).
  inpaint  generate one base plate (first main stage, simple grey background), then repaint only the
           masked region for each later stage / expression. NovelAI inpainting cannot output
           transparency, so every plate image is cut out afterwards with remove_bg.py.
  mixed    each cell kind from the method named in spec.method_by_kind (default: sprites = inpaint;
           transitions, special poses and one-shots = seed). Only those cells are built; cells.json
           keeps their real method, and the preview / export combine them as "mixed".
"""
import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path

SKILLS_ROOT = Path(__file__).resolve().parents[2]
for _dep in ("novelai-strip-sequence/scripts/build_requests.py", "novelai-imagegen/scripts/novelai_image.py",
             "novelai-imagegen/references/sexual_content_guidelines.md"):
    if not (SKILLS_ROOT / _dep).is_file():  # novelai-gameassets depends on the novelai package
        sys.exit(f"error: {SKILLS_ROOT / _dep} not found; install the novelai package "
                 "(novelai-imagegen, novelai-strip-sequence) into the same skills directory")
sys.path.insert(0, str(SKILLS_ROOT / "novelai-strip-sequence" / "scripts"))
import build_requests as sb  # noqa: E402  (strip-sequence prompt assembly is reused, not copied)
from common import latest  # noqa: E402

AGE_ORDER = ["all", "12rec", "15rec", "15", "18"]
AGE_LABEL = {"all": "全年齢", "12rec": "12歳以上推奨", "15rec": "15歳以上推奨", "15": "15歳未満禁止",
             "18": "18歳未満禁止"}
CLASS_AGE = {"clothed": "all", "partial": "all", "underwear": "15rec", "topless": "15",
             "bottomless": "18", "nude": "18"}
BACK_TAGS = "from behind, looking back, back turned"
DEFAULT_PLATE = "simple background, grey background"
DEFAULT_REGIONS = ["upper"]
DEFAULT_MIX = {"sprite": "inpaint", "transition": "seed", "special": "seed", "oneshot": "seed"}


def die(msg):
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(2)


def age_class(stage):
    age = CLASS_AGE[stage["class"]]
    if stage.get("revealing") and age == "all":
        age = "12rec"
    if stage.get("fluids"):
        age = "18"
    return age


def to_strip_spec(spec):
    """Game spec -> strip-sequence spec (special poses become ordinary poses)."""
    s = deepcopy(spec)
    for pid, sp in spec.get("special_poses", {}).items():
        if pid in s["poses"]:
            die(f"special pose id '{pid}' clashes with an entry in poses")
        s["poses"][pid] = {"tags": sp["tags"], "expression": sp.get("expression", "")}
    for os_ in spec.get("oneshots", []):
        if os_.get("pose_tags"):
            s["poses"][f"os_{os_['id']}"] = {"tags": os_["pose_tags"], "expression": ""}
    # stage.pose is honoured per stage by this script; strip-sequence only needs it under per_stage
    s["stages"] = [{k: v for k, v in st.items() if k != "pose" or s["defaults"].get("pose_mode") == "per_stage"}
                   for st in spec["stages"]]
    return s


def validate(spec):
    d = spec["defaults"]
    stages = spec["stages"]
    mains = [s for s in stages if s.get("role", "main") == "main"]
    if not mains or stages[0].get("role", "main") != "main" or stages[-1].get("role", "main") != "main":
        die("the first and last stages must be main stages (role: transition only goes between two mains)")
    for st in stages:
        if st.get("role", "main") not in ("main", "transition"):
            die(f"stage '{st['id']}': role must be main or transition")
        if st.get("pose") and st["pose"] not in spec["poses"]:
            die(f"stage '{st['id']}': pose '{st['pose']}' is not in poses")
        if st.get("facing", "front") not in ("front", "back"):
            die(f"stage '{st['id']}': facing must be front or back (ask the user; 'ask' is unresolved)")
    exprs = spec["expressions"]
    for e in spec["expression_set"]:
        if e not in exprs:
            die(f"expression_set names '{e}', which is not in expressions")
    if spec.get("transition_expression") not in exprs:
        die("transition_expression must name an entry in expressions")
    if "normal" not in spec["expression_set"]:
        die("expression_set must include 'normal' (inpaint parents and fallbacks use it)")
    main_ids = [s["id"] for s in mains]
    for pid, sp in spec.get("special_poses", {}).items():
        scope = sp.get("stages", "all")
        if isinstance(scope, list) and any(x not in main_ids for x in scope):
            die(f"special pose '{pid}': stages must name main stages")
        if not isinstance(scope, list) and scope not in ("all", "to_underwear"):
            die(f"special pose '{pid}': stages must be all, to_underwear, or a list of main stage ids")
        for sid, so in sp.get("stage_overrides", {}).items():
            if sid not in main_ids or so.get("facing", "front") not in ("front", "back"):
                die(f"special pose '{pid}': stage_overrides.{sid} must name a main stage; facing front/back")
    for os_ in spec.get("oneshots", []):
        if os_["kind"] == "icon":
            continue
        if os_.get("class") not in sb.CLASSES:
            die(f"oneshot '{os_['id']}': class must be one of {sb.CLASSES}")
        if os_["class"] in sb.CROTCH_CLASSES and os_.get("crotch") not in ("covered", "open", "both"):
            die(f"oneshot '{os_['id']}': set crotch to covered / open / both (ask the user)")
        for cname, ch in spec["characters"].items():
            if os_["id"] not in ch.get("oneshots", {}):
                die(f"{cname}: missing characters.{cname}.oneshots.{os_['id']} (outfit + pose tags)")
            if os_["class"] in sb.PRIVATE_REQUIRED and not ch.get("scene_private"):
                die(f"{cname}: oneshot '{os_['id']}' ({os_['class']}) needs a private scene (scene_private: true)")
    for m in spec.get("methods", ["seed"]):
        if m not in ("seed", "inpaint", "mixed"):
            die(f"methods: '{m}' must be seed, inpaint or mixed")
    for k, m in spec.get("method_by_kind", {}).items():
        if k not in DEFAULT_MIX or m not in ("seed", "inpaint"):
            die(f"method_by_kind.{k}: kinds are {list(DEFAULT_MIX)}, methods seed / inpaint")
        if k in ("special", "oneshot") and m != "seed":
            die(f"method_by_kind.{k}: special poses and one-shots are seed-method only")
    sb.validate(to_strip_spec(spec))
    if d.get("exposed_expression") is None:
        print("warning: defaults.exposed_expression is unset; strip-sequence adds 'embarrassed, shy, blush' "
              "to every expression from topless onward (presets use 'blush')", file=sys.stderr)


def special_scope(spec, sp):
    mains = [s for s in spec["stages"] if s.get("role", "main") == "main"]
    scope = sp.get("stages", "all")
    if scope == "all":
        return [s["id"] for s in mains]
    if scope == "to_underwear":
        return [s["id"] for s in mains if s["class"] in ("clothed", "partial", "underwear")]
    return scope


class Builder:
    def __init__(self, spec, args):
        self.spec, self.args = spec, args
        self.sspec = to_strip_spec(spec)
        self.cwd = Path.cwd()
        self.project = Path(args.project_dir)
        self.images = sb.rel(self.project / "images", self.cwd)
        self.theme = sb.slug(spec.get("theme", "game")) or "game"
        self.cells, self.mds = [], {}  # mds: method -> prompt lines
        self.written = self.skipped = 0
        self.orders = {}  # target dir -> [request file names in run order]
        self.order_char = {}  # target dir -> character
        self.kinds = None  # mixed: cell kinds the current method builds

    # -- one request -------------------------------------------------------------------------------
    def make(self, cname, char, stage, variant, mode, *, expr=None, pose=None, composition=None,
             orientation=None, scene=None, extra_append=""):
        d = self.sspec["defaults"]
        s = self.sspec
        st = dict(stage)
        if pose:
            s = {**self.sspec, "defaults": {**d, "pose_mode": "per_stage"}}
            st["pose"] = pose
        ovs = []
        if expr:
            ovs.append({"match": {}, "replace_pose_expression": self.spec["expressions"][expr]["tags"]})
        append = sb.join(BACK_TAGS if stage.get("facing") == "back" else "", extra_append)
        if append:
            ovs.append({"match": {}, "append_stage": append})
        if composition:
            ovs.append({"match": {}, "replace_composition": composition})
        ch = {**char, "overrides": ovs + list(char.get("overrides", []))}
        build_mode = mode
        if mode == "plate":
            ch["scene"] = d.get("plate_background", DEFAULT_PLATE)
            build_mode = "bg"
        suffix = "-".join(x for x in (expr, self.args.suffix) if x)
        stem, base, pose_id, req = sb.build(s, cname, ch, st, variant, build_mode, d.get("rating", "sensitive"), suffix)
        if mode == "plate":
            stem = stem.replace(f"-{pose_id}-bg", f"-{pose_id}-plate", 1)
            base = base.replace(f"-{pose_id}-bg", f"-{pose_id}-plate", 1)
            req["output"]["basename"] = base
        if orientation:
            req["orientation"] = orientation
        return base, pose_id, req

    def png(self, cname, base, seed):
        return f"{self.images}/{cname}/{base}-seed{seed}.png"

    def plain(self, base):
        """Basename without the revision suffix (cells.json names cells, not takes)."""
        sfx = f"-{self.args.suffix}" if self.args.suffix else ""
        return base[: -len(sfx)] if sfx and base.endswith(sfx) else base

    def parent_png(self, cname, base, seed, stage_id):
        """Inpaint parent: the take built in this run when that stage is rebuilt with a suffix,
        otherwise the newest existing take (-vN), otherwise the plain expected name."""
        rebuilt = self.args.suffix and (not self.only_stage or stage_id in self.only_stage)
        if rebuilt:
            return self.png(cname, base, seed)
        found = latest(self.project / "images" / cname, self.plain(base))
        return sb.rel(found, self.cwd) if found else self.png(cname, self.plain(base), seed)

    def emit(self, cname, method, req, base, cell):
        if self.kinds is not None and cell["kind"] not in self.kinds:
            return
        script_only = cell["class"] in sb.SCRIPT_ONLY
        if script_only:
            name = f"{cname}-{self.theme}" + ("-inpaint" if method == "inpaint" else "")
            target = Path(self.args.user_run_dir) / name / "requests"
        else:
            target = self.project / "requests" / method
        path = target / f"{base}.request.json"
        selected = not self.only_stage or cell["stage"] in self.only_stage
        if selected:
            target.mkdir(parents=True, exist_ok=True)
            # this take only: with a suffix, an older take of the plain name does not count as run
            unrun = latest(self.project / "images" / cname, base) is None
            if path.exists() and not (self.args.refresh_unrun and unrun):
                self.skipped += 1
            else:
                path.write_text(json.dumps(req, ensure_ascii=False, indent=2), encoding="utf-8")
                self.written += 1
            self.orders.setdefault(target, [])
            self.order_char[target] = cname
            if path.name not in self.orders[target]:
                self.orders[target].append(path.name)
        base = self.plain(base)
        cell.update(character=cname, method=method, basename=base, seed=req["seed"], script_only=script_only,
                    request=sb.rel(path, self.cwd), image=self.png(cname, base, req["seed"]),
                    age_class=cell.get("age_class") or "all")
        if method == "inpaint":
            cell["cutout"] = f"{self.images}/{cname}/cutout/{base}-seed{req['seed']}.png"
        self.cells.append(cell)
        tag = " ※ユーザー実行" if script_only else ""
        extra = ""
        if req.get("inpaint"):
            extra = f"inpaint: parent `{req['inpaint']['image']}` / mask `{req['inpaint']['mask']}`\n\n"
        self.mds.setdefault(method, []).extend([
            f"### {req['output']['basename']}{tag}", "",
            f"{cell['kind']} / class `{cell['class']}` / expression `{cell.get('expression') or '-'}` / "
            f"variant `{cell.get('variant') or '-'}`", "",
            extra + "```", req["prompt"], "```", "", f"negative: `{req['negative_prompt']}`", ""])

    # -- method: seed ------------------------------------------------------------------------------
    def seed_method(self, cname, char):
        spec, d = self.spec, self.spec["defaults"]
        modes = d.get("modes", ["transparent"])
        for stage in spec["stages"]:
            role = stage.get("role", "main")
            exprs = spec["expression_set"] if role == "main" else [spec["transition_expression"]]
            for variant in sb.cells(stage):
                for mode in modes:
                    for e in exprs:
                        base, pose_id, req = self.make(cname, char, stage, variant, mode, expr=e, pose=stage.get("pose"))
                        self.emit(cname, "seed", req, base, self.cell(stage, "sprite" if role == "main" else "transition",
                                                                       e, pose_id, mode, variant))
        for pid, sp in spec.get("special_poses", {}).items():
            scope = special_scope(spec, sp)
            for stage in spec["stages"]:
                if stage["id"] not in scope:
                    continue
                so = sp.get("stage_overrides", {}).get(stage["id"], {})
                stage = {**stage, **({"facing": so["facing"]} if "facing" in so else {})}
                for variant in sb.cells(stage):
                    for mode in modes:
                        base, pose_id, req = self.make(cname, char, stage, variant, mode, pose=pid,
                                                       composition=sp.get("composition"),
                                                       orientation=sp.get("orientation"),
                                                       extra_append=so.get("append_tags", ""))
                        self.emit(cname, "seed", req, base, self.cell(stage, "special", None, pid, mode, variant))
        for os_ in spec.get("oneshots", []):
            if os_["kind"] == "icon":
                continue
            stage = {"id": f"os_{os_['id']}", "label": os_.get("label", os_["id"]), "class": os_["class"],
                     "crotch": os_.get("crotch"), "rating": os_.get("rating"), "fluids": os_.get("fluids"),
                     "negative": os_.get("negative", "")}
            stage = {k: v for k, v in stage.items() if v is not None}
            ch = {**char, "stages": {**char["stages"], stage["id"]: char["oneshots"][os_["id"]]}}
            if os_.get("scene"):
                ch["scene"] = os_["scene"]
            for variant in sb.cells(stage):
                base, pose_id, req = self.make(cname, ch, stage, variant, os_.get("mode", "bg"),
                                               expr=os_.get("expression"), composition=os_.get("composition"),
                                               pose=f"os_{os_['id']}" if os_.get("pose_tags") else None,
                                               orientation=os_.get("orientation"))
                c = self.cell(stage, "oneshot", os_.get("expression"), pose_id, os_.get("mode", "bg"), variant)
                c["oneshot"] = os_["id"]
                self.emit(cname, "seed", req, base, c)

    # -- method: inpaint ---------------------------------------------------------------------------
    def inpaint_method(self, cname, char):
        """Chain: each main stage repaints the previous main stage's normal plate; expressions repaint
        the face of their own stage's normal plate; transitions branch off the previous main stage.
        A stage whose facing differs from its parent cannot be inpainted (the whole body turns), so it
        starts a new base plate (plain generation). Masks are made per base plate: the mask group is
        the id of the stage whose plate started the chain."""
        spec, d = self.spec, self.spec["defaults"]
        strength = d.get("inpaint_strength", 1.0)
        face_strength = d.get("face_inpaint_strength", 0.85)
        masks = f"{sb.rel(self.project / 'masks', self.cwd)}/{cname}"
        prev_main = None  # (base, seed, facing, group, stage id) of the previous main stage's normal plate

        def parent_for(stage):
            facing = stage.get("facing", "front")
            if prev_main is None or prev_main[2] != facing:
                return None
            return prev_main

        for stage in spec["stages"]:
            role = stage.get("role", "main")
            facing = stage.get("facing", "front")
            regions = stage.get("inpaint_regions", DEFAULT_REGIONS)
            first_normal = None
            for variant in sb.cells(stage):
                parent = parent_for(stage)
                if role == "main":
                    expr = "normal"
                    reg = regions
                else:
                    expr = spec["transition_expression"]
                    reg = regions if "face" in regions else regions + ["face"]
                base, pose_id, req = self.make(cname, char, stage, variant, "plate", expr=expr, pose=stage.get("pose"))
                group = parent[3] if parent else stage["id"]
                mask = f"{group}/{'+'.join(reg)}" if parent else None
                ppng = self.parent_png(cname, parent[0], parent[1], parent[4]) if parent else None
                if parent:
                    self.to_inpaint(req, ppng, f"{masks}/{mask}.png", strength)
                cell = self.cell(stage, "sprite" if role == "main" else "transition", expr, pose_id, "plate", variant)
                cell.update(parent=ppng, mask=mask,
                            mask_group=group)
                self.emit(cname, "inpaint", req, base, cell)
                if role != "main":
                    continue
                normal = (base, req["seed"], facing, group, stage["id"])
                first_normal = first_normal or normal
                for e in spec["expression_set"]:
                    if e == "normal":
                        continue
                    b2, _, r2 = self.make(cname, char, stage, variant, "plate", expr=e, pose=stage.get("pose"))
                    fpng = self.parent_png(cname, base, req["seed"], stage["id"])
                    self.to_inpaint(r2, fpng, f"{masks}/{group}/face.png", face_strength)
                    c2 = self.cell(stage, "sprite", e, pose_id, "plate", variant)
                    c2.update(parent=fpng, mask=f"{group}/face", mask_group=group)
                    self.emit(cname, "inpaint", r2, b2, c2)
            if role == "main":
                prev_main = first_normal

    @staticmethod
    def to_inpaint(req, image, mask, strength):
        req["operation"] = "edit"
        req["inpaint"] = {"image": image, "mask": mask, "strength": strength}

    def cell(self, stage, kind, expr, pose, mode, variant):
        return {"kind": kind, "stage": stage["id"], "label": stage.get("label", stage["id"]),
                "role": stage.get("role", "main"), "class": stage["class"], "age_class": age_class(stage),
                "expression": expr, "pose": pose, "mode": mode, "variant": variant,
                "facing": stage.get("facing", "front")}

    # -- run scripts -------------------------------------------------------------------------------
    def write_orders(self):
        runner = sb.rel(SKILLS_ROOT / "novelai-imagegen" / "scripts" / "novelai_image.py", self.cwd)
        has = sb.rel(SKILLS_ROOT / "novelai-strip-sequence" / "scripts" / "has_output.py", self.cwd)
        rembg = sb.rel(Path(__file__).resolve().parent / "remove_bg.py", self.cwd)
        mk = sb.rel(Path(__file__).resolve().parent / "make_masks.py", self.cwd)
        user_root = Path(self.args.user_run_dir).resolve()
        for target, names in self.orders.items():
            order = target / "order.txt"
            # a partial build (--stage) adds to the run order; a full build rewrites it
            old = order.read_text(encoding="utf-8").split() if order.exists() and self.only_stage else []
            merged = old + [n for n in names if n not in old]
            order.write_text("\n".join(merged) + "\n", encoding="utf-8", newline="\n")  # LF: run.sh reads it
            udir = target.parent
            if user_root not in udir.resolve().parents and udir.resolve() != user_root:
                continue
            inpaint = udir.name.endswith("-inpaint")
            kw = dict(title=udir.name, up=sb.rel(self.cwd, udir), runner=runner, has=has, rembg=rembg, mk=mk,
                      images=self.images, post="1" if inpaint else "0", char=self.order_char[target],
                      proj=sb.rel(self.project, self.cwd))
            for name, tpl in (("run.ps1", PS1), ("run.sh", SH)):
                sp = udir / name
                if not sp.exists():
                    sp.write_text(tpl.format(self_rel=sp.as_posix(), **kw), encoding="utf-8", newline="\n")

    def run(self):
        args, spec = self.args, self.spec
        only = set(args.only.split(",")) if args.only else None
        self.only_stage = set(args.stage.split(",")) if args.stage else None
        methods = [args.method] if args.method else spec.get("methods", ["seed"])
        mix = {**DEFAULT_MIX, **spec.get("method_by_kind", {})}
        runs = []  # (method, kinds or None)
        for method in methods:
            if method == "mixed":
                runs += [(m, {k for k, v in mix.items() if v == m}) for m in ("inpaint", "seed")]
            else:
                runs.append((method, None))
        for cname, char in spec["characters"].items():
            if only and cname not in only:
                continue
            for method, kinds in runs:
                self.kinds = kinds
                if kinds == set():
                    continue
                self.mds.setdefault(method, []).extend([f"## {cname} (seed `{char['seed']}`)", ""])
                (self.seed_method if method == "seed" else self.inpaint_method)(cname, char)
            self.kinds = None
        self.write_orders()
        cells_path = self.project / "cells.json"
        old = json.loads(cells_path.read_text(encoding="utf-8"))["cells"] if cells_path.exists() else []
        keys = {(c["character"], c["method"]) for c in self.cells}
        kept = [c for c in old if (c["character"], c["method"]) not in keys]
        masks_needed = sorted({c["mask"] for c in self.cells + kept if c.get("mask")})
        cells_path.write_text(json.dumps({
            "project": spec.get("project", self.project.name), "theme": spec.get("theme", ""),
            "game": spec.get("game", "generic"), "spec": sb.rel(Path(args.spec), self.cwd),
            "stages": [{"id": s["id"], "label": s.get("label", s["id"]), "role": s.get("role", "main"),
                        "class": s["class"], "age_class": age_class(s), "facing": s.get("facing", "front"),
                        "duration_ms": s.get("duration_ms", 450)} for s in spec["stages"]],
            "expressions": {k: v["label"] for k, v in spec["expressions"].items() if k in spec["expression_set"]},
            "transition_expression": spec["transition_expression"],
            "special_poses": {k: v["label"] for k, v in spec.get("special_poses", {}).items()},
            "events": spec.get("events", {}), "oneshots": spec.get("oneshots", []),
            "age_labels": AGE_LABEL, "masks_needed": masks_needed,
            "method_by_kind": mix if "mixed" in methods + spec.get("methods", []) else None,
            "cells": kept + self.cells}, ensure_ascii=False, indent=2), encoding="utf-8")
        for method, lines in self.mds.items():  # one file per method, so rebuilding one keeps the other
            (self.project / f"prompts-{method}.md").write_text(f"# Prompts ({method})\n\n" + "\n".join(lines),
                                                                 encoding="utf-8")
        print(json.dumps({"written": self.written, "skipped_existing": self.skipped, "cells": len(self.cells),
                          "script_only_cells": sum(c["script_only"] for c in self.cells),
                          "agent_cells": sum(not c["script_only"] for c in self.cells),
                          "masks_needed": masks_needed,
                          "order_files": [sb.rel(t / "order.txt", self.cwd) for t in self.orders]},
                         ensure_ascii=False, indent=1))


PS1 = r"""# User-run batch for {title}. The agent does NOT run this script.
# 1) Set the key for this session only (never save it in a file):
#      $env:NOVELAI_API_KEY = "<your NovelAI API key>"
# 2) Run from anywhere:
#      powershell -ExecutionPolicy Bypass -File "{self_rel}"
# Requests run in the order of requests/order.txt (inpaint children need their parent image first).
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = (Resolve-Path (Join-Path $here '{up}')).Path
Set-Location $root
if (-not $env:NOVELAI_API_KEY) {{ Write-Error 'NOVELAI_API_KEY is not set.'; exit 1 }}
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {{ Write-Error 'uv is not installed.'; exit 1 }}
$runner = '{runner}'
$has = '{has}'
$rembg = '{rembg}'
$mk = '{mk}'
$proj = '{proj}'
$char = '{char}'
$out = '{images}'
$post = {post}
uv run $runner validate
if ($LASTEXITCODE -ne 0) {{ exit $LASTEXITCODE }}
foreach ($name in Get-Content (Join-Path $here 'requests/order.txt')) {{
  if (-not $name.Trim()) {{ continue }}
  $f = Join-Path $here "requests/$name"
  Write-Host "== $name"
  if ($post -eq 1) {{ python $mk --project-dir $proj --character $char | Out-Null }}  # masks of new base plates
  python $has --request $f --out-dir $out
  if ($LASTEXITCODE -ne 0) {{
    uv run $runner estimate --request $f
    if ($LASTEXITCODE -ne 0) {{ Write-Warning "estimate failed; skipping $name"; continue }}
    uv run $runner generate --request $f --out-dir $out
    if ($LASTEXITCODE -ne 0) {{ Write-Warning "generate skipped or failed for $name"; continue }}
  }} else {{ Write-Host 'already generated; skipping' }}
  if ($post -eq 1) {{ uv run $rembg --request $f --images $out }}
}}
"""

SH = r"""#!/usr/bin/env bash
# User-run batch for {title}. The agent does NOT run this script.
# export NOVELAI_API_KEY="<your NovelAI API key>"   # this shell only, never save it in a file
# Requests run in the order of requests/order.txt (inpaint children need their parent image first).
set -u
here="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd)"
cd "$here/{up}"
[ -n "${{NOVELAI_API_KEY:-}}" ] || {{ echo "NOVELAI_API_KEY is not set." >&2; exit 1; }}
command -v uv >/dev/null || {{ echo "uv is not installed." >&2; exit 1; }}
runner='{runner}'
has='{has}'
rembg='{rembg}'
mk='{mk}'
proj='{proj}'
char='{char}'
out='{images}'
post={post}
uv run "$runner" validate || exit $?
while read -r name; do
  name="${{name%$'\r'}}"
  [ -n "$name" ] || continue
  f="$here/requests/$name"
  echo "== $name"
  [ "$post" = 1 ] && python "$mk" --project-dir "$proj" --character "$char" >/dev/null  # masks of new base plates
  if python "$has" --request "$f" --out-dir "$out"; then
    echo "already generated; skipping"
  else
    uv run "$runner" estimate --request "$f" || {{ echo "estimate failed; skipping" >&2; continue; }}
    uv run "$runner" generate --request "$f" --out-dir "$out" || {{ echo "generate skipped or failed" >&2; continue; }}
  fi
  [ "$post" = 1 ] && uv run "$rembg" --request "$f" --images "$out"
done < "$here/requests/order.txt"
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", required=True)
    ap.add_argument("--project-dir", required=True)
    ap.add_argument("--user-run-dir", default="user-run-scripts")
    ap.add_argument("--method", choices=["seed", "inpaint", "mixed"],
                    help="build one method only (default: spec.methods)")
    ap.add_argument("--only", help="comma-separated character names")
    ap.add_argument("--stage", help="comma-separated stage ids (request files only; cells.json stays complete)")
    ap.add_argument("--suffix", default="", help="revision suffix, e.g. v2")
    ap.add_argument("--refresh-unrun", action="store_true",
                    help="rewrite existing request files whose image does not exist yet (e.g. after a parent take "
                         "was revised); requests that already produced an image are never touched")
    args = ap.parse_args()
    spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
    validate(spec)
    Builder(spec, args).run()


if __name__ == "__main__":
    sys.exit(main())
