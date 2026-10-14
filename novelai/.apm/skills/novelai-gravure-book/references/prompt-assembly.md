# Prompt assembly and spec keys

## Prompt order (never reorder: it changes the composition under a fixed seed)
`scene, base_tags, appearance (source tag first, weighted), character.expression, outfit, shot tags, pose tags, append_pose, back tags (facing back), covered tags (variant covered), pose expression (+ exposed_expression from topless on), gaze, body, style, rating`

`outfit` = the cut's `outfit` if given, else the chapter's (the cover's own for the cover).

## Negative order
`character.negative, cut.negative, class negative (clothed_negative or exposed_negative), shot negative, common_negative`

## Spec
- top: `project`, `title`, `theme` (slug for the user-run folder), `defaults`, `poses`, `character`, `cover`, `chapters`.
- `defaults`: `model`, `steps`, `scale`, `rating`, `require_zero_anlas`, `base_tags` (must contain an adult tag), `gaze`, `style`, `covered_tags`, `back_tags`, `exposed_expression`, `clothed_negative`, `exposed_negative`, `common_negative` (must contain `child`), `shots` (id -> `{tags, orientation, negative}`; built-ins: closeup, upper, cowboy, full, lying).
- `poses`: id -> `{tags, expression}`.
- `character`: `name` (`[A-Za-z0-9_-]`, folder name), `seed`, `appearance` (with a bangs tag), `expression`, `body`, `negative`, optional `source` (see existing-characters.md).
- `cover`: `label`, `class` (clothed/partial/swimsuit/underwear), `scene`, `scene_private`, `outfit`, `pose`, `shot`, optional `negative`, `append_pose`, `seed`, `orientation`, `note`.
- `chapters[]`: `id`, `title`, `scene`, `scene_private`, `outfit`, `mode` (`cuts`|`strip`), `cuts[]`.
- `cuts[]`: `id`, `label`, `class`, `pose`, `shot`, `outfit` (required in `strip`), `negative`, `append_pose`, `facing` (front|back, required for topless/bottomless/nude), `crotch` (covered|open|both, required for bottomless/nude), `seed`, `orientation`, `rating`, `note`.

## Rating tags
clothed/partial/swimsuit/underwear: `rating:<defaults.rating>`; topless/nude: `rating:explicit, nipples`; bottomless: `rating:explicit`.

## File names
`<character>-cover[-note][-vN]-seed<seed>.png`, `<character>-<chapter>-<cut>[-covered|-open][-note][-vN]-seed<seed>.png`; metadata in `manifest/<stem>.json`.
