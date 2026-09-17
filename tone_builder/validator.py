"""Known-truth validator: without it the method is opinion.

A KNOWN guitar note (from the library) is summed with an accompaniment at a
controlled dominance (RMS guitar / RMS accompaniment). The target reading
(harmonic level at k*f0 in the mix, accepted at >= 10 dB prominence) is compared
with the guitar alone.

The accompaniment is synthetic — pink noise plus a bass line with 6 harmonics,
half the power each — because songs cannot go into the repo. The original
validation (16/09) used the real no-guitar stem of Gravity and measured 1.84 dB
error with zero false positives at -6 dB dominance — but with one guitar only
(a Two-Rock render); see the stage 3 plan for the 96-note sweep.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from tone_analyzer.notes import harmonic_levels
from tone_analyzer.take import take_onset

from tone_builder import library
from tone_builder.audio import SR, load_mono
from tone_builder.target import DUR_S, MIN_HARMONICS, PROMINENCE_DB, midi_hz

# A false positive is a peak accepted in the mix where the guitar alone has no
# harmonic peak (prominence below this). A real guitar harmonic just under
# PROMINENCE_DB, pushed over it by the background, is not a false positive.
NO_PEAK_DB = 6.0


def _pink(n: int, rng: np.random.Generator) -> np.ndarray:
    spec = np.fft.rfft(rng.normal(size=n))
    f = np.fft.rfftfreq(n, 1 / SR)
    spec[1:] /= np.sqrt(f[1:])
    spec[0] = 0
    return np.fft.irfft(spec, n)


def _bass(n: int, rng: np.random.Generator) -> np.ndarray:
    f0 = midi_hz(int(rng.integers(28, 41)))
    t = np.arange(n) / SR
    return sum(np.sin(2 * np.pi * f0 * k * t) / k for k in range(1, 7)) * np.exp(-t * 1.0)


def _unit_rms(x: np.ndarray) -> np.ndarray:
    return x / (np.sqrt(np.mean(x ** 2)) + 1e-20)


def known_truth(notes: list[Path], dominance_db: float = -6.0, seed: int = 0) -> dict:
    rng = np.random.default_rng(seed)
    span = int(DUR_S * SR)
    errors, accepted_total, used, false_pos = [], 0, 0, 0
    for path in notes:
        parsed = library.parse_note_filename(Path(path).name)
        if parsed is None:
            continue
        f0 = midi_hz(parsed[1])
        x = load_mono(path)
        onset = take_onset(x, SR)
        if onset is None or onset + span > len(x):
            continue
        guitar = x[onset:onset + span]
        guitar = 0.35 * guitar / (np.abs(guitar).max() + 1e-12)
        acc = _unit_rms(_unit_rms(_pink(span, rng)) + _unit_rms(_bass(span, rng)))
        g_rms = np.sqrt(np.mean(guitar ** 2))
        mix = guitar + acc * g_rms / 10 ** (dominance_db / 20)
        hm = harmonic_levels(mix, SR, 0.0, f0, dur_s=DUR_S)
        hg = harmonic_levels(guitar, SR, 0.0, f0, dur_s=DUR_S)
        if hm is None or hg is None:
            continue
        ok = [pm is not None and pm >= PROMINENCE_DB and lg is not None
              for pm, lg in zip(hm["prominence_db"], hg["level_db"])]
        if sum(ok) < MIN_HARMONICS:
            continue
        used += 1
        accepted_total += sum(ok)
        false_pos += sum(1 for k, a in enumerate(ok)
                         if a and (hg["prominence_db"][k] is None or hg["prominence_db"][k] < NO_PEAK_DB))
        d = np.array([hm["level_db"][k] - hg["level_db"][k] for k, a in enumerate(ok) if a])
        errors.append(float(np.sqrt(np.mean((d - d.mean()) ** 2))))
    return {"notes": used, "harmonics_per_note": accepted_total / used if used else None,
            "error_db": float(np.mean(errors)) if errors else None, "false_positives": false_pos,
            "dominance_db": dominance_db}
