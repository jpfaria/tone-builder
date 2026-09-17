"""The target: where the guitar plays (separated track) and how loud each
harmonic is (the record).

Separation (Moises, Demucs) deletes harmonics above ~H6: on Gravity the record
shows peaks +21 dB over their neighbourhood where the separated track reads
-104 dB. The separated track only locates notes; the level comes from the record.
"""

from __future__ import annotations

import numpy as np
from tone_analyzer.notes import detect_notes, harmonic_levels, midi_name

from tone_builder.audio import SR

PROMINENCE_DB = 10.0   # with 10 dB the background adds <= 0.4 dB to the peak
MIN_HARMONICS = 5
DUR_S = 0.6            # the shortest library note is 0.67 s


def midi_hz(midi: int) -> float:
    return 440.0 * 2.0 ** ((midi - 69) / 12.0)


def build_target(disc: np.ndarray, lead: np.ndarray, available_midis: set[int]) -> list[dict]:
    """Both signals mono at 48 kHz and aligned."""
    out = []
    span = int(DUR_S * SR)
    for n in detect_notes(lead, SR, dur_s=DUR_S):
        if n["midi"] not in available_midis:
            continue
        start = int(round(n["start_s"] * SR))
        if start + span >= min(len(lead), len(disc)):
            continue
        h = harmonic_levels(disc, SR, n["start_s"], midi_hz(n["midi"]), dur_s=DUR_S)
        if h is None:
            continue
        accepted = [p is not None and p >= PROMINENCE_DB for p in h["prominence_db"]]
        if sum(accepted) < MIN_HARMONICS:
            continue
        out.append({"start_s": n["start_s"], "midi": n["midi"], "name": midi_name(n["midi"]),
                    "level_db": h["level_db"], "accepted": accepted})
    return out
