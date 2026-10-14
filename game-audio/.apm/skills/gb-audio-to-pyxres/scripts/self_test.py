"""ROM-free checks of the portable converter and actual native Pyxel loading."""

import json
import copy
from fractions import Fraction
from pathlib import Path
import tempfile
import subprocess
import sys
import tomllib
import unittest
from unittest.mock import patch
import zipfile

from gb_apu import ApuControl
from pyxel_audio_runtime import channel_plan, load_audio
from trace_to_pyxres import bake_document, export_resource


def synthetic_document():
    # Hand-authored control events, not extracted music or ROM waveforms.
    pulse = [[0, 0x16, 0x40], [0, 0x17, 0xF2], [0, 0x18, 0], [0, 0x19, 0x84]]
    wave = [[0, 0x1A, 0]] + [[0, 0x30 + i, (i << 4) | (15 - i)] for i in range(16)]
    wave += [[0, 0x1A, 0x80], [0, 0x1C, 0x20], [0, 0x1D, 0], [0, 0x1E, 0x84],
             [5, 0x1A, 0], [5, 0x30, 0xAB], [5, 0x1A, 0x80], [5, 0x1E, 0x84]]
    return dict(format_version=1, tracks=[
        dict(name="pulse", frames=30, register_writes=pulse,
             channel_loops={"1": [5, 30]}),
        dict(name="wave", frames=20, register_writes=wave)])


class ControlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import pyxel

        # Pyxel permits one initialization per process. Keep native save/load
        # and playback active while multiple export cases share that context.
        pyxel.init(160, 144, headless=True)
        cls.enterClassContext(patch.object(pyxel, "init"))

    def test_length_and_envelope(self):
        apu = ApuControl()
        for reg, value in ((0x11, 0xBE), (0x12, 0xF1), (0x13, 0), (0x14, 0xC4)):
            apu.write(reg, value)
        apu.advance(0.01)
        self.assertFalse(apu.voices[0]["on"])
        apu.write(0x14, 0x84)
        apu.advance(0.1)
        self.assertTrue(apu.voices[0]["on"])
        self.assertLess(apu.voices[0]["volume"], 15)

    def test_sweep_and_power(self):
        apu = ApuControl()
        for reg, value in ((0x10, 0x11), (0x12, 0xF0), (0x13, 0), (0x14, 0x84)):
            apu.write(reg, value)
        apu.advance(0.01)
        self.assertEqual(apu.period(0), 1536)
        self.assertFalse(apu.voices[0]["on"])
        apu.write(0xFF26, 0)
        apu.write(0xFF12, 0xF0)
        self.assertEqual(apu.reg[0x12], 0)
        apu.write(0xFF26, 0x80)
        apu.write(0xFF12, 0xF0)
        self.assertEqual(apu.reg[0x12], 0xF0)

    def test_wave_changes_and_empty_channels(self):
        tracks, tones = bake_document(synthetic_document())
        self.assertEqual(set(tracks["pulse"]["streams"]), {1})
        wave = tracks["wave"]["streams"][2]
        self.assertEqual(len(set(wave["tones"])), 2)
        first = tones[wave["tones"][0] - 4]["wavetable"]
        last = tones[wave["tones"][-1] - 4]["wavetable"]
        self.assertEqual(first[:4], [0, 15, 1, 14])
        self.assertEqual(last[:2], [10, 11])

    def test_reject_out_of_order_and_invalid_loops(self):
        doc = synthetic_document()
        doc["tracks"][0]["register_writes"] += [[2, 0x12, 0], [1, 0x12, 0]]
        with self.assertRaisesRegex(ValueError, "chronological"):
            bake_document(doc)
        doc = synthetic_document()
        doc["tracks"][0]["channel_loops"] = {"1": [30, 30]}
        with self.assertRaises(ValueError):
            bake_document(doc)

    def test_native_export_load_intro_and_editor_backup(self):
        import pyxel

        with tempfile.TemporaryDirectory(prefix="gb-audio-skill-") as directory:
            path = Path(directory) / "audio.pyxres"
            doc = synthetic_document()
            exported = export_resource(doc, path)
            with zipfile.ZipFile(path) as archive:
                self.assertEqual(json.loads(archive.read("gb_audio.json")), exported)
                data = tomllib.loads(archive.read("pyxel_resource.toml").decode())
            for bank in exported["sound_tones"]:
                self.assertLessEqual(set(data["sounds"][int(bank)]["tones"]), {0, 1, 2, 3})
            loaded = load_audio(pyxel, path)
            self.assertEqual(loaded["clips"]["pulse"]["channels"][2:], [[], []])
            self.assertIsNone(channel_plan(pyxel, loaded, "pulse", 0, 0))
            intro = loaded["clips"]["pulse"]["intro_ticks"][1] / 120
            first = channel_plan(pyxel, loaded, "pulse", 1, 0)
            loop = channel_plan(pyxel, loaded, "pulse", 1, intro + 0.05)
            self.assertFalse(first["loop"])
            self.assertTrue(loop["loop"])
            self.assertEqual(loop["sounds"], first["sounds"][1:])
            self.assertAlmostEqual(loop["sec"], 0.05)
            pyxel.play(1, loop["sounds"], sec=loop["sec"], loop=loop["loop"])
            self.assertIsNone(channel_plan(pyxel, loaded, "wave", 2, 5))
            # A standard-editor save removes the extra ZIP member. The sidecar
            # must still restore the exact Tone definitions without ROM access.
            pyxel.save(str(path))
            restored = load_audio(pyxel, path)
            self.assertEqual(restored["tones"], exported["tones"])

    def test_fractional_tempo_native_arrays_and_boundaries(self):
        import pyxel

        doc = synthetic_document()
        original = copy.deepcopy(doc)
        tracks, definitions = bake_document(doc)
        with tempfile.TemporaryDirectory(prefix="gb-audio-tempo-") as directory:
            path = Path(directory) / "audio.pyxres"
            for speed in (1.0, 1.7, 2.0, 0.75):
                with self.subTest(speed=speed):
                    exported = export_resource(doc, path, speed=speed)
                    loaded = load_audio(pyxel, path)
                    self.assertEqual(exported, loaded)
                    self.assertEqual(loaded["tones"], definitions)
                    self.assertEqual(loaded["playback_speed"], speed)
                    self.assertEqual(loaded["frame_rate"], loaded["source_frame_rate"])
                    self.assertEqual(loaded["playback_frame_rate"], loaded["frame_rate"] * speed)
                    ratio = Fraction(str(speed))
                    for name, track in tracks.items():
                        clip = loaded["clips"][name]
                        for channel, stream in track["streams"].items():
                            start = round(track["loops"][channel][0] / loaded["source_frame_rate"] * 120) if channel in track["loops"] else 0
                            bounds = [(0, start), (start, len(stream["notes"]))] if start else [(0, len(stream["notes"]))]
                            total = 0
                            for bank, (first, last) in zip(clip["channels"][channel], bounds, strict=True):
                                count = -(-(last - first) * ratio.denominator // ratio.numerator)
                                indices = [first + int(tick * ratio) for tick in range(count)]
                                sound = pyxel.sounds[bank]
                                for attribute in ("notes", "volumes", "tones"):
                                    self.assertEqual(list(getattr(sound, attribute)), [stream[attribute][i] for i in indices])
                                self.assertEqual(sound.speed, 1)
                                self.assertAlmostEqual(sound.total_sec(), count / 120)
                                total += count
                            self.assertEqual(clip["playback_ticks"][channel], total)
                            if start:
                                intro = len(pyxel.sounds[clip["channels"][channel][0]].notes)
                                self.assertEqual(clip["source_intro_ticks"][channel], start)
                                self.assertEqual(clip["intro_ticks"][channel], intro)
                                before = channel_plan(pyxel, loaded, name, channel, intro / 120 - 0.001)
                                after = channel_plan(pyxel, loaded, name, channel, intro / 120)
                                self.assertFalse(before["loop"])
                                self.assertTrue(after["loop"])
                                self.assertEqual(after["sounds"], clip["channels"][channel][1:])
                            else:
                                self.assertIsNone(channel_plan(pyxel, loaded, name, channel, total / 120 + 1 / 120))
                    self.assertEqual(doc, original)
            # Repeating the export at the same speed always starts at the
            # original control events, even when the output path exists.
            first = export_resource(doc, path, speed=1.7)
            first_bytes = path.read_bytes()
            second = export_resource(doc, path, speed=1.7)
            self.assertEqual(first, second)
            with zipfile.ZipFile(path) as archive:
                self.assertEqual(archive.namelist().count("gb_audio.json"), 1)
                self.assertEqual(json.loads(archive.read("gb_audio.json")), second)
            # Compare contents rather than ZIP timestamps.
            import io
            with zipfile.ZipFile(io.BytesIO(first_bytes)) as prior, zipfile.ZipFile(path) as current:
                self.assertEqual(prior.read("pyxel_resource.toml"), current.read("pyxel_resource.toml"))

    def test_invalid_tempo_does_not_write(self):
        with tempfile.TemporaryDirectory(prefix="gb-audio-invalid-tempo-") as directory:
            path = Path(directory) / "audio.pyxres"
            for speed in (0, -1, float("nan"), float("inf"), True):
                with self.assertRaisesRegex(ValueError, "positive and finite"):
                    export_resource(synthetic_document(), path, speed=speed)
                self.assertFalse(path.exists())
                self.assertFalse(path.with_suffix(".json").exists())

    def test_cli_fractional_speed_and_relative_output(self):
        converter = Path(__file__).resolve().with_name("trace_to_pyxres.py")
        with tempfile.TemporaryDirectory(prefix="gb-audio-cli-") as directory:
            root = Path(directory)
            (root / "trace.json").write_text(json.dumps(synthetic_document()), encoding="utf-8")
            result = subprocess.run([sys.executable, str(converter), "--input", "trace.json",
                                     "--output", "audio.pyxres", "--speed", "1.7"],
                                    cwd=root, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            sidecar = json.loads((root / "audio.json").read_text(encoding="utf-8"))
            self.assertEqual(sidecar["playback_speed"], 1.7)
            with zipfile.ZipFile(root / "audio.pyxres") as archive:
                self.assertEqual(json.loads(archive.read("gb_audio.json")), sidecar)


if __name__ == "__main__":
    unittest.main(verbosity=2)
