"""Deviation of a rendered note from the target note.

Compared on the target's accepted harmonics only: a 1/3-octave band on a single
note alternates harmonic peaks and valleys 74-84 dB down, and the mean over
that means nothing. Level is removed (mean of the differences); only shape counts.
"""

from __future__ import annotations

import numpy as np
from tone_analyzer.chords import levels_at
from tone_analyzer.take import take_onset

from tone_builder.audio import SR
from tone_builder.target import DUR_S, MIN_HARMONICS, freqs_of


def note_deviation(target_note: dict, wet: np.ndarray) -> dict | None:
    """wet: the same note or chord rendered by a candidate, mono at 48 kHz."""
    onset = take_onset(wet, SR)
    if onset is None:
        return None
    freqs = freqs_of(target_note)
    h = levels_at(wet, SR, onset / SR, freqs, dur_s=DUR_S)
    if h is None:
        return None
    ks = [k for k, (ok, t, w) in enumerate(zip(target_note["accepted"], target_note["level_db"], h["level_db"]))
          if ok and t is not None and w is not None]
    if len(ks) < MIN_HARMONICS:
        return None
    d = np.array([target_note["level_db"][k] - h["level_db"][k] for k in ks])
    d = d - d.mean()
    return {"rms_db": float(np.sqrt(np.mean(d ** 2))), "harmonics": len(ks),
            "points": [(freqs[k], float(v)) for k, v in zip(ks, d)]}


def mean_deviation(per_note: list[dict | None]) -> float | None:
    vals = [p["rms_db"] for p in per_note if p is not None]
    return float(np.mean(vals)) if vals else None
