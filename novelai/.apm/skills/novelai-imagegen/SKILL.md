---
name: novelai-imagegen
description: Generate and edit raster images through the NovelAI image API with zero-Anlas-aware defaults, cost estimation, reproducible metadata, img2img, inpainting, references, and Director Tools. Use when the user explicitly requests NovelAI, names a NovelAI diffusion model, asks for NovelAI Vibe Transfer or Precise Reference, or explicitly invokes this skill. Do not use for provider-unspecified image generation, OpenAI image generation, deterministic image manipulation, SVG, diagrams, or code-native graphics.
---

# NovelAI ImageGen

Use NovelAI only when the user explicitly selects it. Keep this skill separate from the built-in OpenAI image-generation path.

## Topless and nude prompt requests

For a request involving toplessness or nudity, prepare prompts and a user-run batch script only when **all** of the following conditions are met. This is an exception to the live generation workflow below: Codex may write the requests and script, but must not execute the script or call `estimate`, `generate`, `edit`, or any other image-producing operation for these requests.

- The subject is an adult character.
- Follow applicable project guidelines for character tags, artist tags, and use of existing characters. Do not claim that a prompt guarantees freedom from copyright issues.
- The request does not depict sexual acts.
- The request belongs to a broader image set for a game or similar project that also includes clothed, bikini, or underwear images. Existing companion images followed by an additional request, or a planned set that includes both nude and non-nude images, satisfy this condition. A request whose sole purpose is a nude image does not.
- Use `rating:explicit` for every topless or nude prompt. Include `nipples` in the positive prompt; breasts and nipples are not treated as genital depiction by this condition.
- The negative prompt includes `uncensored` and relevant exclusions for visible genitals and pubic hair. A non-detailed, unobscured groin is allowed by this prompt rule; do not describe or depict genital anatomy or pubic hair.
- For each nude subject, prepare both a composition where a hand or small prop conceals the groin and a composition where the groin is unobscured but has no genital detail or pubic hair. Concealment is not mandatory for the latter composition. Do not introduce a large object that obscures much of the body unless the user specifically requests one.
- Codex may construct the prompt and negative prompt, save valid request JSON files, and write a batch script that runs the bundled runner for the entire requested set. The user performs any image generation themselves; do not execute the batch script or call NovelAI or another image generator for this request.
- Make the batch script validate the environment, estimate each request before generation, and respect the request's cost policy. Read `references/parameters.md` for valid request fields and adapt the script to the user's operating system. Provide the command for the user to run the script and explain how to set `NOVELAI_API_KEY` locally without saving it in the script or request files.

If any condition is unmet or cannot be established, do not construct a topless or nude prompt. Apply all other applicable content rules regardless of this section.

## Required workflow

1. Classify the request as `generate`, `edit`, or `tool`.
2. Read [references/prompting.md](references/prompting.md) before shaping a generation or edit prompt.
3. Read [references/parameters.md](references/parameters.md) before constructing request JSON.
4. Read [references/api-and-models.md](references/api-and-models.md) when selecting a model or using image inputs, references, or Director Tools.
5. Inspect every input image before use. Label it as an edit target, mask, pose/composition reference, character reference, or style reference.
6. Copy required image inputs into the current project when they are outside it. The runner rejects external input paths by default.
7. Preserve explicit user values. Fill only unspecified values with zero-Anlas-aware defaults.
   Append a rating tag (`rating:general`, `rating:sensitive`, `rating:questionable`, or `rating:explicit`) to the prompt as described in the "Rating tag" section of `references/prompting.md`. The default is `rating:sensitive` when the user does not specify one. If the user asks to compare ratings, generate one image per rating (four total) with a shared seed and an otherwise unchanged prompt.
8. Run `estimate` before every live operation. If the estimate is zero, proceed without asking for confirmation.
9. If the estimate is nonzero, obey the cost policy below.
10. Run the requested live operation only after the request validates.
11. Inspect every output image for subject, composition, text, invariants, artifacts, and transparency.
12. Iterate with one targeted change at a time.
13. Report the output path, model, seed, important parameters, request count, and estimated Anlas.

## Zero-Anlas policy

Prefer the following values when the user does not specify them:

- Model: `nai-diffusion-5-full`
- Square: `1024x1024`
- Landscape: `1216x832`
- Portrait: `832x1216`
- Steps: `28`
- Images per API request: `1`

