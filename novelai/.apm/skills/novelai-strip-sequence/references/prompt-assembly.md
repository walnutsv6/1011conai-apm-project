# Prompt assembly (strip sequence)

## Positive order

```
[background] , 1girl, solo, mature female, adult woman, 20s, tall ,
[appearance] , [base expression] , [stage outfit tags] , cowboy shot ,
[pose tags] , [covered tags] , [pose expression] , looking at viewer ,
[body] , anime style, detailed, vivid colors , [rating tags]
```

- `[background]` is the character's private `scene` in `bg` mode and exactly `transparent background, simple background, no background` in `transparent` mode. Nothing else differs between the two modes.
- `[appearance]` always has hair colour/length/style **and a bangs tag**.
- `[stage outfit tags]` come from `characters.<name>.stages.<stage id>` (override: `replace_stage`, `append_stage`).
- `[covered tags]` (`defaults.covered_tags`, default `covering crotch`) are added only to the `covered` variant of nude/bottomless stages. The `open` variant adds nothing there.
- `[rating tags]` are last and appear once:
  - `clothed` / `partial` / `underwear`: `rating:<stage.rating or defaults.rating>`
  - `topless`, `nude`: `rating:explicit, nipples`
  - `bottomless` (breasts covered): `rating:explicit`
- Keep the order stable. Under a fixed seed, reordering tags changes the whole image.

## Negative order

```
[character negative] , [override negative] , [stage negative] , [class negative] , [mode negative] , [common negative]
```

- Stage negative: tags of garments already removed (and anything that must not appear), e.g. `suit jacket, blazer` for the stage after the jacket comes off. Carry earlier removals forward in later stages.
- Class negative: `defaults.clothed_negative` (`nude, topless, nipples, pussy, pubic hair`) for clothed/partial/underwear; `defaults.exposed_negative` (`uncensored, pussy, pubic hair, genitals, sex, penis, 1boy, cum, bodily fluids`) for topless/bottomless/nude.
- Mode negative (transparent only): `scenery, background, outdoors`.
- Common negative: `full body, wide shot, child, loli, petite, flat chest, multiple girls, bad anatomy, extra fingers, missing fingers, malformed hands, duplicate, text, watermark, logo, signature`.

## Spec keys

```jsonc
{
  "project": "...", "theme": "bedroom-office",          // theme -> user-run-scripts/<character>-<theme>/
  "defaults": {
    "model", "orientation", "steps", "scale", "rating", "require_zero_anlas",
    "modes": ["bg", "transparent"],
    "pose_mode": "fixed" | "per_stage", "fixed_pose": "<pose id>",   // fixed_pose required for fixed
    "base_tags", "composition", "gaze", "style",
    "covered_tags", "clothed_negative", "exposed_negative", "common_negative"
  },
  "poses":  { "<id>": { "tags": "...", "expression": "..." } },
  "stages": [                                            // order = sequence order
    { "id": "jacketoff", "label": "上着を脱ぐ", "class": "partial",
      "pose": "<pose id>",                               // required for per_stage
      "crotch": "covered" | "open" | "both",             // required for bottomless / nude
      "negative": "...", "rating": "sensitive" }
  ],
  "characters": { "<name>": {
    "seed", "appearance", "expression", "scene", "scene_private": true, "body", "negative",
    "stages": { "<stage id>": "outfit tags" },
    "overrides": [ { "match": {"stage", "mode", "variant"}, "append_stage": "...", "note": "slug" } ]
  } }
}
```

`build_requests.py` aborts when: the adult tag or `child` guard is missing, a stage lacks `crotch` / `pose` as required, the first stage is not `clothed` or `underwear`, there is no clothed/partial/underwear stage, a character lacks tags for a stage, or `scene_private` is not true for a set that reaches underwear in `bg` mode.

## Request JSON (per image)

Same fields as `novelai-variations`, plus `output.character` so the runner writes to `<out-dir>/<character>/` and `manifest/<stem>.json`:

