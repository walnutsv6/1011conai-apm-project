---
name: openai-compatible-imagegen
description: Generate and edit 2D game assets (sprites, characters, items, icons, tiles, UI parts) through any OpenAI-compatible Images API (/v1/images/generations and /v1/images/edits — OpenAI gpt-image models, LocalAI and similar servers), then remove backgrounds, convert to pixel art and pack or slice sprite sheets locally. Use when asked to make image or sprite assets with OpenAI or an OpenAI-compatible endpoint, or to post-process sprites. Do not use for NovelAI requests (use novelai-imagegen). The API key is read only from an environment variable.
---

# OpenAI-compatible ImageGen — 2D game assets

Two scripts, both run from this skill's `scripts/` folder:

- `scripts/imagegen.py` — API client (Python 3.10+, stdlib only). Subcommands: `check`, `generate`, `edit`.
- `scripts/postprocess.py` — local image ops (Pillow; `uv run` installs it automatically). Subcommands: `remove-bg`, `trim`, `pixelate`, `sheet-pack`, `sheet-slice`.

Read [references/USAGE.md](references/USAGE.md) for provider differences and parameters, and [references/sprite-prompting.md](references/sprite-prompting.md) **before writing any asset prompt**.

## Endpoint config file and API key
- **Endpoint and model** (non-secret) go in `imagegen.config.json` at the project root (the directory the scripts are run from). `--config PATH` or `$IMAGEGEN_CONFIG` point elsewhere. Template: [examples/imagegen.config.example.json](examples/imagegen.config.example.json). Fields:
  - `base_url`: including `/v1`.
  - `model`
  - `api_key_env`: the *name* of the env var holding the key.
  - `no_auth`
  - `params`: default request fields such as `response_format`, `size`, `quality`.
- **Precedence:** command-line option > config file > env vars (`OPENAI_BASE_URL`, `IMAGEGEN_MODEL`) > defaults (`https://api.openai.com/v1`, `gpt-image-1`, key env `OPENAI_API_KEY`). `check` prints where each value came from.
- To switch to a non-OpenAI endpoint, create or edit the config file rather than passing `--base-url` on every call. The file contains no secrets, so it can be committed.
- **The API key is never in files.** It is read only from the env var named by `api_key_env` / `--api-key-env` (default `OPENAI_API_KEY`). The script refuses a config file that contains any credential-like field (`api_key`, `token`, `authorization`, …). There is no option that takes the key value.
- Never ask the user to paste a key into chat, and never write a key into scripts, `.env` files, config or request JSON, command lines, logs, or commits. If `check` reports `NOT SET`, explain how to set it in the shell that launches the agent (see USAGE.md "Environment setup") and stop.
- `no_auth` (`--no-auth`) is only for local servers that need no key.

## Workflow
1. **Plan the asset set.** Agree on subject, view (side / top-down / isometric / front), target in-game size (e.g. 32×32), palette or style, and the list of frames/variants. Decide the output folder in the game project (e.g. `assets/sprites/<name>/raw/`).
2. **Check the endpoint**: `python scripts/imagegen.py check` shows the config file, endpoint, model and key status. Add `--live` to list models; it makes one cheap GET. If the user wants a non-OpenAI endpoint and there is no config yet, create `imagegen.config.json` from the template with their URL and model (no key), then re-run `check`.
3. **Write the prompt** following `references/sprite-prompting.md`: one subject, centred, full body, fixed view, consistent style anchor, plain background. Use `--background transparent` with gpt-image models; otherwise ask for a flat chroma background (`solid flat #FF00FF magenta background`). Do not name existing games, franchises, or characters.
4. **Dry run first, always.** Run `generate`/`edit` without `--execute` and show the user the preview (endpoint, model, size, quality, n, outputs, prompt). Generation is billed by the provider; the script does not estimate price. Only after explicit approval of that request (or a bounded batch with a stated image count) re-run with `--execute`. Start with `--quality low` / small `--n` while iterating.
5. **Never auto-retry a failed or ambiguous POST** and never loop paid calls to "improve" quality — report the error and ask.
6. **Consistency across frames/variants:** pick the best base image, then use `edit --image base.png` (add `--extra-json '{"input_fidelity": "high"}'` on gpt-image models) with a prompt that changes only the pose/variant. Repeat per frame. Inspect each result.
7. **Post-process locally** (no cost, no `--execute` needed):
   `remove-bg` (skip if already transparent) → `trim --padding 2` → `pixelate` (target size, `--colors` or `--palette`) → `sheet-pack` (`--align bottom` for characters).
