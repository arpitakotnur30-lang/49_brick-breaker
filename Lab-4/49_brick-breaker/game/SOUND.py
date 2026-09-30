import array
import math
import os
import pygame

# Optional: drop WAV files named paddle.wav, wall.wav, brick.wav, win.wav or
# lose.wav into a "sounds" folder next to main.py to override the synthesized
# tones. Missing files are fine - the built-in tones are used instead.
SOUND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sounds")

# name -> (list of frequencies in Hz played one after another, seconds per note, waveform, volume)
SPECS = {
    "paddle": ([520],                     0.07, "square", 0.35),
    "wall":   ([330],                     0.05, "sine",   0.40),
    "brick":  ([880, 1100],               0.05, "square", 0.30),
    "win":    ([523, 659, 784, 1047],     0.14, "sine",   0.45),   # C5 E5 G5 C6 (rising)
    "lose":   ([392, 330, 262, 196],      0.20, "square", 0.35),   # falling
}


class SoundManager:
    """Loads/synthesizes all game sounds. Every failure path degrades to silence."""

    def __init__(self):
        self.muted = False
        self.available = False
        self.sounds = {}

        try:
            if pygame.mixer.get_init() is None:
                pygame.mixer.init(frequency=22050, size=-16, channels=1)
            self._rate, fmt, self._channels = pygame.mixer.get_init()
            self._can_synth = (fmt == -16)  # we generate signed 16-bit samples
            self.available = True
        except pygame.error:
            return  # no audio device (e.g. a server / CI): stay silent

        for name in SPECS:
            sound = self._load_wav(name) or self._synthesize(name)
            if sound is not None:
                self.sounds[name] = sound

    # -- creation ------------------------------------------------------
    def _load_wav(self, name):
        path = os.path.join(SOUND_DIR, f"{name}.wav")
        if not os.path.isfile(path):
            return None
        try:
            return pygame.mixer.Sound(path)
        except (pygame.error, OSError):
            return None

    def _synthesize(self, name):
        if not self._can_synth:
            return None
        freqs, note_len, wave, volume = SPECS[name]
        try:
            samples = array.array("h")
            for freq in freqs:
                n = int(self._rate * note_len)
                attack = max(1, int(self._rate * 0.005))  # tiny fade-in/out avoids clicks
                release = max(1, int(n * 0.35))
                for i in range(n):
                    s = math.sin(2 * math.pi * freq * i / self._rate)
                    if wave == "square":
                        s = 0.6 if s >= 0 else -0.6
                    env = min(1.0, i / attack, (n - i) / release)
                    value = int(32767 * volume * env * s)
                    for _ in range(self._channels):
                        samples.append(value)
            return pygame.mixer.Sound(buffer=samples.tobytes())
        except Exception:
            return None

    # -- playback ------------------------------------------------------
    def play(self, name):
        if not self.available or self.muted:
            return
        sound = self.sounds.get(name)
        if sound is None:
            return
        try:
            sound.play()
        except pygame.error:
            pass

    def toggle_mute(self):
        self.muted = not self.muted
        if self.muted and self.available:
            pygame.mixer.stop()