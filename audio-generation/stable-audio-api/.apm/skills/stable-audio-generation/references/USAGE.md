# Stable Audio 3.0 game BGM + SFX — operational reference

## Installation
Install with APM (`apm install walnutsv6/1011conai-apm-project/audio-generation/stable-audio-api --target <target>`). Restart the agent session if needed. Python 3.10+ is required. The Python script has no third-party Python dependencies. For local audio cleanup/conversion, install FFmpeg so `ffmpeg` is on PATH.

Set `STABILITY_API_KEY` in the process environment, not in files committed to source control. For example, in PowerShell: `$env:STABILITY_API_KEY = Read-Host -MaskInput "Stability API key"`. On macOS/Linux, use a secure shell prompt or secret manager. Don't paste API keys into chat.

## BGM mode (`--mode music`)
Music defaults to 60 sec, tags `TrackType: Music` if no TrackType tag exists. Prompts should cover genre, energy, tempo as approximate guidance, instrumentation, no vocals if instrumental, game scene, and a stable arrangement. Prompting cannot guarantee exact BPM, musical structure, or perfect loops.

```bash
python scripts/stable_audio.py generate --mode music --prompt "Instrumental jazzy arcade baseball team selection BGM, warm Rhodes piano, syncopated bass, bright restrained drums, no vocals" --duration 240 --format mp3 --output assets/audio/bgm/select.mp3
```

## SFX mode (`--mode sfx`)
SFX defaults to 3 sec, tags `TrackType: SFX` unless one already exists. Describe source, action, single event vs continuous ambience, texture, microphone perspective, decay, exclusion of unrelated music/voices. Choose length suited to the event. Output WAV for further cleanup, or MP3 for compact preview.

```bash
python scripts/stable_audio.py generate --mode sfx --prompt "Single bright retro arcade UI confirmation chime, short rising electronic blip, clean attack and quick decay, no background music" --duration 2 --format wav --output assets/audio/sfx/confirm.wav
python scripts/stable_audio.py generate --mode sfx --prompt "Isolated race car engine rising smoothly in pitch, no music and no other vehicles" --duration 12 --format wav --output assets/audio/sfx/engine_rev.wav
```

## Generating and resuming
`generate` is dry-run unless `--execute` is supplied. Every paid generation additionally requires `--approve-credits 8` (a local acknowledgment, NOT a billing cap). Obtain user approval for the specific run or capped batch. After submission, a metadata file `<output>.json` contains job ID and generation settings. If the command reports a pending job, poll using:

```bash
python scripts/stable_audio.py collect --metadata assets/audio/sfx/confirm.wav.json
```

Never automatically resubmit a request when a POST timed out; provider might have accepted it. Neither API balance checking nor current price verification is supported. The script refuses overwrites.

## Post-process locally (optional)
`process` requires FFmpeg only when `--execute` is specified. Dry-run previews the exact FFmpeg command. It never overwrites source or an existing target. Supported outputs: OGG (Vorbis), WAV, MP3. `--trim-silence` is only available for SFX and removes leading/trailing silence based on an approximate -45dB threshold. Beware very quiet tails; preview the processed file. `--normalize` uses FFmpeg `loudnorm` (single-pass, approximate). `--fade-out SECONDS` requires `--duration` specifying the **actual audio length** to position the fade correctly.

```bash
python scripts/stable_audio.py process --mode sfx --input assets/audio/sfx/confirm.wav --output assets/audio/sfx/confirm_clean.ogg --trim-silence --normalize
python scripts/stable_audio.py process --mode music --input assets/audio/bgm/select.mp3 --output assets/audio/bgm/select.ogg --normalize
```

Add `--execute` to carry out a chosen cleanup operation. Post-processing is not a seamless-loop generator; use a DAW or purpose-built loop editing workflow when required. No audio-to-audio, inpainting, bulk splitting, or engine integration is included.

## API and credits
- Official model: `stable-audio-3`; asynchronous text-to-audio creation followed by GET result polling.
- POST `https://api.stability.ai/v2beta/audio/stable-audio/text-to-audio`; GET `https://api.stability.ai/v2beta/audio/results/{id}`.
- `multipart/form-data`, `prompt`, `model`, `duration` (1–380 sec), `output_format` (mp3/wav), `seed`.
- The reference specifies **8 credits for a successful Stable Audio 3.0 generation**; confirmed by the user for 60 sec (500 → 492). The general pricing webpage lists a different 26-credit figure. The CLI doesn't impose a server-side spending cap.
- Check live billing and licence terms before large batches or commercial releases.

Sources:
- https://platform.stability.ai/docs/api-reference
- https://platform.stability.ai/pricing
- https://stability.ai/guides/stable-audio-3-prompt-guide
