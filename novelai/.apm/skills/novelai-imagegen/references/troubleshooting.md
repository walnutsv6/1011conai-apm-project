# Troubleshooting

## Missing API key

Set `NOVELAI_API_KEY` in the local process. Never put the key in request JSON or chat.

PowerShell:

```powershell
$env:NOVELAI_API_KEY = "..."
```

Bash:

```bash
export NOVELAI_API_KEY="..."
```

Run `uv run scripts/novelai_image.py validate --live` after configuration.

## Dependency failure

Run the script through `uv run`, not bare Python. Inline dependency metadata pins `novelai-sdk==0.14.1` and installs `socksio` for environments that expose an HTTPX SOCKS proxy.

If `uv` is unavailable, create a dedicated virtual environment and install the pinned SDK, Pillow, and socksio. Do not install into system Python by default.

## Subscription check failure

Do not assume Opus or zero cost. Check the API key, subscription status, network access, and NovelAI service health. Retry only after resolving the cause.

## Confirmation required

Read `error.details.estimated_anlas`. Present that value and a zero-Anlas alternative. After explicit confirmation, set `cost_policy.confirmed_paid` to true and rerun the same request.

## Zero Anlas required

Reduce only unspecified values. Typical alternatives are 1024×1024, 1216×832, or 832×1216; 28 steps or fewer; and one image per request. Never lower an explicit value without permission.

## Unknown cost

Do not execute unless the user confirms a paid operation. SDK 0.14.1 reports upscale pricing as unknown. `require_zero_anlas: true` always blocks unknown pricing.

## Rate limit or server error

Avoid automatic retries when the server may have completed a billed request. If completion is ambiguous, report the uncertainty. Retry at most once only when failure clearly occurred before generation began.

## Path outside project

Copy the source image into the current project and update the request path. This prevents accidental uploads of unrelated local files.

## Invalid parameters

Read the SDK validation error and compare the request with [parameters.md](parameters.md). Do not silently drop unknown or invalid fields.

## Output inspection failure

Keep generated files and metadata. Report which invariant could not be checked. For transparent output, inspect the alpha channel; for exact text, zoom in and verify every character.

## Content level violation

`CONTENT_LEVEL_VIOLATION` means the prompt exceeds the project level in `<agent dir>/novelai-content-level.json` (default level 2 when the file is missing). `details.violations` lists each rule and the offending tags. Remove or replace those tags, or add the missing negative exclusions (`required_negative`). Rules `fluids`, `nude_contact` and `embrace_ejaculation` come from project options, not the level (`embrace_ejaculation` also rejects semen with a drawn partner; placement is not checked). `male_genital` rejects exposed penis tags with a female character or POV contact. Do not rephrase tags to bypass the check. If the user wants a different level or option, run the `novelai-content-level` skill; never edit the file directly.

`INVALID_CONTENT_LEVEL` means the config file is malformed, or level 3 lacks confirmed `eocs_premises`. Re-run the `novelai-content-level` skill.
