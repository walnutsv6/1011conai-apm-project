---
name: novelai-gravure-book
description: Build a gravure-photobook style CG collection (cover + chapters of cuts, clothes to nude) for one fixed adult character with NovelAI, either an original character or one inspired by an existing adult character. Proposes chapters, cuts and camera shots for the user to choose, fixes the seed, and writes requests, prompts.md, user-run scripts and a page-turning book viewer (index.html). The agent generates only the clothed cover; every body page is prompt + user-run script. Sub-skill of novelai-imagegen. Use when the user asks for a gravure / photobook / CG-collection set via NovelAI. Do not use for a single image (use novelai-imagegen), an outfit x pose matrix (use novelai-variations) or a one-pose undressing ladder (use novelai-strip-sequence).
---

# NovelAI Gravure Book (cover + chapters)

Sub-skill of `novelai-imagegen`, sibling of `novelai-variations` and `novelai-strip-sequence`. It only **designs and batches the prompts and builds the viewer**; estimates, cost decisions, authentication and live calls belong to the `novelai-imagegen` runner. Read `../novelai-imagegen/SKILL.md` first (its topless/nude section governs this skill), then `../novelai-imagegen/references/sexual_content_guidelines.md` **before** proposing anything. If the request deviates from the guideline (minor-looking character, sex acts, forced/unwilling framing, public place), stop and say so instead of building it.

## Concept

A book is `cover + chapters[]`; a chapter is a scene + outfit + ordered `cuts[]`; a cut is `class x pose x shot (x nude composition)`.

- **Character**: one per book (fixed appearance block incl. a bangs tag, body, base expression, **fixed seed**). Several books may exist side by side, each with its own folder.
- **Chapter** `mode: cuts` (same outfit, different poses and camera shots: the photobook default) or `mode: strip` (cuts are ordered undressing steps; every cut carries its own `outfit`).
- **Cut classes**: `clothed`, `partial`, `swimsuit`, `underwear`, `topless`, `bottomless`, `nude`.
- **Shots**: `closeup`, `upper`, `cowboy`, `full`, `lying` (landscape); add or override in `defaults.shots`.
- Only background mode (`bg`); no transparent versions.

## Who generates what

| page | class | who |
| --- | --- | --- |
| cover | clothed / partial / swimsuit / underwear only | **the agent** (estimate, then generate) |
| every body cut | any, including clothed | **the user**, with the scripts you prepare |

The cover is never topless/bottomless/nude (`build_requests.py` aborts). With a non-exposed cover, the body chapters may be anything up to and including all-nude: the set still contains a clothed image, so it is not a nude-only set.

**Never run, estimate or generate body requests yourself.** Write the requests and the scripts, hand over the commands, and stop. Do not claim anything about images the user generated. Do not run `run.ps1` / `run.sh` (they generate); `update-book.*` only rebuilds the HTML and may be run by the agent or the user.

## Hard rules (from the project guideline)

- Characters are adults in setting **and** impression. `defaults.base_tags` keeps an adult tag; `common_negative` keeps `child, loli`. Costumes such as school uniforms are adult cosplay. If the character looks like a minor, do not make the book at all (clothed cuts included), and never add youthful tags when re-rolling.
- Existing characters: see [references/existing-characters.md](references/existing-characters.md). Original-by-inspiration, adult source only, never real people.
- Self-directed, non-sexual-act framing only. Never add sex acts, forced/unwilling cues, genital detail or pubic hair. Hands or small props over breasts/groin are fine. Gestures such as taking off a jacket or unhooking a bra are fine.
- Backgrounds from `underwear` onward (cover included) must be private, hard-to-enter spaces (hotel suite, bedroom, private pool, own room...). Set `scene_private: true`; the script aborts otherwise. No streets or places a third party could enter. A rooftop pool is fine only if the scene says nobody is around.
- `bottomless` / `nude` cuts need `crotch`: `covered` (hand or small prop), `open` (unobscured, no genital detail/pubic hair) or `both` (guideline default when the pose is unspecified). `topless` / `bottomless` / `nude` cuts need `facing`: `front` or `back`.
- Exposed classes add `rating:explicit` (+ `nipples` unless bottomless) and a negative with `uncensored` plus genital/pubic-hair exclusions. These do not guarantee the result: the user must look at every image (age impression, consistency, composition, background, excluded elements).
- Ratings (age labels) are not shown in outputs.

## Workflow

In the commands below, `<skills-root>` is the installed skills directory (`.claude/skills` for Claude, `.agents/skills` for Codex/Copilot).

1. **Hear the requirements, then propose candidates.** Ask for what is missing:
   - Theme/concept and use (gravure CG set, game reward, both).
   - **Character**: propose an adult original (with a bangs tag and a seed), or, for an existing character, confirm the canon age first (see the reference). Use `novelai-character-extract` if the user supplies a reference image.
   - **Cover**: not exposed. Outfit, pose, shot, scene.
   - **Chapters**: how many, and per chapter the scene, outfit(s), number of cuts, `cuts` or `strip`. Offer the chapter templates in [references/book-structure.md](references/book-structure.md) as inspiration, not defaults.
   - **Worn items in detail** (per chapter, layer by layer: type, colour, material, length, accessories, what stays on in the nude cuts). Summarise as a layer table and confirm before writing tags.
   - **Facing (front / back)** for every cut where underwear, a bra or a bikini is taken off, and every cut after it. Ask per cut with `AskUserQuestion`; never decide it yourself. Recommend back for the gesture of unhooking a bra or untying a strap. Ask again when cuts are added or revised. Use two cuts if the user wants both.
   - **Nude composition** (`covered` / `open` / `both`) per nude/bottomless cut; a back-facing cut hides the groin, so `open` alone is enough there. A knee-hug nude pose is only an on-request variation, never in the default set.
   - **Private scene** per chapter.
   - Example: [examples/spec.example.json](examples/spec.example.json) (inspiration only). Spec keys and prompt order: [references/prompt-assembly.md](references/prompt-assembly.md).
