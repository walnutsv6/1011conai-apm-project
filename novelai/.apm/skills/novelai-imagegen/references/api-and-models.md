# SDK and model reference

This skill pins `novelai-sdk==0.14.1`, an unofficial MIT-licensed client. Recheck its public documentation and PyPI release before updating.

## Supported models in SDK 0.14.1

- `nai-diffusion-5-full`
- `nai-diffusion-5-curated`
- `nai-diffusion-4-5-full`
- `nai-diffusion-4-5-curated`
- `nai-diffusion-4-full`
- `nai-diffusion-4-curated`
- `nai-diffusion-3`
- `nai-diffusion-3-furry`

Default to `nai-diffusion-5-full` for new work unless the user names another model or a tested workflow requires one.

## Client surface

- Generate: `client.image.generate(GenerateImageParams(...))`
- Subscription: `client.user.get_subscription()`
- Actual Anlas balance: `client.user.get_anlas()`
- Cost estimate: `params.calculate_anlas(is_opus=...)`
- Director Tools: `client.tools.augment(params)`
- Upscale: `client.tools.upscale(UpscaleParams(...))`

The subscription response exposes `active`, `is_opus`, `tier_name`, `anlas`, and `perks.unlimited_image_generation`. Reuse one response instead of requesting it repeatedly.

## Zero-Anlas generation

Check active Opus status, no more than 1,048,576 pixels, no more than 28 steps, one image per API request, and an SDK estimate of zero. The estimate is best effort and not a billing guarantee.

| Orientation | Size | Pixels |
| --- | ---: | ---: |
| Square | 1024 × 1024 | 1,048,576 |
| Landscape | 1216 × 832 | 1,011,712 |
| Portrait | 832 × 1216 | 1,011,712 |

## Image inputs

- `I2iParams`: image, strength 0.01–0.99, noise 0–0.99
- `InpaintParams`: image, mask, strength 0.01–1.0
- `CharacterReference`: image, type, fidelity 0–1, strength 0–1
- `ControlNetImage`: image, info extracted, strength, model

The SDK accepts paths, bytes, base64, PIL images, or arrays. The runner intentionally accepts project-local file paths only.

## Director Tools

| Tool | Purpose | Important cost note |
| --- | --- | --- |
| `line_art` | Extract line art | May be free on active Opus within the area limit |
| `sketch` | Produce a sketch | May be free on active Opus within the area limit |
| `colorize` | Colorize input | Supports prompt and defry |
| `emotion` | Change expression | Supports emotion, prompt, and defry |
| `declutter` | Remove text and effects | Can preserve speech bubbles |
| `remove_background` | Remove background | Never free, including Opus |
| `upscale` | Fixed 2× upscale | SDK 0.14.1 cannot estimate its price |

Background removal returns three outputs: masked, generated, and blend.

## Sources

- https://caru-ini.github.io/novelai-sdk/docs/
- https://caru-ini.github.io/novelai-sdk/docs/user-account/
- https://caru-ini.github.io/novelai-sdk/docs/anlas-calculation/
- https://caru-ini.github.io/novelai-sdk/docs/director-tools/
- https://pypi.org/project/novelai-sdk/
- https://image.novelai.net/docs/
