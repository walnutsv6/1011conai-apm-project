# NovelAI prompting

## Build the prompt

Preserve the user's requested content. Normalize it in this order:

1. Scene or background
2. Main subject and count
3. Pose, action, clothing, and important attributes
4. Composition and camera
5. Lighting, mood, palette, and medium
6. Required constraints

Use concise Danbooru-style tags for concrete visual attributes. Use natural-language phrases when relationships, layout, or an unusual action need explanation. Do not add extra characters, objects, brands, slogans, or narrative events.

Use `quality: true` instead of padding the prompt with redundant quality tags unless a model-specific test proves otherwise.

## Rating tag

Append exactly one rating tag to the end of the positive prompt of every `generate` request (and of `edit` requests that use a prompt). Choose it as follows:

For topless or nude requests that meet the conditions in `SKILL.md`, use `rating:explicit` and include `nipples` in the positive prompt. This exception takes precedence over the default and rating comparison rules below.

| User specification | Appended tag |
| --- | --- |
| `general` | `rating:general` |
| `questionable` | `rating:questionable` |
| `sensitive` | `rating:sensitive` |
| `explicit` | `rating:explicit` |
| none | `rating:sensitive` (default; gave the finest detail in comparison tests) |
| `all` / compare / 4 patterns | one image per rating, all four |

Rules:

- Do not alter the rest of the prompt, the negative prompt, or any other parameter when applying a rating. The tag is the only difference between variants.
- If the user's prompt already contains a `rating:` tag, keep the user's value and do not add another.
- Do not infer a rating from the content; use the table above. Treat an explicit user rating as authoritative.

### Comparison mode (all four ratings)

When the user asks to compare ratings:

1. Fix the base prompt, negative prompt, model, size, steps, scale, and sampler.
2. Fix a single `seed` (pick one if unspecified, and reuse it) so that the rating tag is the only varying input.
3. Build four requests, differing only in the trailing rating tag: `rating:general`, `rating:sensitive`, `rating:questionable`, `rating:explicit`.
4. Run `estimate` and the live call for each as a separate one-image request, with `output.basename` suffixed by the rating (e.g. `scene-general`, `scene-sensitive`, `scene-questionable`, `scene-explicit`).
5. Inspect all four outputs and report them side by side in one table: rating, output path, seed, estimated Anlas.

## Negative prompt

Put exclusions in `negative_prompt`, not in the positive prompt. Include only relevant failure modes. Common starting point:

```text
bad anatomy, extra fingers, missing fingers, malformed hands, duplicate, text, watermark, logo
```

Do not exclude an element the user requested. For sprite or cutout work, add unwanted scenery only when a transparent or plain background is intended.

## Edits

State the change first, then list invariants. Example:

```text
Change only the helmet from red to bright blue. Preserve the character, face, pose, body proportions, uniform design, camera angle, crop, lighting, and background.
```

Use inpaint when the change has a clear mask. Use img2img for broad restyling. Use character reference when identity matters and style reference when visual treatment matters.

Repeat invariants on every retry. Change only one parameter or prompt detail per iteration.

## Multiple references

Assign each image exactly one documented role before constructing JSON:

- edit target
- inpaint mask
- character reference
- style reference
- pose or composition reference

Do not use an edit target merely as a style reference or vice versa.

## Text in images

Quote exact required text in the prompt and verify it visually. NovelAI may render text inaccurately. When exact typography matters, generate the visual without text and add it with a deterministic graphics tool afterward.

## Transparency

For transparent generation, set `straight_alpha: true` and `tag_hint_transparent_background: true` where supported, request an isolated subject, and inspect the saved alpha channel. For an existing image, use Director Tool `remove_background`; it is never zero Anlas.

## Game assets

Specify intended use, camera direction, pose, crop, background, and consistency constraints. For sprites, generate one pose at a time unless testing shows that a sheet preserves frame boundaries and anatomy. Save seeds and references for later matching.
