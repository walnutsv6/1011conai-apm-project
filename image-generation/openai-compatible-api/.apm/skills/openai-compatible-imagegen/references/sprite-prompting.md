# Prompting for 2D game assets

Image models draw illustrations by default. Sprites need a constrained, repeatable layout, so state the constraints explicitly and keep them identical across the set.

## Prompt skeleton

Write prompts in English, in this order:

1. **Asset type and use**: "2D game sprite of …", "game item icon of …", "seamless top-down grass tile".
2. **Subject**: one subject, with concrete shapes and colours ("a small round green slime with two white eyes").
3. **View and pose**: "side view facing right", "top-down", "3/4 isometric view", "front view, idle pose". Fix this for the whole set.
4. **Framing**: "single character, centred, full body visible, nothing cropped, small margin around it".
5. **Style anchor**: reuse one sentence verbatim across all assets, for example "clean pixel-art style, bold dark outline, flat cel shading, limited palette, no gradients". For non-pixel games: "flat vector cartoon style, thick outline, two-tone shading".
6. **Background**:
   - gpt-image with `--background transparent`: "transparent background, no shadow on the ground".
   - Otherwise: "solid flat #FF00FF magenta background, no gradient, no shadow, no floor". Pick a chroma colour that does not occur in the subject (magenta for green or blue subjects, green #00FF00 for pink or red ones).
7. **Exclusions**: "no text, no UI, no border, no watermark, no extra characters".

Example:
```
2D game sprite of a small round green slime monster with two white eyes, side view facing right, idle pose.
Single character, centred, full body visible, small margin around it.
Clean pixel-art style, bold dark outline, flat cel shading, limited palette, no gradients.
Transparent background, no ground shadow. No text, no border, no extra characters.
```

## Getting a consistent set

- Generate the **base** first, with a few candidates (`--n 2-3 --quality low`). Let the user pick one, then optionally re-run that prompt at higher quality.
- For each variant or animation frame, use `edit --image base.png` and describe only the change: "Same character, same proportions, colours and style. Change: left foot forward, mid-walk." On gpt-image add `--extra-json '{"input_fidelity": "high"}'`.
- Ask for one frame per request. Requests for a whole sheet in one image ("4 frames in a row") rarely land on an exact grid.
- Keep the same `--size` and background method for every frame, so `trim` and `pixelate` scale them equally. To keep relative scale (a small item next to a large character), skip `trim`, or trim and then `pixelate` with the same `--scale-factor` for all frames.
- Tiles: ask for "seamless tileable texture, top-down, edges continue across borders". Then check the tiling visually. The model does not guarantee seamlessness.
- Icons: "single item, centred, 3/4 view, thick outline, readable at 32×32 pixels".

## Pixel-art notes

Models produce pixel-art-looking images at high resolution, but the "pixels" are not on a clean grid. Use `postprocess.py pixelate` to the real target size (`--height 32`, `--colors 8`–`16`, or a project palette via `--palette`). Inspect the `--preview-scale` output, and fix single stray pixels by hand if needed.

## Content rules

- Do not name existing games, franchises, studios, or characters, or ask for "in the style of <living artist>". Describe the visual traits instead.
- Keep characters clearly non-sexual. This skill is for general game assets.
- The provider's moderation applies. Do not try to work around refusals; rephrase or ask the user.
