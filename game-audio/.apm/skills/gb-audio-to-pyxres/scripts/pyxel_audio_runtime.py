"""Standalone ROM-free loading and channel playback plans for exported audio."""

import json
from pathlib import Path
import zipfile


def load_audio(pyxel, path):
    path = Path(path)
    with zipfile.ZipFile(path) as archive:
        manifest = (json.loads(archive.read("gb_audio.json")) if "gb_audio.json" in archive.namelist()
                    else json.loads(path.with_suffix(".json").read_text(encoding="utf-8")))
    if manifest.get("format_version") != 1 or "clips" not in manifest:
        raise ValueError("Unsupported GB audio resource")
    pyxel.load(str(path))
    tones = list(pyxel.tones[:manifest["tone_base"]])
    for definition in manifest["tones"]:
        tone = pyxel.Tone()
        tone.mode = definition["mode"]
        tone.sample_bits = definition["sample_bits"]
        tone.wavetable[:] = definition["wavetable"]
        tone.gain = definition["gain"]
        tones.append(tone)
    pyxel.tones[:] = tones
    for bank, tone_sequence in manifest["sound_tones"].items():
        pyxel.sounds[int(bank)].tones[:] = tone_sequence
    # Read the native music data so editor changes to sequence lists can apply.
    for clip in manifest["clips"].values():
        sequences = [list(s) for s in pyxel.musics[clip["music"]].seqs[:4]]
        clip["channels"] = sequences + [[] for _ in range(4 - len(sequences))]
    return manifest


def channel_plan(pyxel, manifest, name, channel, elapsed):
    if not 0 <= channel < 4 or elapsed < 0:
        raise ValueError("Invalid playback channel/time")
    clip = manifest["clips"][name]
    sounds = clip["channels"][channel]
    if not sounds:
        return None
    intro = clip["intro_ticks"][channel] / manifest["tick_rate"]
    loop = clip["loops"][channel]
    boundary = None
    if intro:
        if elapsed < intro:
            loop = False
            boundary = intro
        else:
            sounds = sounds[1:]
            elapsed -= intro
    duration = sum(pyxel.sounds[bank].total_sec() or 0 for bank in sounds)
    if not duration or not loop and elapsed >= duration:
        return None
    return dict(sounds=sounds, sec=elapsed % duration, loop=loop, next_boundary=boundary)
