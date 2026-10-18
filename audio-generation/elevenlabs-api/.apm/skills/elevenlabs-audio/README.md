# elevenlabs-audio — Agent Skill

Install with APM (`apm install walnutsv6/1011conai-apm-project/audio-generation/elevenlabs-api --target <target>`). Restart the agent session if required to reload skills.

Python >=3.8 (stdlib-only). Optional FFmpeg for audio quality inspection and MP3→WAV/OGG conversions. API token via `ELEVENLABS_API_KEY` environment variable; do not commit tokens.

```powershell
python scripts/audio.py music --prompt 'Bright instrumental arcade racing electronic music' --seconds 10 --output output/race.mp3 --dry-run
python scripts/audio.py sfx --prompt 'Short crisp UI select blip' --seconds 2 --output output/select.mp3 --dry-run
```

Remove `--dry-run` to make a billable request; confirmation is required. To run without terminal interaction, `--yes` requires prior explicit authorization from the user.

Each successful generation emits `audio.mp3.json` containing prompt, user-based cost estimate, actual response `character-cost` if available, song ID where supplied, and optional FFmpeg volume inspection. By design, the tool does not retry errors or automatically regenerate quiet clips.

Known limitations: cost estimate is an observation, not guaranteed pricing. Volume inspection does not assess musical correctness or detect initial silence precisely. Audio output converts via ffmpeg without seamless-loop postprocessing.
