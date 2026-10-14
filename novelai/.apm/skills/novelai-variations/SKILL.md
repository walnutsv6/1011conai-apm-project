---
name: novelai-variations
description: Propose theme-appropriate outfit and pose candidates, let the user choose, then build a matrix of outfit × pose variations for one or more fixed characters with NovelAI, including background and transparent-background versions, per-character fixed seeds, outfit-mixing negative tags, and a prompts.md and a per-project index.html (plus an on-demand old-vs-new compare.html). Sub-skill of novelai-imagegen. Use when the user asks for pose variations, outfit variations, costume/pose lineups, or a character sheet set via NovelAI. Do not use for a single one-off image (use novelai-imagegen directly).
---

# NovelAI Variations (outfit × pose matrix)

Sub-skill of `novelai-imagegen`. This skill only **designs and batches the prompts**; every estimate, cost decision, authentication rule, and live call is delegated to the `novelai-imagegen` runner (`../novelai-imagegen/scripts/novelai_image.py`). Read `../novelai-imagegen/SKILL.md` first if it is not already loaded, and follow its zero-Anlas, rating-tag, and output rules unchanged.

## Concept

Each image is `character × outfit × pose × background-mode`. Only one axis changes between images, so differences are attributable and the set stays consistent.

- **Character**: fixed block (appearance, base expression, background/scene, body type) plus a **fixed seed per character**.
- **Outfit**: a tag block plus its own *negative* tags that keep other outfits from leaking in.
- **Pose**: pose tags plus the expression that belongs to the pose.
- **Mode**: `bg` (scene background from the character) and `transparent` (background replaced only).

Everything not varied is byte-identical across the set. See [references/prompt-assembly.md](references/prompt-assembly.md) for the exact order and rules.

## Workflow

In the commands below, replace `<skills-root>` with the installed skills directory. APM uses `.agents/skills` for Codex and Copilot by default, and `.claude/skills` for Claude.

1. **Propose candidates, let the user decide.** Outfits and poses are never fixed by this skill; they depend on the project's theme (race queen, school, fantasy, casual, sportswear, anything).
   - Ask for the theme/concept, the characters (or propose them), the rating, and the modes (`bg`, `transparent`, or both) if missing.
   - Then present **candidate lists** for the user to pick from, adapted to that theme:
     - Outfits: 3–6 candidates, each with an ID, a one-line meaning, and draft tags. Give a clear spread (e.g. covered / casual / revealing, or different roles) and a palette tied to each character.
     - Poses: 6–10 candidates, each with an ID, draft pose tags, and the expression that goes with it. Cover a range: idle, lean, arms-up, wave, action, prop-holding, sitting, etc., chosen to suit the theme.
     - Outfit × pose pairs: propose a sensible pairing (3–4 poses per outfit) and flag conflicts (props, poses that crop or break an outfit).
   - Use `AskUserQuestion` (multiSelect) or a plain list. The user may pick, edit, drop, or add their own; the user's tags win verbatim. Do not generate until the selection is confirmed.
   - Example candidates from a past project live in [references/example-racequeen.md](references/example-racequeen.md). Treat them as inspiration only, never as defaults.
   - **Every character's appearance must include a bangs tag** along with hair colour, length and style (e.g. `blunt bangs`, `side swept bangs`, `parted bangs`, `hair between eyes`, `swept bangs`, or `no bangs` / `forehead` when none). NovelAI otherwise picks a different fringe per outfit/pose and the character looks inconsistent. If the user did not specify one, propose a bangs tag as part of the character candidate. `build_requests.py` warns when an appearance has no `bangs` tag.
2. **Write the spec** from the confirmed selection as JSON (see [examples/spec.example.json](examples/spec.example.json)) in the project, e.g. `output/novelai-imagegen/<project>/spec.json`.
3. **Generate request files**:
   ```bash
   python <skills-root>/novelai-variations/scripts/build_requests.py --spec <spec.json> --out-dir <project>/requests [--only bay] [--outfit bunny] [--rating sensitive]
   ```
   It writes one request JSON per image, a `manifest.json`, and `prompts.md`. Existing request files are never overwritten (use `--suffix v2` for a revision).
4. **Review prompts first**: open `prompts.md`, confirm the assembled prompt for one image per outfit and per mode.
5. **Pilot**: run `estimate` + `generate` for one image per character, inspect it (anatomy, outfit correctness, no leaked props, alpha for transparent).
6. **Batch**: run `estimate` then `generate` sequentially for every request (one image per API request). Estimate must be zero or per the cost policy of `novelai-imagegen`.
   ```bash
   for f in <project>/requests/*.json; do
     uv run <skills-root>/novelai-imagegen/scripts/novelai_image.py estimate --request "$f" && \
     uv run <skills-root>/novelai-imagegen/scripts/novelai_image.py generate --request "$f" --out-dir <project>/images/<character>
   done
   ```
   The runner refuses to overwrite; skipped/existing outputs are fine to leave.
7. **Inspect every output** and fix failures with a *targeted* change (see Fix patterns). Rename the redo with a `v2` suffix; move the old files to `superseded/` rather than deleting.
8. **Build the project index page** (part of this skill; after every batch and after every redo):
   ```bash
   python <skills-root>/novelai-variations/scripts/build_index.py --project-dir output/novelai-imagegen/<project> --title "<project title>"
   ```
   Writes `output/novelai-imagegen/<project>/index.html`, **one list page for the whole project** (same style as `racequeen/index.html`): a nav of characters, then one section per character with a table whose rows are outfit × (`背景あり`/`透過`) and whose columns are poses. It shows **latest versions only** (files in `superseded/` are ignored; the highest `vN` wins), click-to-zoom, light/dark, checkerboard behind transparent images. Open it and check every cell shows an image.
