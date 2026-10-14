"""Convert game-specific GB register traces to standalone Pyxel audio data."""

import argparse
import json
import math
from fractions import Fraction
from pathlib import Path
import zipfile

from gb_apu import ApuControl, GB_FRAME_RATE, TICK_RATE, ToneRegistry


def integer(value, label, low=0, high=None):
    if isinstance(value, bool) or not isinstance(value, int) or value < low or high is not None and value > high:
        raise ValueError(f"Invalid {label}: {value!r}")
    return value


def bake_document(document, gain=0.3):
    if document.get("format_version") != 1:
        raise ValueError("Unsupported input format_version")
    rate = document.get("frame_rate", GB_FRAME_RATE)
    if isinstance(rate, bool) or not isinstance(rate, (int, float)) or not math.isfinite(rate) or rate <= 0:
        raise ValueError("frame_rate must be positive and finite")
    if not math.isfinite(gain) or gain <= 0:
        raise ValueError("gain must be positive and finite")
    tracks = document.get("tracks")
    if not isinstance(tracks, list) or not tracks:
        raise ValueError("tracks must be a nonempty list")
    tones = ToneRegistry(gain)
    result = {}
    for track in tracks:
        name = track.get("name")
        if not isinstance(name, str) or not name.strip() or name in result:
            raise ValueError("Track names must be nonempty and unique")
        frames = integer(track.get("frames"), "frames", 1)
        writes = track.get("register_writes")
        if not isinstance(writes, list):
            raise ValueError(f"{name}: register_writes must be a list")
        normalised = []
        previous_frame = -1
        for row in writes:
            if not isinstance(row, (list, tuple)) or len(row) != 3:
                raise ValueError(f"{name}: expected [frame, register, value]")
            frame = integer(row[0], "write frame", 0, frames)
            register = integer(row[1], "register")
            value = integer(row[2], "register value", 0, 255)
            if register >= 0xFF00:
                register -= 0xFF00
            if not (0x10 <= register <= 0x26 or 0x30 <= register <= 0x3F):
                raise ValueError(f"{name}: unsupported APU register {row[1]:#x}")
            if frame < previous_frame:
                raise ValueError(f"{name}: register writes must be chronological")
            normalised.append((frame, register, value))
            previous_frame = frame
        loops = {}
        for channel, bounds in track.get("channel_loops", {}).items():
            if str(channel) not in ("0", "1", "2", "3") or len(bounds) != 2:
                raise ValueError(f"{name}: invalid channel loop")
            start = integer(bounds[0], "loop start", 0, frames - 1)
            end = integer(bounds[1], "loop end", start + 1, frames)
            loops[int(channel)] = (start, end)
        apu = ApuControl(tones)
        cursor = 0
        streams = {channel: dict(notes=[], volumes=[], tones=[]) for channel in range(4)}
        for tick in range(math.ceil(frames / rate * TICK_RATE)):
            time = (tick + 0.5) / TICK_RATE
            while cursor < len(normalised) and normalised[cursor][0] / rate <= time:
                frame, register, value = normalised[cursor]
                apu.advance(frame / rate)
                apu.write(register, value)
                cursor += 1
            apu.advance(time)
            for channel, stream in streams.items():
                note, tone, volume = apu.sample(channel)
                for attribute, value in (("notes", note), ("tones", tone), ("volumes", volume)):
                    stream[attribute].append(value)
        streams = {channel: stream for channel, stream in streams.items() if any(stream["volumes"])}
        for channel, stream in streams.items():
            if channel in loops:
                end = round(loops[channel][1] / rate * TICK_RATE)
                for attribute in stream:
                    stream[attribute] = stream[attribute][:end]
        result[name] = dict(frames=frames, loops=loops, streams=streams)
    return result, tones.definitions