```json
{
  "schema_version": 1, "operation": "generate",
  "prompt": "...", "negative_prompt": "...",
  "model": "nai-diffusion-5-full", "orientation": "portrait",
  "seed": 318245, "steps": 28, "scale": 5.0, "samples": 1,
  "cost_policy": {"subscription_plan": "auto", "prefer_zero_anlas": true, "require_zero_anlas": true, "confirm_above_anlas": 100, "confirmed_paid": false},
  "output": {"basename": "mia-skirtoff-stand-bg", "character": "mia", "format": "png"}
}
```

`straight_alpha` and `tag_hint_transparent_background` are added in transparent mode only.

## Choosing stages

Derive the ladder from what the user confirmed about the worn items (layer table) and the desired detail level of the in-between steps; do not invent garments or skip layers they listed.

| Detail level | Stages per garment | Typical `partial` tags |
| --- | --- | --- |
| Coarse | 1 (worn -> removed) | none, just the next state |
| Standard | 1-2 (one half-removed state for main items) | `slipping off shoulders`, `unbuttoned`, `open blouse` |
| Fine | 2-4 (gesture steps) | `hand on button`, `half unbuttoned`, `pulling down strap`, `holding hem`, `unclasping bra` (hands visible; keep it self-directed, no sex acts) |

Items the user said stay on (thighhighs, ribbon, accessories) are repeated in every stage's tags, including the nude stage, and are never put in a stage negative.

- Aim for small, readable steps: one garment or one gesture per stage. A stage that removes two things hides the "gradual" feel.
- Partial states (`slipping off shoulders`, `unbuttoned`, `holding hem`) between full states make the sequence smoother than jumping between worn and removed.
- Underwear stages need hand/leg poses that do not hide the whole outfit; prefer simple standing or seated poses.
- Under `pose_mode: per_stage`, change only arms/hands between neighbouring stages so identity and framing stay stable.
- Facing direction (front/back) is asked per stage for every bra / bikini / panties removal stage and every stage after it; see SKILL.md workflow. Keep the turn direction consistent: all back-facing stages look back over the same shoulder.

## Fine ladder reference

The granularity to aim for when the user chooses *Fine*. Outfit: cardigan, blouse with neck ribbon, flared skirt, thighhighs (kept on), lace bra and panties, hair ribbon and necklace (kept on). 18 stages, 40 images with `bg` + `transparent` and the nude `covered` / `open` split.

| # | id | what changes | class | facing |
| --- | --- | --- | --- | --- |
| 1 | `dressed` | fully dressed, standing | clothed | front |
| 2 | `cardi_hold` | hands hold the cardigan front | partial | front |
| 3 | `cardi_slip` | cardigan slips off both shoulders | partial | front |
| 4 | `ribbon_untie` | untying the neck ribbon (cardigan gone) | partial | front |
| 5 | `blouse_unbutton` | hand on a button, chest opening a little | partial | front |
| 6 | `blouse_open` | blouse pulled open, bra visible | underwear | front |
| 7 | `blouse_off` | blouse dropped, bra only on top | underwear | front |
| 8 | `skirt_zip` | hand on the skirt zipper | underwear | front |
| 9 | `skirt_down` | skirt falling, around the thighs | underwear | front |
| 10 | `lingerie` | underwear + thighhighs, sitting on the bed edge | underwear | front |
| 11 | `bra_unhook` | back turned, unhooking the bra (clasp visible) | underwear | back |
| 12 | `bra_off` | bra falling off the shoulders, held against the chest | underwear | back |
| 13 | `topless` | bra removed, panties on | topless (user) | back |
| 14 | `panties_pull` | hands on the panties waistband | topless (user) | back |
| 15 | `panties_down` | panties pulled down to the thighs, bent forward | topless (user) | back |
| 16 | `nude_back` | nude, groin not visible | nude (user), `open` only | back |
| 17 | `nude` | nude, sitting | nude (user), `both` | front |
| 18 | `nude_knee` | nude, hugging one raised knee (leg covers the groin in `covered`, turned wide out in `open`) | nude (user), `both` | front |

- Stages 12 and 13-15 split "bra comes off" from "topless" and "panties come off" so the jump from underwear to nude is never one step.
- Facing and the stage count are the user's decision per project; this table is a reference for granularity, not a default to copy.
