# Prompt assembly

## Positive order

```
[background] , 1girl, solo, mature female, adult woman, 20s, tall ,
[appearance] , [base expression] , [outfit] , cowboy shot ,
[pose] , [pose expression] , looking at viewer ,
[body] , anime style, detailed, vivid colors, rating:<rating>
```

- `[appearance]` always contains hair colour, length, style **and a bangs tag**; omitting bangs lets the fringe vary between images.
- `[background]` is the character's scene for `bg` mode, and exactly `transparent background, simple background, no background` for `transparent` mode. Nothing else differs between the two modes.
- Pose expression follows the pose tags and supplements the base expression.
- The rating tag is last and appears once (see `novelai-imagegen` prompting rules).
- Keep the order stable. Under a fixed seed, reordering tags changes the whole image.

## Negative order

```
[character negative] , [outfit negative] , [mode negative] , [common negative]
```

- Character negative: identity guards (e.g. `dark skin, deep tan`).
- Outfit negative: tags that stop other outfits or props leaking in. Derive them from the outfits actually chosen (what each outfit must *not* look like). Illustrative examples:
  - swimwear: `race queen, umbrella, parasol, jacket, nude, nipples`
  - covered outfit: `umbrella, parasol, cleavage, midriff, navel, bikini, miniskirt, swimsuit`
  - revealing outfit: `umbrella, parasol, bikini, nude, nipples`
  - A pose that needs a prop (parasol) removes that prop from the outfit negative.
- Mode negative (transparent only): `scenery, background, outdoors`.
- Common negative: `full body, wide shot, child, loli, petite, flat chest, multiple girls, bad anatomy, extra fingers, missing fingers, malformed hands, duplicate, text, watermark, logo, signature`.

## Request JSON (per image)

```json
{
  "schema_version": 1,
  "operation": "generate",
  "prompt": "...",
  "negative_prompt": "...",
  "model": "nai-diffusion-5-full",
  "orientation": "portrait",
  "seed": 318245,
  "steps": 28,
  "scale": 5.0,
  "samples": 1,
  "cost_policy": {"subscription_plan": "auto", "prefer_zero_anlas": true, "require_zero_anlas": true, "confirm_above_anlas": 100, "confirmed_paid": false},
  "output": {"basename": "bay-bikini-wave-transparent", "format": "png"},
  "straight_alpha": true,
  "tag_hint_transparent_background": true
}
```

`straight_alpha` and `tag_hint_transparent_background` are set only for transparent mode. `require_zero_anlas` defaults to true here so batches can never spend Anlas silently; set it false in the spec only if the user accepts paid generations.

## Choosing candidates

Outfit and pose sets are not fixed. Offer theme-appropriate candidates and let the user decide (see SKILL.md step 1). Guidelines when drafting candidates:

- Give outfits a clear visual spread and a palette tied to each character so identity reads across outfits.
- Cover a range of poses; pair each outfit with only the poses that suit it.
- Write the outfit negative from the chosen outfits so they do not bleed into each other; a prop-holding pose must not be blocked by its own negative (`negative_remove`).
- Give every character a scene (background tags) that matches the theme; it is used for `bg` mode only.
