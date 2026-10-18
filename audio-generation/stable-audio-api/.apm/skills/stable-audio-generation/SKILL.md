---
name: stable-audio-generation
description: Generate game BGM/music, jingles, and sound effects (SFX) using the official Stable Audio 3.0 API, collect pending jobs, and optionally post-process game audio with FFmpeg. Use when asked to make or prepare game audio assets. Requires STABILITY_API_KEY only for actual API requests.
---

# Stable Audio Generation — music and SFX

Run `scripts/stable_audio.py` using Python 3.10+. **Read `references/USAGE.md` before use** for limitations and command examples. No third-party Python libraries are required; optional post-processing requires `ffmpeg` executable.

## Workflow and safety
1. Select `--mode music` for BGM/jingles, or `--mode sfx` for UI hits, foley, sports impacts, engine samples, and ambience. Use precise English sound descriptions and avoid imitating identifiable existing songs. `TrackType: Music` or `TrackType: SFX` is automatically prepended unless an explicit `TrackType:` tag is already present. Do not incorrectly claim these tags guarantee results.
2. Defaults: 60 seconds for `music`; 3 seconds for `sfx`. Override with `--duration` (1–380 sec). MP3 is the default output format; WAV is also available. Specify unique output paths under the game's audio assets directory. Prefer `sfx` with a single isolated event and no music/voices where appropriate.
3. **Always dry-run** `generate` before paid requests. Present output path, duration, prompt, and estimated charge. API docs state **8 credits per successful generation** (confirmed by user test); the pricing webpage elsewhere mentions 26. Treat estimate as indicative, not a server-side spending cap.
4. Only after explicit approval for the particular generation/bounded batch (including maximum cost), run `generate --execute --approve-credits 8`; review current account billing before approval. Do not automatically repeat paid requests to improve quality.
5. Read `STABILITY_API_KEY` from environment. Never request secrets in chat or put them into files, CLI arguments, logs, or source control. API generation is non-idempotent; **do not automatically retry an ambiguous POST**. Use `collect` with the saved JSON metadata to resume a pending job, never a duplicate generate call.
6. `process` is separate and local. Default dry-run. Use `--execute` only on explicit user request to perform audio cleanup. `--trim-silence` can be used only with `--mode sfx`, so BGM intros/timing are not accidentally damaged. `--normalize`, `--fade-out` (with accurate `--duration`), OGG conversion are optional. `process` never overwrites source or destination. Inspect/preview audio before use; don't promise seamless loops or exact SFX durations.
7. Preserve JSON metadata with effective prompt, mode, seed, output and job ID. Check rights and commercial terms independently; no legal clearance is provided by this script.

## Commands

BGM dry run:
```bash
python scripts/stable_audio.py generate --mode music --prompt "Instrumental upbeat jazz fusion for a baseball team selection menu; no vocals, no opening drum fill" --duration 240 --format mp3 --output assets/audio/bgm/select.mp3
```

SFX dry run:
```bash
python scripts/stable_audio.py generate --mode sfx --prompt "One isolated crisp wooden baseball bat hit, dry close-up impact, quick decay, no music or crowd" --duration 3 --format wav --output assets/audio/sfx/bat_hit.wav
```

After an authorized cost review, add `--execute --approve-credits 8` to a generate command. Restore pending results without charging for new generation:
```bash
python scripts/stable_audio.py collect --metadata assets/audio/sfx/bat_hit.wav.json
```

Optionally remove silence, normalize and convert a completed SFX to OGG (requires FFmpeg), dry-run first:
```bash
python scripts/stable_audio.py process --mode sfx --input assets/audio/sfx/bat_hit.wav --output assets/audio/sfx/bat_hit_clean.ogg --trim-silence --normalize
```
Then add `--execute` to perform the local operation.

## Not implemented
Audio-to-audio generation, inpainting, real-time account balance queries, bulk asset slicing, batch API generation, waveform-exact looping/crossfading, server-enforced credit ceilings, automatic licensing determinations, and autoplay/listening checks. Do not pretend these features are available.
