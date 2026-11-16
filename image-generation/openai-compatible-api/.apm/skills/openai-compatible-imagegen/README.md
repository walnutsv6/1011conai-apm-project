# OpenAI-compatible ImageGen — 2D game assets

This skill generates sprites, items, icons and tiles through any OpenAI-compatible Images API: OpenAI gpt-image models, LocalAI, and other servers that expose `/v1/images/generations` and `/v1/images/edits`. It then turns the results into game-ready files locally:

- background removal
- trimming
- pixel-art downscaling with a palette limit
- sprite sheets with a TexturePacker-compatible JSON atlas

## Install

```bash
apm install walnutsv6/1011conai-apm-project/image-generation/openai-compatible-api --target <target>
```

Requirements:
- Python 3.10+.
- `imagegen.py` uses only the standard library.
- `postprocess.py` needs Pillow. `uv run scripts/postprocess.py ...` installs it automatically; alternatively, `pip install pillow` and run it with `python`.

## Endpoint and API key

Put the endpoint URL and model in `imagegen.config.json` at your project root. Copy `examples/imagegen.config.example.json` to start:

```json
{ "base_url": "http://localhost:8080/v1", "model": "your-image-model-id", "api_key_env": "IMAGEGEN_API_KEY" }
```

The key is read **only** from the environment variable named in `api_key_env` (default `OPENAI_API_KEY`).
- Set it in the environment that launches your agent. See `references/USAGE.md` for PowerShell and bash examples.
- A config file that contains a key is rejected.
- Do not store the key in a `.env` file, a script or the repository.

Precedence: command line > config file > env vars (`OPENAI_BASE_URL`, `IMAGEGEN_MODEL`) > defaults.

## Quick start

```bash
python scripts/imagegen.py check
python scripts/imagegen.py generate --quality low --background transparent \
  --prompt "2D game sprite of a small green slime, side view, centred, pixel-art style, transparent background" \
  --output assets/slime/raw/idle.png                    # dry run: shows the request, sends nothing
# ...after approving: add --execute
uv run scripts/postprocess.py pixelate --input assets/slime/raw/idle.png --output assets/slime/idle32.png --height 32 --colors 12 --preview-scale 8
```

Generation is billed by the provider. The scripts always dry-run unless `--execute` is given, never overwrite files, and never retry a paid request automatically.

See `SKILL.md` for the agent workflow, `references/USAGE.md` for parameters, providers and troubleshooting, and `references/sprite-prompting.md` for prompt patterns.
