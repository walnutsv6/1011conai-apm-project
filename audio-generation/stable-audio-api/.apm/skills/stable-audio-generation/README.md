# Stable Audio game assets — Agent Skill v1.2

Generate **BGM/music** and **sound effects (SFX)** via Stability AI's Stable Audio 3.0 asynchronous text-to-audio API. Includes cost-aware dry-run defaults, job recovery, metadata, and optional local FFmpeg SFX cleanup / OGG conversion.

## Install

Install with APM (`apm install walnutsv6/1011conai-apm-project/audio-generation/stable-audio-api --target <target>`). Restart the agent session if needed. Python 3.10+ required; no extra Python packages. FFmpeg required only for `process --execute`.

Get API key at https://platform.stability.ai/account/keys and set `STABILITY_API_KEY` in the agent's process environment. Do not store or share the key in prompts or a Git repository.

See `SKILL.md` and `references/USAGE.md` for command examples, billing cautions and troubleshooting.

## Examples

```bash
# No API requests until --execute --approve-credits 8
python scripts/stable_audio.py generate --mode music --duration 240 --format mp3 --prompt "Instrumental jazzy sports game team selection BGM, warm electric piano, upbeat drums, no vocals" --output game/audio/select.mp3
python scripts/stable_audio.py generate --mode sfx --duration 3 --format wav --prompt "Single wooden baseball bat crack, clean close-up hit, no background sound" --output game/audio/bat.wav

# Optional postprocessing: dry run by default; add --execute to apply
python scripts/stable_audio.py process --mode sfx --input game/audio/bat.wav --output game/audio/bat.ogg --trim-silence --normalize
```

Rate estimate: 8 API credits per successful generation, based on official API reference and the user's observed 60-second generation. Pricing may change; live usage is not queried by this Skill.
