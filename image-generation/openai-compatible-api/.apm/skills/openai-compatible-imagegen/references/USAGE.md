# Usage reference

## Config file (endpoint and model)

Put non-secret endpoint settings in `imagegen.config.json` in the project root, the directory you run the scripts from. Copy `examples/imagegen.config.example.json` to start.

```json
{
  "_comment": "No API keys here. Keys starting with _ or $ are ignored.",
  "base_url": "http://localhost:8080/v1",
  "model": "your-image-model-id",
  "api_key_env": "IMAGEGEN_API_KEY",
  "no_auth": false,
  "params": { "response_format": "b64_json", "size": "1024x1024" }
}
```

| Field | Meaning |
| --- | --- |
| `base_url` | API base URL **including** `/v1`. Requests go to `<base_url>/images/generations` and `/images/edits`. |
| `model` | Default model id. |
| `api_key_env` | **Name** of the environment variable holding the key (e.g. `IMAGEGEN_API_KEY`). Never the key itself. |
| `base_url_env` | Name of an env var to read the base URL from, used only when `base_url` is absent. |
| `no_auth` | `true` for local servers without authentication (no `Authorization` header is sent). |
| `params` | Default request fields merged into every generate/edit request, e.g. `response_format`, `size`, `quality`, `background`, or server-specific fields such as `steps`. Command-line options and `--extra-json` override them. `model`, `prompt`, `n`, `image` and `mask` are not allowed here. |

Rules:
- **Which file is read:** `--config PATH`, else `$IMAGEGEN_CONFIG`, else `./imagegen.config.json` if it exists. A missing file is an error only when it was named explicitly.
- **Precedence:** command line > config file > env vars (`OPENAI_BASE_URL`, `IMAGEGEN_MODEL`) > defaults. The config file wins over env vars on purpose: `OPENAI_BASE_URL` is often set globally for other tools and should not silently redirect this project. `check` prints a `sources` map showing where each value came from.
- **Validation:**
  - A file containing any credential-like field (`api_key`, `apikey`, `token`, `access_token`, `authorization`, `password`, `secret`, `cookie`, …), at any depth, is rejected.
  - Unknown fields and wrong types are errors, so typos do not silently fall back to OpenAI.
  - A base URL with embedded `user:password@` is rejected.
- **Several endpoints:** keep one file per endpoint (e.g. `configs/local.json`, `configs/openai.json`) and pass `--config`.
- **Committing:** the file holds no secrets, so it is safe to commit.

## Environment setup (API key)

The API key is read only from the process environment. Set it in the shell (or OS user settings) that launches the agent, then restart the agent session so it inherits it. Do not put keys in project files, `.env` files, the config file, scripts, or command lines.

| Variable | Purpose | Default |
| --- | --- | --- |
| `OPENAI_API_KEY` | API key. Use another name via `api_key_env` in the config or `--api-key-env NAME`. | — |
| `OPENAI_BASE_URL` | Base URL **including** `/v1`, used when neither `--base-url` nor the config sets one | `https://api.openai.com/v1` |
| `IMAGEGEN_MODEL` | Default model id, used when neither `--model` nor the config sets one | `gpt-image-1` |
| `IMAGEGEN_CONFIG` | Path of the config file | `./imagegen.config.json` |

PowerShell 7+, current session only (Windows PowerShell 5.1 lacks `-MaskInput`; use `[System.Net.NetworkCredential]::new('', (Read-Host -AsSecureString)).Password` in its place):
```powershell
$env:OPENAI_API_KEY = Read-Host -MaskInput "API key"   # typed, not echoed, not stored in history
```
Persistent for the Windows user (takes effect in newly started terminals). Type it interactively, not inside a script you save:
```powershell
[Environment]::SetEnvironmentVariable("OPENAI_API_KEY", (Read-Host -MaskInput "API key"), "User")
```
bash / zsh, current session:
```bash
read -rs OPENAI_API_KEY && export OPENAI_API_KEY
```
For persistence on macOS/Linux prefer a secret manager or the OS keychain over writing the key into `~/.bashrc`.

Several providers side by side: give each its own key variable, and name it in that endpoint's config file (`"api_key_env": "LOCALAI_API_KEY"`).

## Parameters

Only `model`, `prompt` and `n` are always sent. Other fields are sent only when you give them, either on the command line or in the config `params`, because compatible servers often reject unknown fields.

| Option | API field | Notes |
| --- | --- | --- |
| `--size` | `size` | gpt-image: `1024x1024`, `1536x1024`, `1024x1536`, `auto`. dall-e-3: `1024x1024`, `1792x1024`, `1024x1792`. Others vary. |
| `--quality` | `quality` | gpt-image: `low`/`medium`/`high`/`auto` (cost scales strongly with quality). dall-e-3: `standard`/`hd`. |
| `--background` | `background` | gpt-image: `transparent`/`opaque`/`auto`. Transparent needs png/webp. Most other servers ignore or reject it. |
| `--output-format` | `output_format` | gpt-image: `png`/`webp`/`jpeg`. When omitted it is not sent; the file extension of `--output` is used only locally. |
| `--response-format` | `response_format` | dall-e-2/3 and many local servers: `b64_json` or `url`. **gpt-image rejects this field** (it always returns b64_json). |
| `--seed` | `seed` | Only servers that support it (several local servers do; OpenAI does not). |
| `--n` | `n` | dall-e-3 only allows 1. |
| `--extra-json` | merged | Anything else: `{"input_fidelity": "high"}` (gpt-image edits: preserve faces/details of the input), `{"output_compression": 80}`, `{"moderation": "low"}`, `{"style": "natural"}` (dall-e-3), or server-specific fields such as `{"steps": 20}`. |

