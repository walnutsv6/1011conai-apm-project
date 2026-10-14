"""ROM-free BGM player with explicit stopped, paused and playing states."""
import json
from pathlib import Path

import pyxel
from audio_runtime import channel_plan, load_audio

FPS = 60
STOPPED, PAUSED, PLAYING = 'stopped', 'paused', 'playing'


class App:
    def __init__(self, catalog_path=None):
        catalog_path = Path(catalog_path or Path(__file__).with_name('catalog.json')).resolve()
        self.root = catalog_path.parent
        self.catalog = json.loads(catalog_path.read_text(encoding='utf-8'))
        self.tracks = self.catalog['tracks']
        if not self.tracks:
            raise ValueError('The catalog must contain at least one track')
        self.state = STOPPED
        self.index = 0
        self.elapsed_base = 0.0
        self.boundaries = [None] * 4
        pyxel.init(320, 240, title=self.catalog.get('player_title', 'Pyxel BGM Player'),
                   fps=FPS, quit_key=pyxel.KEY_NONE)
        self.start_frame = pyxel.frame_count
        self.select(0)

    @property
    def elapsed(self):
        advancing = (pyxel.frame_count - self.start_frame) / FPS if self.state == PLAYING else 0
        return self.elapsed_base + advancing

    def plan(self, channel):
        pyxel.stop(channel)
        plan = channel_plan(pyxel, self.audio, self.track['name'], channel, self.elapsed)
        self.boundaries[channel] = plan['next_boundary'] if plan else None
        if plan:
            pyxel.play(channel, plan['sounds'], sec=plan['sec'], loop=plan['loop'])

    def select(self, index):
        # Keep the existing state: selection while stopped/paused is silent.
        pyxel.stop()
        self.index = index % len(self.tracks)
        self.track = self.tracks[self.index]
        self.audio = load_audio(pyxel, self.root / self.track['resource'])
        self.clip = self.audio['clips'][self.track['name']]
        self.elapsed_base = 0.0
        self.start_frame = pyxel.frame_count
        self.boundaries = [None] * 4
        self.duration = max((sum(pyxel.sounds[bank].total_sec() for bank in banks)
                             for banks in self.clip['channels']), default=0)
        self.looping = any(loop and banks for loop, banks in zip(self.clip['loops'], self.clip['channels']))
        if self.state == PLAYING:
            for channel in range(4):
                self.plan(channel)

    def toggle(self):
        if self.state == PLAYING:
            self.elapsed_base = self.elapsed
            self.state = PAUSED
            pyxel.stop()
            self.boundaries = [None] * 4
        else:
            if self.state == STOPPED:
                self.elapsed_base = 0.0
            self.state = PLAYING
            self.start_frame = pyxel.frame_count
            for channel in range(4):
                self.plan(channel)

    def restart(self):
        pyxel.stop()
        self.elapsed_base = 0.0
        self.start_frame = pyxel.frame_count
        self.boundaries = [None] * 4
        if self.state == PLAYING:
            for channel in range(4):
                self.plan(channel)

    @staticmethod
    def pressed(*keys):
        return any(pyxel.btnp(key) for key in keys)

    def update(self):
        if self.pressed(pyxel.KEY_ESCAPE, pyxel.GAMEPAD1_BUTTON_START):
            pyxel.stop()
            pyxel.quit()
            return
        previous = self.pressed(pyxel.KEY_LEFT, pyxel.KEY_UP,
                                pyxel.GAMEPAD1_BUTTON_DPAD_LEFT, pyxel.GAMEPAD1_BUTTON_DPAD_UP)
        following = self.pressed(pyxel.KEY_RIGHT, pyxel.KEY_DOWN,
                                 pyxel.GAMEPAD1_BUTTON_DPAD_RIGHT, pyxel.GAMEPAD1_BUTTON_DPAD_DOWN)
        if previous != following:
            self.select(self.index + (1 if following else -1))
        if self.pressed(pyxel.KEY_R, pyxel.GAMEPAD1_BUTTON_B):
            self.restart()
        if self.pressed(pyxel.KEY_SPACE, pyxel.GAMEPAD1_BUTTON_A):
            self.toggle()
        if self.state == PLAYING:
            if not self.looping and self.elapsed >= self.duration:
                self.elapsed_base = self.duration
                self.state = STOPPED
                pyxel.stop()
                self.boundaries = [None] * 4
            else:
                for channel, boundary in enumerate(self.boundaries):
                    if boundary is not None and self.elapsed >= boundary:
                        self.plan(channel)

    def draw(self):
        pyxel.cls(1)
        pyxel.rect(0, 0, 320, 33, 5)
        pyxel.text(12, 10, self.catalog.get('player_title', 'PYXEL BGM PLAYER')[:48], 7)
        pyxel.text(12, 23, 'Standalone audio player', 6)
        pyxel.text(12, 45, f'{self.index + 1:02}/{len(self.tracks):02}', 10)
        pyxel.text(58, 45, self.track.get('display_name', self.track['name'])[:40], 7)
        pyxel.text(12, 61, self.state.upper(), 11)
        pyxel.text(105, 61, f'{self.elapsed:7.1f}s', 7)
        if self.state == STOPPED:
            pyxel.text(12, 80, 'Press A / SPACE to play', 10)
        elif self.state == PAUSED:
            pyxel.text(12, 80, 'Press A / SPACE to resume', 10)
        else:
            pyxel.text(12, 80, 'LOOPING' if self.looping else 'ONE SHOT', 6)
        pyxel.line(12, 100, 308, 100, 5)
        first = max(0, min(self.index - 3, len(self.tracks) - 7))
        for row, entry in enumerate(self.tracks[first:first + 7]):
            y = 111 + row * 12
            selected = first + row == self.index
            if selected:
                pyxel.rect(8, y - 2, 304, 10, 5)
            label = entry.get('display_name', entry['name'])[:43]
            pyxel.text(12, y, ('> ' if selected else '  ') + label, 10 if selected else 6)
        pyxel.text(12, 207, 'Keys: ARROWS Select  SPACE Play/Pause', 7)
        pyxel.text(12, 217, 'Pad: DPAD Select  A Play/Pause  B Restart', 6)
        pyxel.text(12, 229, 'R Restart  /  ESC or START Quit', 6)


if __name__ == '__main__':
    app = App()
    pyxel.run(app.update, app.draw)
