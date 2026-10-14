# Request parameters

Use schema version 1. Pass request JSON with `--request` or `--request-json-stdin`.

## Generate

```json
{
  "schema_version": 1,
  "operation": "generate",
  "prompt": "1girl, baseball uniform, standing",
  "negative_prompt": "bad anatomy, extra fingers, text, watermark",
  "model": "nai-diffusion-5-full",
  "orientation": "portrait",
  "steps": 28,
  "scale": 5.0,
  "samples": 1,
  "cost_policy": {
    "subscription_plan": "auto",
    "prefer_zero_anlas": true,
    "require_zero_anlas": false,
    "confirm_above_anlas": 100,
    "confirmed_paid": false
  },
  "output": {"basename": "baseball-player", "format": "png"}
}
```

Omit `size` to use orientation-aware zero-Anlas defaults. Omit both `size` and `orientation` for `1024x1024`.

Accepted `size` forms:

- `"1024x1024"`
- `[1024, 1024]`
- `{"width": 1024, "height": 1024}`
- `"square"`, `"landscape"`, or `"portrait"`

Main SDK-backed fields:

- `model`
- `negative_prompt`
- `quality`
- `uc_preset`
- `steps` from 1 through 50
- `scale` from 0 through 10
- `sampler`
- `noise_schedule`
- `seed`
- `samples` from 1 through 64 total; the runner chunks or splits API requests
- `cfg_rescale`
- `variety_boost`
- `straight_alpha`
- `tag_hint_transparent_background`
- `image_format`: `png` or `webp`

## Cost policy

`subscription_plan` is normally `auto`. The runner queries NovelAI for live operations. Use `opus` or `non_opus` only for offline estimate tests; never use an override as proof of a live account tier.

`prefer_zero_anlas` defaults to true. It fills only unspecified values and splits a multi-image request into one-image calls when every call estimates zero.

`require_zero_anlas` prohibits live execution when the estimate is nonzero or unknown.

`confirm_above_anlas` defaults to 100. An estimate of zero never requires confirmation.

After the user confirms a high-cost request, set `confirmed_paid` to true without changing other values.

## img2img

```json
{
  "schema_version": 1,
  "operation": "edit",
  "prompt": "same character, running pose",
  "i2i": {"image": "inputs/character.png", "strength": 0.55, "noise": 0.0}
}
```

## Inpaint

```json
{
  "schema_version": 1,
  "operation": "edit",
  "prompt": "replace only the hat with a blue baseball cap",
  "inpaint": {"image": "inputs/player.png", "mask": "inputs/hat-mask.png", "strength": 1.0}
}
```

## Character or style reference

```json
{
  "schema_version": 1,
  "operation": "edit",
  "prompt": "standing at home plate",
  "character_references": [
    {"image": "inputs/reference.png", "type": "character", "fidelity": 0.8, "strength": 1.0}
  ]
}
```

Reference type is `character`, `style`, or `character&style`.

## ControlNet / Vibe Transfer

```json
{
  "schema_version": 1,
  "operation": "edit",
  "prompt": "baseball pitcher in windup",
  "controlnet": {
    "strength": 1.0,
    "images": [{"image": "inputs/pose.png", "info_extracted": 0.7, "strength": 0.6}]
  }
}
```

## Director Tool

```json
{
  "schema_version": 1,
  "operation": "tool",
  "tool": "remove_background",
  "input": "inputs/player.png",
  "cost_policy": {"subscription_plan": "auto", "confirmed_paid": false},
  "output": {"basename": "player-cutout", "format": "png"}
}
```

Tools: `line_art`, `sketch`, `colorize`, `emotion`, `declutter`, `remove_background`, and `upscale`.

Extra fields:

- `colorize`: `prompt`, `defry` (0–5)
- `emotion`: `emotion`, `prompt`, `defry` (0–5)
- `declutter`: `keep_bubbles`
- `upscale`: `model`

Background removal returns masked, generated, and blend images. Upscale cost is unknown in SDK 0.14.1 and requires `confirmed_paid: true`.