Edits (`/images/edits`) are sent as `multipart/form-data`: one `--image` uses the field `image`, several use `image[]` (override with `--image-field`). `--mask` is a PNG of the same size whose fully transparent pixels mark the area to repaint. dall-e-2 edits require square RGBA PNGs under 4 MB; gpt-image accepts png/webp/jpg and several reference images.

Model availability changes over time. Use `check --live` to list the models the endpoint exposes, and check the provider's documentation for current models and pricing.

## Outputs

- `--output a.png` with `--n 1` → `a.png`; with `--n 3` → `a-1.png`, `a-2.png`, `a-3.png`.
- Each image gets `<image>.json`: endpoint path, base-URL host, params (incl. prompt), `revised_prompt`, `usage` (token counts on gpt-image), the response's `created`, `size`, `quality` and `background` when returned, the detected file format, and a completion timestamp.
- If the server returns a body that cannot be parsed, it is saved as `<output>.response.txt` for inspection. **Do not re-run the paid request automatically**; inspect first.

## Provider notes

- **OpenAI**: default base URL. gpt-image models support transparent backgrounds natively, which is the best path for sprites.
- **LocalAI / other self-hosted servers**: in `imagegen.config.json` set `base_url` (`http://host:port/v1`), `model`, and `"no_auth": true` if no key is configured. Add `"params": {"response_format": "b64_json"}` if the server would otherwise return a URL. Transparent backgrounds are usually unsupported, so prompt for a flat chroma background and use `postprocess.py remove-bg`.
- **Servers that return URLs**: the image is downloaded from the URL without sending the API key.
- Chat-completions-based image models (e.g. via OpenRouter) are **not** supported by this skill.

## Post-processing details (`postprocess.py`)

- `remove-bg`: background colour is the median of the border pixels (or `--color "#RRGGBB"`). Pixels within `--tolerance` (summed RGB distance, default 28) become transparent, then alpha ramps over `--soft` (default 22). By default only background-coloured regions **connected to the image border** are removed, so enclosed details (eye whites on white) survive; `--global` keys every matching pixel (use for gaps between arms and body that are enclosed). Inputs that already contain transparency are copied unchanged unless `--rekey`.
- `trim`: crops to pixels with alpha ≥ `--alpha-threshold` (default 1) and adds `--padding`.
- `pixelate`: `--width`/`--height` (one keeps aspect) or `--scale-factor`. `--resample box` (average, default) gives cleaner results from painterly AI images; `nearest` keeps hard edges if the source is already pixel-aligned. `--colors N` (median cut, no dithering) or `--palette` (`"#000000,#ffffff"`, a GIMP `.gpl`, or a palette `.png`). Alpha is binarised at `--alpha-threshold` (default 128; `-1` keeps soft alpha). `--preview-scale 8` also writes `<name>@8x.png` for review.
- `sheet-pack`: inputs in the given order (globs are sorted). Cell = largest frame unless `--cell WxH`. `--padding` is used for both margin and spacing. `--align bottom` keeps characters' feet on a common baseline. Frame names in the atlas are the input file names.
- `sheet-slice`: `--rows/--cols` or `--cell WxH`, with the same `--padding` semantics as `sheet-pack`. `--skip-empty` drops fully transparent cells. AI-generated "sprite sheets" are rarely on an exact grid — generate frames individually and pack them instead.

## Troubleshooting

| Symptom | Cause / action |
| --- | --- |
| `<NAME> is not set` | The variable named by `api_key_env` is not visible to the agent process: set it and restart the session. |
| Requests still go to api.openai.com | No config file was found in the current directory. Run `check` and look at `config_file` and `sources`, or pass `--config`. |
| `contains credential fields` | Remove the key from the config file and set `api_key_env` to the variable's name instead. |
| `HTTP 400 ... response_format` | Remove `--response-format` (gpt-image). |
| `HTTP 400 ... background` / unknown parameter | Server doesn't support it: drop the option, use a chroma background + `remove-bg`. |
| `HTTP 401/403` | Wrong key for this base URL, or the organisation is not verified for the model. |
| `HTTP 404` | Base URL missing `/v1`, or the server lacks `/images/*`. |
| Halo / fringe of background colour | Increase `--tolerance` or `--soft`, or re-key with an explicit `--color`. |
| Inner gaps not removed | Use `remove-bg --global` (only when the background colour does not appear inside the sprite). |
| Pixel art looks muddy | Trim first so the sprite fills the frame, try `--resample nearest`, reduce `--colors`, or use a fixed palette. |
