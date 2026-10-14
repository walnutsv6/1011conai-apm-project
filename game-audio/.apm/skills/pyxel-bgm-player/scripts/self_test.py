"""Native player-state, keyboard, gamepad and isolated pyxapp checks; no ROM."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import pyxel
from package_player import build

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / 'assets'))
import player


def make_project(root):
    (root / 'resources').mkdir()
    definitions = [dict(mode=0, sample_bits=4, wavetable=[0] * 16 + [15] * 16, gain=0.2)]
    for name, lengths, channels, loops, intros in (
        ('intro', [60, 120, 90, 180], [[0, 1], [], [2, 3], []], [True, False, True, False], [60, 0, 90, 0]),
        ('finite', [120], [[0], [], [], []], [False] * 4, [0] * 4),
        ('loop', [240], [[], [0], [], []], [False, True, False, False], [0] * 4),
    ):
        tones = {}
        for bank, length in enumerate(lengths):
            sound = pyxel.sounds[bank]
            sound.notes[:] = [24 + bank] * length
            sound.volumes[:] = [5] * length
            sound.tones[:] = [0] * length
            sound.effects[:] = [0]
            sound.speed = 1
            tones[str(bank)] = [4] * length
        pyxel.musics[0].set(*channels)
        metadata = dict(format_version=1, tone_base=4, tones=definitions, sound_tones=tones,
                        tick_rate=120, clips={name: dict(music=0, channels=channels, loops=loops, intro_ticks=intros)})
        path = root / 'resources' / f'{name}.pyxres'
        pyxel.save(str(path))
        with zipfile.ZipFile(path, 'a', compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('gb_audio.json', json.dumps(metadata))
        path.with_suffix('.json').write_text(json.dumps(metadata), encoding='utf-8')
    catalog = dict(player_title='Synthetic BGM Player', tracks=[
        dict(name=name, resource=f'resources/{name}.pyxres') for name in ('intro', 'finite', 'loop')])
    (root / 'catalog.json').write_text(json.dumps(catalog), encoding='utf-8')


class PlayerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pyxel.init(320, 240, headless=True, fps=60, quit_key=pyxel.KEY_NONE)
        cls.enterClassContext(patch.object(pyxel, 'init'))
        cls.temporary = tempfile.TemporaryDirectory(prefix='pyxel-bgm-skill-')
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.root = Path(cls.temporary.name).resolve()
        make_project(cls.root)

    def setUp(self):
        pyxel.stop()
        self.app = player.App(self.root / 'catalog.json')

    def press(self, *keys):
        for key in keys:
            pyxel.set_btn(key, True)
        self.app.update()
        self.app.draw()
        pyxel.flip()
        for key in keys:
            pyxel.set_btn(key, False)
        self.app.update()
        pyxel.flip()

    def silent(self):
        self.assertTrue(all(pyxel.play_pos(ch) is None for ch in range(4)))

    def active(self):
        self.assertTrue(any(pyxel.play_pos(ch) is not None for ch in range(4)))

    def test_startup_waits_for_keyboard_or_a(self):
        with patch.object(pyxel, 'play', wraps=pyxel.play) as play:
            app = player.App(self.root / 'catalog.json')
            for _ in range(20):
                app.update()
                app.draw()
                pyxel.flip()
            play.assert_not_called()
            self.assertEqual(app.state, player.STOPPED)
            self.assertEqual(app.elapsed, 0)
        self.silent()
        self.press(pyxel.KEY_SPACE)
        self.assertEqual(self.app.state, player.PLAYING)
        self.active()

    def test_all_directions_keep_stopped_selection_silent(self):
        keys = ((pyxel.KEY_RIGHT, 1), (pyxel.KEY_DOWN, 1), (pyxel.KEY_LEFT, -1), (pyxel.KEY_UP, -1),
                (pyxel.GAMEPAD1_BUTTON_DPAD_RIGHT, 1), (pyxel.GAMEPAD1_BUTTON_DPAD_DOWN, 1),
                (pyxel.GAMEPAD1_BUTTON_DPAD_LEFT, -1), (pyxel.GAMEPAD1_BUTTON_DPAD_UP, -1))
        with patch.object(pyxel, 'play', wraps=pyxel.play) as play:
            for key, direction in keys:
                before = self.app.index
                self.press(key)
                self.assertEqual(self.app.index, (before + direction) % 3)
                self.assertEqual(self.app.state, player.STOPPED)
                self.assertEqual(self.app.elapsed, 0)
                self.silent()
            play.assert_not_called()

    def test_paused_selection_keyboard_and_gamepad(self):
        self.press(pyxel.GAMEPAD1_BUTTON_A)
        self.press(pyxel.KEY_SPACE)
        self.assertEqual(self.app.state, player.PAUSED)
        for key in (pyxel.KEY_RIGHT, pyxel.GAMEPAD1_BUTTON_DPAD_RIGHT):
            with patch.object(pyxel, 'play', wraps=pyxel.play) as play:
                self.press(key)
                for _ in range(15):
                    self.app.update()
                    pyxel.flip()
                play.assert_not_called()
            self.assertEqual(self.app.state, player.PAUSED)
            self.assertEqual(self.app.elapsed, 0)
            self.silent()
        self.press(pyxel.GAMEPAD1_BUTTON_A)
        self.assertEqual(self.app.state, player.PLAYING)
        self.active()

    def test_playing_selection_replaces_current_track(self):
        self.press(pyxel.KEY_SPACE)
        for key in (pyxel.KEY_RIGHT, pyxel.GAMEPAD1_BUTTON_DPAD_RIGHT):
            before = self.app.index
            self.press(key)
            self.assertEqual(self.app.index, (before + 1) % 3)
            self.assertEqual(self.app.state, player.PLAYING)
            self.assertLess(self.app.elapsed, 0.1)
            self.active()

    def test_pause_freezes_and_resumes_position_in_loop(self):
        self.press(pyxel.GAMEPAD1_BUTTON_A)
        self.app.elapsed_base = 1.2
        self.app.start_frame = pyxel.frame_count
        self.app.update()
        self.press(pyxel.GAMEPAD1_BUTTON_A)
        held = self.app.elapsed
        for _ in range(15):
            pyxel.flip()
            self.app.update()
        self.assertEqual(self.app.elapsed, held)
        self.silent()
        self.press(pyxel.KEY_SPACE)
        self.assertAlmostEqual(self.app.elapsed, held, delta=0.05)
        self.assertEqual(self.app.boundaries, [None] * 4)
        self.active()

    def test_independent_intro_boundaries_and_restart_states(self):
        for key in (pyxel.KEY_R, pyxel.GAMEPAD1_BUTTON_B):
            self.press(key)
            self.assertEqual(self.app.state, player.STOPPED)
            self.silent()
        self.press(pyxel.GAMEPAD1_BUTTON_A)
        self.assertEqual(self.app.boundaries, [0.5, None, 0.75, None])
        self.app.elapsed_base = 0.6
        self.app.start_frame = pyxel.frame_count
        self.app.update()
        self.assertEqual(self.app.boundaries, [None, None, 0.75, None])
        self.app.elapsed_base = 0.8
        self.app.start_frame = pyxel.frame_count
        self.app.update()
        self.assertEqual(self.app.boundaries, [None] * 4)
        self.press(pyxel.GAMEPAD1_BUTTON_B)
        self.assertEqual(self.app.state, player.PLAYING)
        self.assertEqual(self.app.boundaries, [0.5, None, 0.75, None])
        self.active()
        self.press(pyxel.KEY_SPACE)
        self.press(pyxel.GAMEPAD1_BUTTON_B)
        self.assertEqual(self.app.state, player.PAUSED)
        self.assertEqual(self.app.elapsed, 0)
        self.silent()

    def test_finite_completion_and_play_again(self):
        self.app.select(1)
        self.press(pyxel.KEY_SPACE)
        self.app.elapsed_base = 1.1
        self.app.start_frame = pyxel.frame_count
        self.app.update()
        self.assertEqual(self.app.state, player.STOPPED)
        self.silent()
        self.press(pyxel.GAMEPAD1_BUTTON_A)
        self.assertEqual(self.app.state, player.PLAYING)
        self.assertLess(self.app.elapsed, 0.1)
        self.active()

    def test_input_edges_and_duplicate_input(self):
        self.press(pyxel.KEY_SPACE, pyxel.GAMEPAD1_BUTTON_A)
        self.assertEqual(self.app.state, player.PLAYING)
        pyxel.set_btn(pyxel.GAMEPAD1_BUTTON_A, True)
        self.app.update()
        for _ in range(20):
            pyxel.flip()
            self.app.update()
        self.assertEqual(self.app.state, player.PAUSED)
        pyxel.set_btn(pyxel.GAMEPAD1_BUTTON_A, False)
        pyxel.flip()
        self.app.update()
        self.press(pyxel.KEY_RIGHT, pyxel.GAMEPAD1_BUTTON_DPAD_RIGHT)
        self.assertEqual(self.app.index, 1)
        self.silent()

    def test_quit_stops_sound_for_keyboard_and_gamepad(self):
        for key in (pyxel.KEY_ESCAPE, pyxel.GAMEPAD1_BUTTON_START):
            self.app.restart()
            if self.app.state != player.PLAYING:
                self.app.toggle()
            with patch.object(pyxel, 'quit') as quit:
                self.press(key)
                quit.assert_called_once()
            self.silent()

    def test_pyxel_packaging_and_isolated_play(self):
        # Deliberate extra files prove that packaging stages only playback data.
        (self.root / 'unrelated.gbc').write_bytes(b'synthetic unrelated data')
        (self.root / 'extract.py').write_text('raise RuntimeError("must not be imported")', encoding='utf-8')
        app, distribution = build(self.root, self.root / 'dist', 'synthetic-player')
        with zipfile.ZipFile(distribution) as archive:
            self.assertEqual(set(archive.namelist()), {app.name, 'PLAY.txt'})
            self.assertIsNone(archive.testzip())
        with zipfile.ZipFile(app) as archive:
            self.assertFalse(any(name.endswith(('.gbc', '.wav', 'extract.py', '.json'))
                                 and not name.endswith('catalog.json') for name in archive.namelist()))
        bootstrap = self.root / 'verify_packaged.py'
        bootstrap.write_text('''import sys
from pathlib import Path
import pyxel
import pyxel.cli
app, isolated = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
isolated.mkdir()
pyxel.cli._create_app_dir = lambda: str(isolated)
native = pyxel.init
pyxel.init = lambda *a, **k: native(*a, **dict(k, headless=True))
def verify(update, draw):
    assert update.__self__.state == 'stopped'
    assert all(pyxel.play_pos(ch) is None for ch in range(4))
    for _ in range(10):
        update(); draw(); pyxel.flip()
    assert all(pyxel.play_pos(ch) is None for ch in range(4))
    pyxel.set_btn(pyxel.GAMEPAD1_BUTTON_A, True)
    update(); draw()
    assert any(pyxel.play_pos(ch) is not None for ch in range(4))
    import audio_runtime
    assert Path(audio_runtime.__file__).resolve().is_relative_to(isolated)
    print('PACKAGED_PLAYER_OK')
pyxel.run = verify
pyxel.cli.play_pyxel_app(str(app))
''', encoding='utf-8')
        result = subprocess.run([sys.executable, '-B', str(bootstrap), str(app), str(self.root / 'isolated')],
                                cwd=self.root / 'dist', capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('PACKAGED_PLAYER_OK', result.stdout)


if __name__ == '__main__':
    unittest.main(verbosity=2)
