---
name: tetris-spec-interviewer
description: Interview users before implementing a Tetris game by reading project-root Markdown specifications such as tetris-guideline.md and rotation-systems-legacy.md, extracting unresolved choices, and asking focused Japanese questions about Guideline SRS, legacy Sega/Atari/TGM rotation modes, controls, scoring, modes, UX, and implementation scope.
---

# Tetris Spec Interviewer

## Purpose

Use this skill to turn local Tetris specification Markdown files into a concise implementation interview. The goal is to clarify what kind of Tetris game to build before writing code.

## Workflow

1. Locate Markdown specification files in the project root first. Prioritize files whose names include `tetris`, `guideline`, `rotation`, `ars`, `sega`, `atari`, or `legacy`.
2. Read the relevant files directly. Do not rely on memory when the local files are available.
3. If both Guideline and legacy rotation documents exist, treat the Guideline document as the default modern mode and the legacy document as optional alternate modes.
4. Load `references/question-bank.md` for the interview structure.
5. Ask in Japanese unless the user asks for another language.
6. Start with high-impact choices. Avoid sending a huge questionnaire all at once; ask 5-8 grouped questions, then continue based on answers.
7. When the user answers, summarize confirmed decisions and list remaining open decisions.
8. Finish by producing an implementation-ready specification summary with clear defaults, accepted options, and explicitly deferred features.

## Interview Priorities

Always clarify these decisions early:

- Target ruleset: Guideline SRS, TGM/ARS, Sega, Atari, or multiple selectable modes.
- Platform and UI: browser, desktop app, canvas, React, mobile support, keyboard/gamepad.
- Core mechanics: matrix size, rotation system, randomizer, hold, next queue, ghost piece, drops, lock delay.
- Game modes: Marathon, Sprint, Ultra, B-type, Master/TGM-style, or custom.
- Scoring and recognition: T-Spin, Back-to-Back, Combo, Perfect Clear, grade system.
- Difficulty and timing: gravity curve, DAS, ARR, ARE, lock delay, line clear delay.
- Visual/audio scope: colors, effects, countdown, pause, sound, accessibility.
- Legal/product naming: avoid presenting an unofficial clone as an official licensed Tetris product unless licensing is explicitly part of the project.

## Defaults

When the user wants a standard modern implementation and does not specify otherwise, recommend:

- Guideline-style rules: 10x40 matrix with visible 10x20 area, SRS, 7-bag, hold, 6-piece next queue, ghost piece, hard/soft drop.
- Modes: Marathon first, then Sprint and Ultra if time permits.
- Scoring: Single/Double/Triple/Tetris, T-Spin, Back-to-Back, Combo, Perfect Clear, drop points.
- Handling: 60fps timing, DAS about 167 ms, ARR about 33 ms, lock delay about 0.5 seconds with 15 reset cap.
- UI: keyboard controls first, gamepad optional.

If the user asks for retro, arcade, or TGM feel, switch the questions toward Sega/TGM/Atari choices instead of assuming Guideline compliance.

## Output Shape

For each interview round, use this structure:

```markdown
Questions to confirm:
1. ...
2. ...

Current draft specification:
- ...

Open decisions:
- ...
```

For the final handoff, use this structure:

```markdown
Implementation specification summary

Confirmed decisions:
- ...

Deferred or out of scope:
- ...

Implementation notes:
- ...
```