2. **Write the spec** as JSON, e.g. `output/novelai-imagegen/<project>/spec.json` (chapter/cut ids use `[A-Za-z0-9_]` only; they become part of file names).
3. **Build the requests**:
   ```bash
   python <skills-root>/novelai-gravure-book/scripts/build_requests.py --spec <spec.json> --project-dir output/novelai-imagegen/<project> [--user-run-dir user-run-scripts] [--chapter cover,ch2] [--suffix v2]
   ```
   - Cover -> `<project>/requests/`. Every body cut -> `user-run-scripts/<character>-<theme>/requests/`, with `run.ps1`, `run.sh`, `update-book.ps1`, `update-book.sh` and `README.txt` next to it (never under `output/`). A new request or revision gets a new folder (new `theme`); do not mix into an old one.
   - Also writes `<project>/manifest.json` (every page cell, in order) and `<project>/prompts.md`.
   - Existing request files are never overwritten; use `--suffix v2` for a revision.
4. **Review `prompts.md`** with the user (cover, one cut per class, both nude compositions).
5. **Generate the cover only** (estimate first, zero-Anlas policy of `novelai-imagegen`):
   ```bash
   python <skills-root>/novelai-gravure-book/scripts/has_output.py --request <project>/requests/<c>-cover.request.json --out-dir <project>/images || \
   (uv run <skills-root>/novelai-imagegen/scripts/novelai_image.py estimate --request <that.json> && \
    uv run <skills-root>/novelai-imagegen/scripts/novelai_image.py generate --request <that.json> --out-dir <project>/images)
   ```
   Inspect it. Fix with a *targeted* change (see Fix patterns), moving the old take and its `manifest/<stem>.json` to `images/<character>/superseded/`.
6. **Build the viewer** (after the cover and after every later change):
   ```bash
   python <skills-root>/novelai-gravure-book/scripts/build_book.py --project-dir output/novelai-imagegen/<project> [--title "<title>"]
   ```
   Writes `<project>/index.html`: cover, contents, chapter title pages and 2-cut spreads, page turning by arrow keys / swipe / buttons, view switch `all / covered / open`, "images only" toggle, click-to-zoom, light/dark. Body cuts without an image show a dashed "ユーザー生成枠" frame. Latest `vN` wins; `superseded/` is ignored.
7. **Hand over**, then stop: the path of `user-run-scripts/<character>-<theme>/`, the run command (PowerShell: `$env:NOVELAI_API_KEY = "<key>"` then `powershell -ExecutionPolicy Bypass -File <dir>/run.ps1`; bash: `export NOVELAI_API_KEY=...` then `bash <dir>/run.sh`), and the HTML-only command (`update-book.ps1` / `.sh`, no key). The key stays in the user's shell session, never in a file. `run.*` skips existing images, estimates each request, generates into `<project>/images/<character>/`, then rebuilds the HTML. Remind the user to check every result by eye.
8. **Report**: index.html path, counts (cover + chapters x cuts), seed, cover estimate, script paths, what the user still has to run. Do not claim success for images not inspected.

## Fix patterns (change one thing, keep the seed)

| Symptom | Fix |
| --- | --- |
| Removed garment reappears | Add it to that cut's `negative` (and every later cut's). |
| Pose or composition drifts | Change only that cut's `pose` / `append_pose` / `shot`; never reorder the rest of the prompt (it changes the composition under a fixed seed). |
| `covered` shows the hand in the wrong place | Change `defaults.covered_tags` or use `append_pose` (e.g. `holding pillow`), small props only. |
| Bangs / hair colour / skin drift | Bangs tag in `appearance`; opposite colours in the character `negative`; regenerate. |
| Garment colour drifts between cuts | Prefix the tag with `solid dark <colour>` in the drifting cuts and add `light <colour> <garment>, gradient <garment>` to their `negative`. |
| Back-facing cut looks the other way | Add `looking back over left/right shoulder` to that cut's `append_pose`; do not flip the image. |
| Eyes closed by an expression tag | Pick another pose expression or add `closed eyes, half-closed eyes` to the cut's `negative`. |

**Revising user-run pages**: never overwrite the user's images or request files. Move old takes (png + `manifest/<stem>.json`) to `images/<character>/superseded/`, change the spec `theme` to a new slug, and run `build_requests.py --chapter <changed chapters>`; delete from the new folder any request for pages that need no rerun. Rebuild `index.html` once the user has run the script.

## Output layout

```
output/novelai-imagegen/<project>/
  spec.json, manifest.json, prompts.md
  requests/              # cover request (agent runs it)
  images/<character>/    # png (runner output), manifest/<stem>.json, superseded/
  index.html             # page-turning book viewer (build_book.py)
user-run-scripts/<character>-<theme>/
  run.ps1, run.sh        # generate body pages, then rebuild index.html
  update-book.ps1, .sh   # rebuild index.html only (no key)
  README.txt
  requests/              # all body cut requests
```
