"""GB control timers sampled for Pyxel; no PCM synthesis or ROM decoder."""

import math

GB_FRAME_RATE = 4194304 / 70224
TICK_RATE = 120


class ToneRegistry:
    def __init__(self, gain=0.3):
        self.definitions = []
        self.waves = {}
        for pattern in ("00000001", "10000001", "10000111", "01111110"):
            self.definitions.append(dict(mode=0, sample_bits=1,
                                         wavetable=[int(c) for c in pattern], gain=gain))
        self.definitions.extend(dict(mode=mode, sample_bits=4, wavetable=[], gain=gain)
                                for mode in (1, 2))
        self.gain = gain

    def wave(self, values):
        key = bytes(values)
        if key not in self.waves:
            self.waves[key] = 4 + len(self.definitions)
            samples = [n for byte in key for n in (byte >> 4, byte & 15)]
            self.definitions.append(dict(mode=0, sample_bits=4, wavetable=samples, gain=self.gain))
        return self.waves[key]


class ApuControl:
    def __init__(self, tones=None):
        self.tones = tones if tones is not None else ToneRegistry()
        self.reg = [0] * 64
        self.voices = [dict(on=False, length=0, volume=0, envelope_timer=0) for _ in range(4)]
        self.shadow = 0
        self.sweep_timer = 0
        self.sweep_enabled = False
        self.clock_step = 0
        self.time = 0.0
        # Standalone traces can start after the boot ROM's NR52 initialization.
        # An explicit NR52 write overrides this default.
        self.powered = True

    def sweep_period(self):
        delta = self.shadow >> (self.reg[0x10] & 7)
        return self.shadow + (-delta if self.reg[0x10] & 8 else delta)

    def write(self, register, value):
        if register >= 0xFF00:
            register -= 0xFF00
        if register == 0x26:
            self.powered = bool(value & 0x80)
            if not self.powered:
                self.reg[0x10:0x26] = [0] * 22
                for voice in self.voices:
                    voice.update(on=False, length=0, volume=0, envelope_timer=0)
                self.sweep_enabled = False
            self.reg[register] = value
            return
        if not self.powered and register < 0x30:
            return
        self.reg[register] = value
        channel = (0 if 0x10 <= register <= 0x14 else 1 if 0x16 <= register <= 0x19
                   else 2 if 0x1A <= register <= 0x1E else 3 if 0x20 <= register <= 0x23 else None)
        if channel is None:
            return
        voice = self.voices[channel]
        length, envelope, trigger = ((0x11, 0x12, 0x14), (0x16, 0x17, 0x19),
                                     (0x1B, 0x1C, 0x1E), (0x20, 0x21, 0x23))[channel]
        if register == length:
            voice["length"] = (256 if channel == 2 else 64) - (value if channel == 2 else value & 63)
        if register == envelope and channel != 2 and not value & 0xF8:
            voice["on"] = False
        if channel == 2 and register == 0x1A and not value & 0x80:
            voice["on"] = False
        if register != trigger or not value & 0x80:
            return
        voice["on"] = bool(self.reg[0x1A] & 0x80 if channel == 2 else self.reg[envelope] & 0xF8)
        if not voice["length"]:
            voice["length"] = 256 if channel == 2 else 64
        if channel != 2:
            voice["volume"] = self.reg[envelope] >> 4
            voice["envelope_timer"] = self.reg[envelope] & 7 or 8
        if channel == 0:
            self.shadow = self.period(0)
            self.sweep_timer = (self.reg[0x10] >> 4) & 7 or 8
            self.sweep_enabled = bool(self.reg[0x10] & 0x77)
            if self.reg[0x10] & 7 and self.sweep_period() > 2047:
                voice["on"] = False

    def period(self, channel):
        low = (0x13, 0x18, 0x1D)[channel]
        return self.reg[low] | (self.reg[low + 1] & 7) << 8

    def advance(self, until):
        if until < self.time:
            raise ValueError("APU time must be monotonic")
        while (self.clock_step + 1) / 512 <= until + 1e-12:
            self.clock_step += 1
            step = (self.clock_step - 1) % 8
            if step % 2 == 0:
                for channel, voice in enumerate(self.voices):
                    if self.reg[(0x14, 0x19, 0x1E, 0x23)[channel]] & 0x40 and voice["length"]:
                        voice["length"] -= 1
                        if not voice["length"]:
                            voice["on"] = False
            if step in (2, 6):
                self.sweep_timer -= 1
                if self.sweep_timer <= 0:
                    pace, shift = self.reg[0x10] >> 4 & 7, self.reg[0x10] & 7
                    self.sweep_timer = pace or 8
                    if self.sweep_enabled and pace:
                        period = self.sweep_period()
                        if period > 2047:
                            self.voices[0]["on"] = False
                        elif shift:
                            self.shadow = period
                            self.reg[0x13] = period & 255
                            self.reg[0x14] = (self.reg[0x14] & 0xF8) | period >> 8
                            if self.sweep_period() > 2047:
                                self.voices[0]["on"] = False
            if step == 7:
                for channel in (0, 1, 3):
                    voice = self.voices[channel]
                    envelope = self.reg[{0: 0x12, 1: 0x17, 3: 0x21}[channel]]
                    voice["envelope_timer"] -= 1
                    if voice["envelope_timer"] <= 0:
                        voice["envelope_timer"] = envelope & 7 or 8
                        if envelope & 7:
                            voice["volume"] = max(0, min(15, voice["volume"] + (1 if envelope & 8 else -1)))
        self.time = until

    def sample(self, channel):
        voice = self.voices[channel]
        if channel == 2:
            volume = (0, 15, 7, 3)[self.reg[0x1C] >> 5 & 3]
            tone = self.tones.wave(self.reg[0x30:0x40]) if voice["on"] and volume else 4
            frequency = 65536 / (2048 - self.period(2))
        elif channel == 3:
            volume = voice["volume"]
            polynomial = self.reg[0x22]
            clock = 262144 / ((polynomial & 7 or 0.5) * 2 ** (polynomial >> 4))
            frequency = clock / 4  # Pyxel-noise approximation, not a GB LFSR
            tone = 8 if polynomial & 8 else 9
        else:
            volume = voice["volume"]
            tone = 4 + (self.reg[(0x11, 0x16)[channel]] >> 6)
            frequency = 131072 / (2048 - self.period(channel))
        volume = round(volume * 7 / 15) if voice["on"] and self.powered else 0
        note = max(0, min(95, round(33 + 12 * math.log2(frequency / 440))))
        return note if volume else -1, tone, volume
