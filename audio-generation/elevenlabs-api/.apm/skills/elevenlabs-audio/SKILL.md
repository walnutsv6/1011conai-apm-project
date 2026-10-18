---
name: elevenlabs-audio
description: Generate game background music and sound effects through ElevenLabs Music and Sound Effects APIs with explicit credit approval, logging, and optional ffmpeg quality inspection. Use for game audio asset creation and integration.
---

# ElevenLabs Game Audio

Use `scripts/audio.py` for all actual API generation. Python 3.8+ and `ELEVENLABS_API_KEY` are required. `ffmpeg` is optional for volume inspection and required for `.ogg`/`.wav` output. Never print/store the API key.

## Required workflow

1. Clarify the project audio purpose, duration, style, output path, and whether instrumental/looped. Prefer English prompts. Do not include actual performer/song names in music prompts; review ElevenLabs Music Terms before distribution.
2. Call `python scripts/audio.py <music|sfx> ... --dry-run` first. Dry-run is local only, not an API authentication test.
3. Show estimated credit consumption before generating, emphasizing that the estimate is not an official price quote. For this user's observed account, BGM `12.5 credits/sec` (one 10 s job) and SFX `10 credits/sec` (three jobs) are provisional defaults. Confirm costs in dashboard if rates change.
4. **Do not make a paid generation request without explicit approval for that request**. For interactive users the script asks for literal `YES`. Only use `--yes` after the user explicitly authorized the particular job, never because the agent can issue commands autonomously. Do not recursively retry failed/ambiguous requests.
5. After generation, report the audio path, metadata JSON path, response `character-cost` if returned, and audio quality warnings. Listen/review before adopting assets. For SFX, earlier bat impact clip was almost inaudible despite valid MP3: check peak and prompt timing; no automatic paid regeneration.
6. Modify or integrate into the target game **only at user's request**. Never overwrite existing assets without separate approval.

## Commands

```powershell
$env:ELEVENLABS_API_KEY = 'YOUR_KEY'  # use a secret manager/environment; never commit it
python scripts/audio.py music --prompt 'Instrumental arcade racing fusion, no vocals' --seconds 30 --output assets/audio/race.mp3 --dry-run
python scripts/audio.py music --prompt 'Instrumental arcade racing fusion, no vocals' --seconds 30 --output assets/audio/race.ogg
python scripts/audio.py sfx --prompt 'Immediate crisp short menu confirm synth blip, clean attack' --seconds 2 --output assets/audio/select.wav --dry-run
python scripts/audio.py sfx --prompt 'Steady high-rev engine at constant RPM, no gear changes' --seconds 5 --loop --output assets/audio/engine.ogg
```

Supports `--max-estimated-credits`, `--prompt-influence` (SFX), `--allow-vocals` (music), `--no-analysis` and `--ffmpeg`. No automatic repeats, no parallel mass generation, and no undocumented spend.

## Quality and licensing

If installed, ffmpeg measures decoded audio mean and peak dBFS; peak below -35 dBFS triggers a warning. Not a guarantee of meaningful content. No audio normalization or automatic loop smoothing; `.ogg` conversion preserves audio but does not itself make loops gapless. Generated music may need editorial processing. Game licensing depends on account-specific terms. See `references/api-and-rights.md`.
