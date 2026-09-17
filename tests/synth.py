"""Synthetic notes with known harmonics, shared by the method tests."""
import numpy as np

SR = 48000


def note(midi, seconds=1.5, start_s=0.5, slope_db=-6.0, gains_db=None, n_harm=8, amp=0.3, total_s=None):
    f0 = 440.0 * 2 ** ((midi - 69) / 12)
    n = int(seconds * SR)
    t = np.arange(n) / SR
    env = np.exp(-t * 1.5)
    x = np.zeros(n)
    for k in range(1, n_harm + 1):
        g = slope_db * (k - 1) + (gains_db[k - 1] if gains_db is not None else 0.0)
        x += 10 ** (g / 20) * np.sin(2 * np.pi * f0 * k * t)
    x = amp * env * x / np.abs(x).max()
    total = int((total_s or (start_s + seconds + 0.5)) * SR)
    out = np.zeros(total)
    a = int(start_s * SR)
    out[a:a + n] = x
    return out