9. **Old-vs-new comparison is a separate page, built only when needed** (e.g. after a redo, or when the user asks to compare):
   ```bash
   python <skills-root>/novelai-variations/scripts/build_compare.py --project-dir output/novelai-imagegen/<project> [--character mia] [--outfit bunny] [--pose lean] [--mode bg]
   ```
   Writes `compare.html` next to `index.html`: for each cell with 2+ versions (including `superseded/`), versions side by side oldest → newest with a tag diff of prompt/negative (+added / −removed) between consecutive versions. Do not build it by default; `index.html` links to it automatically if it exists.
10. **Summarize**: `prompts.md` (from `build_requests.py`) plus the `index.html` path (and `compare.html` if built).

## Fixed conventions (technical, theme-independent)

- Model `nai-diffusion-5-full`, 832×1216 portrait, steps 28, scale 5.0, samples 1.
- Seed fixed **per character**, shared by all of that character's images (identity stays stable across outfits/poses).
- Subjects are always adults: keep `mature female, adult woman, 20s, tall` in the base tags and `child, loli, petite, flat chest` in the negative. Do not remove them.
- Composition `cowboy shot` + `looking at viewer`; negative `full body, wide shot` to keep framing uniform.
- Transparent version: replace **only** the background segment with `transparent background, simple background, no background`; set `straight_alpha: true`, `tag_hint_transparent_background: true`; in negative add `scenery, background, outdoors`. Verify the alpha channel.
- Filename: `<character>-<outfit>-<pose>-<bg|transparent>[-<note>][-vN]-seed<seed>.png` with its adjacent `.json`.

## Fix patterns (change one thing, keep the seed)

| Symptom | Fix |
| --- | --- |
| Outfit bleeds in from another outfit | Add that outfit's distinguishing tags to the negative (e.g. `bikini, miniskirt, swimsuit` for a covered outfit). Put them in the outfit's negative block, not globally. |
| Prop appears where it should not (umbrella, flag) | Add the prop to the negative for outfits/poses that exclude it; remove from negative only for the pose that uses it. |
| Bangs / fringe differ between images | Add (or fix) a bangs tag in the character `appearance` (e.g. `side swept bangs`), and put the conflicting fringe in the character negative (e.g. `blunt bangs, hair between eyes`). Regenerate the whole character with the same seed so all images match. |
| Hair colour drifts toward the wrong shade (e.g. `platinum blonde` renders silver/white) | Put the colour first in `appearance` with a plain-colour companion tag (`platinum blonde hair, pale blonde hair`), and add the drifted shades to the character negative (`silver hair, white hair, grey hair`). Regenerate the whole character with the same seed. Verified: this moved silver-white to blonde. If it overshoots to golden, drop `pale blonde hair` or add `yellow hair, golden hair` to the negative. |
| Accessory (e.g. rabbit/cat ears, crown) cut off at the top edge | **Only when the user asks** (framing is `cowboy shot`, not full body, so slight crops are accepted by default). Apply to the affected outfit only via `overrides`: `append_outfit` (e.g. `long rabbit ears`), `append_negative` (`head out of frame, cropped head, cut off ears, out of frame`), `replace_composition` (e.g. `cowboy shot, from a distance, headroom, space above head`). Tags shift framing only slightly; if a pose still crops, give that image a different `seed` in its override (try a few, keep the best) and label it `altseed`. Check for stray objects the new seed introduces and negate them. |
| Skin tone / hair colour drifts | Reinforce with an extra tag in the character appearance (e.g. `fair skin, light tan skin`; `dark red-brown hair`) and add opposites to the negative (`dark skin, deep tan`; `blonde hair`). Use as a per-image override and label `-skin`/`v2`. |
| Eyes closed/half-closed by an expression tag | Drop that expression tag for the pose (per-character override) and add `closed eyes, half-closed eyes` to the negative. |
| Body type inconsistent between outfits | Add per-outfit body tags (e.g. `slender, large breasts, slim legs`) and matching negatives; keep `curvy`/`slim waist` base. |
| Transparent version has leftover scenery | Strengthen negative with `scenery, background, outdoors`; regenerate; if still bad, use the `remove_background` Director Tool (paid, needs confirmation). |
| Only a tiny pose change wanted | Edit just the pose tags; never reorder the rest of the prompt (changes the composition under a fixed seed). |

Override keys: `replace_pose_expression`, `replace_outfit`, `append_outfit`, `replace_composition`, `append_appearance`, `append_negative`, `append_body`, `seed`, `note`. Per-character / per-image exceptions go in the spec's `overrides` array rather than being hand-edited in request files, so `prompts.md` stays the single source of truth.

## Output layout

```
output/novelai-imagegen/<project>/
  spec.json
  requests/            # generated request JSON + manifest.json
  images/<character>/  # png + json (runner output), superseded/ for old takes
  prompts.md           # generated prompt tables
  index.html           # project list page, latest only (build_index.py)
  compare.html         # old vs new, on demand (build_compare.py)
```

## Reporting

Report: index.html path, counts (characters × valid pairs × modes), seeds per character, total estimated Anlas, any images redone and why, and the output paths. Do not claim success for images not inspected.