def sample_indices(length, speed):
    if isinstance(speed, bool) or not isinstance(speed, (int, float)) or not math.isfinite(speed) or speed <= 0:
        raise ValueError("speed must be positive and finite")
    ratio = Fraction(str(speed))
    count = (length * ratio.denominator + ratio.numerator - 1) // ratio.numerator
    return [tick * ratio.numerator // ratio.denominator for tick in range(count)]


def export_resource(document, output, sound_base=0, music_base=0, gain=0.3, speed=1.0):
    import pyxel

    # Native initialization can change cwd to the script directory.
    output = Path(output).resolve()
    sample_indices(0, speed)  # Validate before baking or writing any output.
    tracks, tones = bake_document(document, gain)
    integer(sound_base, "sound_base")
    integer(music_base, "music_base")
    rate = document.get("frame_rate", GB_FRAME_RATE)
    needed = sum(1 + (channel in t["loops"] and t["loops"][channel][0] > 0)
                 for t in tracks.values() for channel in t["streams"])
    pyxel.init(160, 144, headless=True)
    if sound_base + needed > len(pyxel.sounds) or music_base + len(tracks) > len(pyxel.musics):
        raise ValueError("Not enough Pyxel SOUND/MUSIC banks for this export")
    manifest = dict(format_version=1, tone_base=4, tones=tones, sound_tones={}, clips={},
                    frame_rate=rate, source_frame_rate=rate, playback_frame_rate=rate * speed,
                    playback_speed=speed, tick_rate=TICK_RATE,
                    source_rom_sha256=document.get("source_rom_sha256"),
                    approximations=["120Hz", "semitone pitch", "8 volume steps",
                                    "fixed APU phase", "Pyxel noise clock", "no NR50/NR51 mixing"])
    bank = sound_base
    for offset, (name, track) in enumerate(tracks.items()):
        music = music_base + offset
        sequences = [[] for _ in range(4)]
        intros = [0] * 4
        source_intros = [0] * 4
        playback_ticks = [0] * 4
        looping = [False] * 4
        for channel, stream in track["streams"].items():
            looping[channel] = channel in track["loops"]
            start = round(track["loops"][channel][0] / rate * TICK_RATE) if looping[channel] else 0
            source_intros[channel] = start
            ranges = ((0, start), (start, len(stream["notes"]))) if start else ((0, len(stream["notes"])),)
            for first, last in ranges:
                sound = pyxel.sounds[bank]
                indices = [first + index for index in sample_indices(last - first, speed)]
                sound.notes[:] = [stream["notes"][index] for index in indices]
                sound.volumes[:] = [stream["volumes"][index] for index in indices]
                exact_tones = [stream["tones"][index] for index in indices]
                if start and first == 0:
                    intros[channel] = len(indices)
                playback_ticks[channel] += len(indices)
                manifest["sound_tones"][str(bank)] = exact_tones
                sound.tones[:] = [3 if tone in (8, 9) else 0 if tone >= 10 else 1
                                 if tone == 6 else 2 for tone in exact_tones]
                sound.effects[:] = [0]
                sound.speed = 1
                sequences[channel].append(bank)
                bank += 1
        pyxel.musics[music].set(*sequences)
        manifest["clips"][name] = dict(music=music, channels=sequences, loops=looping,
                                       intro_ticks=intros, source_intro_ticks=source_intros,
                                       playback_ticks=playback_ticks, frames=track["frames"])
    output.parent.mkdir(parents=True, exist_ok=True)
    pyxel.save(str(output))
    payload = json.dumps(manifest, ensure_ascii=False, separators=(",", ":"))
    with zipfile.ZipFile(output, "a", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("gb_audio.json", payload)
    output.with_suffix(".json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                                          encoding="utf-8")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--sound-base", type=int, default=0)
    parser.add_argument("--music-base", type=int, default=0)
    parser.add_argument("--gain", type=float, default=0.3)
    parser.add_argument("--speed", type=float, default=1.0, help="Playback speed relative to original traces (default: 1.0)")
    args = parser.parse_args()
    document = json.loads(args.input.read_text(encoding="utf-8"))
    manifest = export_resource(document, args.output, args.sound_base, args.music_base, args.gain, args.speed)
    print(f"Exported {args.output}: {len(manifest['clips'])} tracks, {len(manifest['sound_tones'])} sounds")


if __name__ == "__main__":
    main()