8. **Look at the images** (open the PNG, or the `@Nx` preview from `pixelate`) before reporting. Report file paths, what was generated, and anything that looked off.
9. Keep each image's sidecar `<image>.json` (prompt, revised prompt, params, usage). Remind the user to check the provider's terms for commercial use; this skill gives no legal clearance.

## Commands

```bash
# Endpoint / key status (never prints the key); reads ./imagegen.config.json if present
python scripts/imagegen.py check
python scripts/imagegen.py check --live --config configs/local-server.json
python scripts/imagegen.py check --live --base-url http://localhost:8080/v1 --api-key-env LOCALAI_API_KEY   # one-off override

# Text-to-image dry run (add --execute after approval)
python scripts/imagegen.py generate --model gpt-image-1 --size 1024x1024 --quality low --background transparent \
  --prompt-file prompts/slime_idle.txt --output assets/sprites/slime/raw/idle.png

# Several candidates (n > 4 also needs --allow-many); saved as idle-1.png, idle-2.png ...
python scripts/imagegen.py generate --n 3 --quality low --background transparent --prompt "..." --output raw/idle.png

# Variant / animation frame guided by a base image
python scripts/imagegen.py edit --image raw/idle-2.png --background transparent --extra-json '{"input_fidelity": "high"}' \
  --prompt "Same slime character, same style and colours, squashed flat mid-jump, side view" --output raw/jump.png

# Masked edit (transparent mask pixels = area to repaint)
python scripts/imagegen.py edit --image raw/sword.png --mask raw/sword_blade_mask.png --prompt "blade glowing blue" --output raw/sword_ice.png

# Local post-processing (uv installs Pillow; or use python if Pillow is installed)
uv run scripts/postprocess.py remove-bg --input raw/jump.png --output cut/jump.png            # --color "#FF00FF" to force
uv run scripts/postprocess.py trim --input cut/jump.png --output cut/jump_trim.png --padding 2
uv run scripts/postprocess.py pixelate --input cut/jump_trim.png --output px/jump.png --height 32 --colors 16 --preview-scale 8
uv run scripts/postprocess.py sheet-pack --inputs "px/*.png" --columns 4 --align bottom --padding 1 --output sheets/slime.png
uv run scripts/postprocess.py sheet-slice --input sheets/slime.png --cell 32x32 --padding 1 --output-dir frames --prefix slime
```

`sheet-pack` writes `<sheet>.json` in TexturePacker "JSON Hash" format (Phaser `load.atlas`, PixiJS `Spritesheet`), plus `meta.grid` (frame size, margin, spacing) for uniform-grid loaders such as Phaser `load.spritesheet` or Godot `hframes/vframes`.

## Safety rules enforced by the scripts
- Dry run unless `--execute`; `--n` above 4 needs `--allow-many` (hard cap 10).
- Never overwrites existing images or sidecars (`postprocess.py` only with `--force`).
- Edit inputs outside the current project are rejected unless `--allow-external-inputs`.
- The key is sent only to the configured base URL, never to result download URLs, and is masked in error messages. Credential-like fields are stripped from sidecars and rejected in `--extra-json` and the config file.
- Config files are validated: unknown fields, non-string URLs or models, and `model`/`prompt`/`n` inside `params` are errors.

## Not implemented
Chat-completions / Responses-API image output (e.g. OpenRouter image models), streaming or partial images, ML background segmentation (rembg etc.), automatic retries, cost estimation or balance queries, automatic grid detection for AI-drawn sheets, and guaranteed character consistency between frames. Do not claim these are available.
