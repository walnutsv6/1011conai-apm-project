# Inpaint method

Goal: stages and expressions that line up pixel for pixel, so the game can swap sprites without the figure jumping. Trade-offs against the seed method are measured in the pilot, not assumed.

## Chain

```
dressed plate (generate, grey background)            group "dressed"
 ├─ dressed <expr>      inpaint face of dressed plate
 ├─ cardi_tr            inpaint clothes+face of dressed plate (transition branch)
 └─ cardioff plate      inpaint clothes of dressed plate
     ├─ cardioff <expr> inpaint face
     ├─ blouse_tr       ...
     └─ ...
bra_tr (facing back)   facing changed -> new base plate (generate)   group "bra_tr"
topless (back)         parent = previous main (lingerie, front) -> facing differs -> new base "topless"
```

- A main stage repaints the **previous main stage's normal plate** (cumulative, so removed garments stay removed). Error accumulates down the chain; if a late stage drifts, regenerate from a fresh base with `--suffix v2` rather than piling on fixes.
- Transitions branch off the previous main stage and never feed later stages.
- Facing changes start a new base plate. A base plate is a plain generation with the fixed seed, so it is as consistent as the seed method, not more.
- Special poses (arms move) and one-shots are seed-method only.

## Masks

`make_masks.py` finds the figure's bounding box on the grey plate and cuts boxes relative to it (fractions of the bbox height/width): `face` (centred on the head columns), `upper` (shoulders to waist), `chest`, `lower` (waist down), `torso` (neck down). Combined regions are joined with `+` (`upper+face`); transitions always include `face` because their expression differs from the parent. Masks are per group (`masks/<c>/<group>/`), made after that group's base plate exists; the user-run inpaint script regenerates them for user-run base plates by itself.

- Look at every `_overlay-*.png` before running the inpaint requests of that group.
- Too small a box leaves fragments of the removed garment at the edge; too large a box lets hair and arms change. Adjust in `defaults.mask_regions` (e.g. `"lower": [0.40, 1.0, -0.08, 1.08]`), or replace the PNG with a hand-painted mask of the same name (white = repaint).
- A long skirt or open cardigan reaching outside the body bbox needs negative x0 / x1 > 1 margins.

## Cut-out (transparency)

NovelAI inpainting cannot output alpha, so plates are generated on `simple background, grey background` and cut out locally:

- `uv run remove_bg.py --cells <project>/cells.json --character <c>` — rembg with `isnet-anime` (pinned in the script header; first run downloads the model; needs Python <3.14, which uv provides). Agent cells only; user-run cells are cut out by the user's script.
- `--method chroma` — keys out the plate's border colour with a soft edge; no model. **Unusable on the default grey plate** with white/grey clothing or skin shading (meru pilot: sweater and skin shadows became transparent). Use it only with a `plate_background` colour absent from the character (e.g. `simple background, green background`).
- NovelAI `remove_background` Director Tool is never free; only with the user's explicit paid confirmation.
- Output: `images/<c>/cutout/<same name>.png`. The preview and export prefer cut-outs; the plate stays the source.
- Check the cut-out edges on a dark and a light background (the preview shows a checkerboard); fix hair halos with `chroma` + a different `plate_background` colour if rembg cuts into the hair.

## Fix patterns

| Symptom | Fix |
| --- | --- |
| Removed garment remnants at the mask edge | Widen the region in `mask_regions`; regenerate that cell only (see "Revising a take"). |
| Sleeves of a removed top survive as a new garment (white long sleeves) | Add `bare arms, bare shoulders` to the stage tags and `long sleeves, sleeves` to the negative of that stage and every later one (meru pilot). |
| The removed garment's edge turns into an accessory where the mask ends (cuffs become wrist scrunchies) | The box ends at the old hem: extend it past the hem (meru: `upper` to the hands, `[0.27, 0.88, -0.06, 1.06]`) and add the accessory to the negative of that stage and every later one (`wrist cuffs, wrist scrunchie, bracelet`). |
| Face/hair changes when only clothes should | Region too high: lower `y0` of `upper` / `torso`. |
| Expression inpaint barely changes the face | Raise `face_inpaint_strength` (0.85 -> 1.0) or widen `face`; if eyes close, see strip-sequence "Eyes closed" fix. |
| Expression inpaint changes identity | Lower `face_inpaint_strength` (0.85 -> 0.7). |
| Seam / lighting step at the mask edge | Slightly larger region; same `plate_background`; keep strength 1.0 for clothes. |
| Cut-out halo or holes | Switch method (`--method chroma` / rembg) with `--force`; change `plate_background` to a colour absent from the character. |
| Nonzero inpaint estimate | Stop (zero-Anlas policy); check size = plate size and steps <= 28; report to the user. |

## Revising a take

- Agent cell: move the old png, its `manifest/<stem>.json` and its `cutout/` png to `images/<c>/superseded/` (same sub-folders) and the old request to `requests_superseded/<method>/`; fix the spec; rebuild with `--method <m> --stage <id>`. The new take has the same name, so children keep pointing at it.
- Or keep both with `--suffix v2`: requests and outputs get `-v2`; cells.json keeps the plain name and every reader picks the newest `-vN`. Inpaint parents of a rebuilt stage point at the `-v2` take, others at the newest existing take.
- After a parent changed, run `build_game_requests.py --refresh-unrun` so requests that have not produced an image yet are rewritten from the current spec (existing images and their requests are never touched).