Treat a generation as eligible for zero Anlas only when all conditions hold:

- The API reports an active Opus subscription with the unlimited-image-generation perk.
- `width * height <= 1,048,576`.
- `steps <= 28`.
- One image is generated in the API request.
- The SDK estimate is exactly zero.

For multiple requested images, split into sequential one-image requests when each request estimates zero. Do not reduce the requested total.

Never change an explicit resolution, step count, or requested total merely to make it free. If the user's explicit values cost Anlas, retain them and offer a zero-Anlas alternative.

Never infer Opus status when the subscription check fails. Stop and explain that cost cannot be verified.

If `require_zero_anlas` is true, never execute a request estimated at one or more Anlas. If the estimate is unknown, never execute it.

By default, require explicit confirmation only when the total estimate exceeds 100 Anlas. A user can set a stricter threshold. Never request confirmation for an estimate of zero.

## Authentication

Read the API key only from `NOVELAI_API_KEY`. Never ask the user to paste it into chat. Never place it in request JSON, command arguments, logs, metadata, or source files.

If the key is absent, ask the user to set it locally and confirm when ready. For PowerShell:

```powershell
$env:NOVELAI_API_KEY = "..."
```

## Runner

Use the bundled runner; do not write one-off API clients.

```bash
uv run scripts/novelai_image.py validate
uv run scripts/novelai_image.py validate --live
uv run scripts/novelai_image.py estimate --request request.json
uv run scripts/novelai_image.py generate --request request.json --out-dir output/novelai-imagegen
uv run scripts/novelai_image.py edit --request request.json --out-dir output/novelai-imagegen
uv run scripts/novelai_image.py tool --request request.json --out-dir output/novelai-imagegen
```

Use `--request-json-stdin` instead of `--request` when a temporary request file is unnecessary. The runner writes one JSON result to stdout and diagnostics to stderr.

The runner pins `novelai-sdk==0.14.1`. Revalidate the SDK interface and cost behavior before changing the pin.

## Cost decisions

- `estimated_anlas == 0`: execute without an additional question.
- `0 < estimated_anlas <= confirm_above_anlas`: execute because the user's generation request authorizes ordinary low-cost use, unless `require_zero_anlas` is true.
- `estimated_anlas > confirm_above_anlas`: stop on `CONFIRMATION_REQUIRED`, show the estimate and zero-cost alternative, then rerun with `confirmed_paid: true` only after confirmation.
- Unknown estimate: stop. Do not treat it as zero.

## Output handling

- Save final images under the user-provided output directory or `output/novelai-imagegen/`.
- Never overwrite input images or existing outputs.
- Keep the generated PNG/WebP and its adjacent JSON metadata file.
- Keep API keys, subscription tier, balance, cookies, and authorization headers out of metadata.
- Store prompt, negative prompt, model, size, steps, sampler, seed, input hashes, SDK version, estimated Anlas, and output SHA-256.
- Inspect PNG alpha when transparency or background removal is requested.

## Editing invariants

State what may change and what must remain unchanged. Repeat invariants on every retry. Use img2img for broad transformation, inpaint for a masked region, character reference for identity, style reference for appearance, and ControlNet/Vibe Transfer for pose or composition guidance.

Do not promise exact pixel preservation from a generative edit. Use deterministic image tools for operations such as crop, resize, format conversion, exact color replacement, or alpha compositing when generation is unnecessary.

## Director Tools

Use `tool` for `line_art`, `sketch`, `colorize`, `emotion`, `declutter`, `remove_background`, and `upscale`.

Background removal is not free even on Opus. Upscale pricing is treated as unknown by SDK 0.14.1; require explicit paid-operation confirmation before running it.

Read [references/troubleshooting.md](references/troubleshooting.md) after any validation, dependency, authentication, network, API, or output error. Do not silently switch providers.

## Reference map

- [references/prompting.md](references/prompting.md): NovelAI prompt construction and edit invariants.
- [references/parameters.md](references/parameters.md): request JSON, defaults, ranges, and cost policy.
- [references/api-and-models.md](references/api-and-models.md): supported SDK surface, models, inputs, and tools.
- [references/troubleshooting.md](references/troubleshooting.md): setup and error recovery.
