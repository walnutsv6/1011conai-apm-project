# Spec and assets.json

## Spec keys (spec.json)

The spec is a `novelai-strip-sequence` spec plus game keys. Everything strip-sequence documents in `../novelai-strip-sequence/references/prompt-assembly.md` (prompt order, negatives, overrides, `defaults`) applies; this file lists only what is added or different.

```jsonc
{
  "project": "meru-yakyuken", "theme": "yakyuken",     // theme -> user-run-scripts/<character>-<theme>[-inpaint]/
  "game": "yakyuken",                                   // preset id (preview label)
  "methods": ["seed", "inpaint"],                       // pilot: both; afterwards the chosen one, or ["mixed"]
  "method_by_kind": {"sprite": "inpaint", "transition": "seed",   // only with "mixed": the method per cell kind
                     "special": "seed", "oneshot": "seed"},       // (this is the default; special/oneshot must be seed)
  "defaults": {
    "...strip-sequence defaults...",
    "modes": ["transparent"],                           // seed-method sprite modes (bg needs a private scene)
    "exposed_expression": "blush",                      // keeps expressions readable from topless on
    "plate_background": "simple background, grey background",   // inpaint plates
    "inpaint_strength": 1.0, "face_inpaint_strength": 0.85,
    "mask_regions": {"skirt": [0.45, 0.80, -0.08, 1.08]}         // optional extra/override mask boxes
  },
  "poses": { "stand": {...}, "undress": {"tags": "standing, hands on clothes, undressing", "expression": ""} },
  "expressions": { "<id>": {"label": "通常", "tags": "gentle smile, blush"} },
  "expression_set": ["normal", "win", "lose", "shy"],   // must include normal
  "transition_expression": "shy",
  "special_poses": { "<id>": {"label", "tags", "expression", "stages": "all"|"to_underwear"|[ids], "composition"?, "orientation"?,
                     "stage_overrides"?: {"topless": {"facing": "front", "append_tags": "covering breasts with one arm"}}} },
  "stages": [
    { "id": "dressed", "label": "着衣", "class": "clothed", "role": "main" },
    { "id": "cardi_tr", "label": "カーディガンを脱ぐ途中", "class": "partial", "role": "transition",
      "pose": "undress", "inpaint_regions": ["upper"], "duration_ms": 450 },
    { "id": "bra_tr", "...": "...", "facing": "back" },          // front (default) | back
    { "id": "nude", "class": "nude", "role": "main", "crotch": "both", "revealing"?: false, "fluids"?: false }
  ],
  "events": { "<id>": {"label", "advance": 0|1, "expression"?, "special"?: [pose ids], "random_special"?, "fallback_expression"?} },
  "oneshots": [
    {"id": "icon", "kind": "icon", "from": {"stage": "dressed", "expression": "normal"}},
    {"id": "title", "kind": "title", "class": "clothed", "orientation": "landscape", "pose_tags": "...", "expression": "normal", "scene"?: "..."},
    {"id": "reward", "kind": "reward", "class": "nude", "crotch": "both", "pose_tags": "...", "expression": "shy"}
  ],
  "characters": { "<name>": {
    "...strip-sequence character keys (seed, appearance with bangs, expression, scene, scene_private, body, negative, stages, overrides)...",
    "oneshots": { "title": "outfit tags", "reward": "nude, ... (kept-on items)" }
  } }
}
```

Rules checked by `build_game_requests.py` (besides strip-sequence's `validate()`):

- First and last stages are `main`; `role` is `main` or `transition`; `facing` is `front` or `back` (`ask` in a preset means "ask the user" and fails until resolved).
- `expression_set` includes `normal`; every id exists in `expressions`; `transition_expression` exists.
- `stage.pose` names an entry in `poses`; special-pose scopes name main stages.
- One-shots other than `icon` need a class, a crotch choice for nude/bottomless, `characters.<c>.oneshots.<id>`, and a private scene for underwear and beyond.
- Character `expression` is placed before the outfit tags in every prompt; keep it empty or neutral so it does not fight the expression axis.

## cells.json

Written by `build_game_requests.py`; read by `make_masks.py`, `remove_bg.py --cells`, `build_preview.py`, `export_assets.py`. One entry per expected image: `character, method, kind (sprite|transition|special|oneshot), stage, role, class, age_class, expression, pose, mode, variant, facing, basename, seed, script_only, request, image, cutout? (inpaint), parent?, mask?, mask_group?, oneshot?`. Rebuilding one method of one character replaces only those cells. With `mixed`, each cell keeps its real `method` and only the kinds `method_by_kind` assigns to it are built; the top-level `method_by_kind` tells the preview and `export_assets.py --method mixed` how to combine them. `basename` never carries the `-vN` revision suffix; readers pick the newest take (`scripts/common.py`).

## assets.json (export)

```jsonc
{
  "schema": "strip-game-assets/1", "project", "game", "method", "max_age",
  "rating_note": "age_class は制作上の自主規制区分であり、正式なレーティングではない…",
  "age_labels": {"all": "全年齢", "12rec": "12歳以上推奨", "15rec": "15歳以上推奨", "15": "15歳未満禁止", "18": "18歳未満禁止"},
  "expressions": {"normal": "通常", ...}, "transition_expression": "shy",
  "special_poses": {"rock": "グー", ...},
  "events": {...as in the spec...},
  "characters": { "meru": {
    "stages": [ { "id": "dressed", "label": "着衣", "class": "clothed", "age_class": "all", "facing": "front",
                  "sprites": {"normal": "meru/....png", "win": "meru/....png"},     // nude: {"covered": f, "open": f}
                  "special": {"rock": "meru/....png"},
                  "fallback_expression": "normal" } ],
    "transitions": [ { "from": "dressed", "to": "cardioff",
                       "frames": [ {"stage": "cardi_tr", "label": "...", "file": "meru/....png", "variant": "", "duration_ms": 450} ] } ],
    "cap_stage": "lingerie",          // last main stage in this edition; the game ends / shows the reward here
    "oneshots": { "icon": "meru/meru-icon.png", "title": "meru/....png", "reward": {"covered": f, "open": f} },
    "missing": ["basename", ...]      // expected but not generated; use fallback_expression
  } }
}
```

Stages above `--max-age` are left out together with every transition whose destination is left out and every one-shot above the cap. The game should treat an `advance` event at `cap_stage` as "cleared".
