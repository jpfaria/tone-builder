"""The target: where the guitar plays (separated track) and how loud each
harmonic is (the record).

Separation (Moises, Demucs) deletes harmonics above ~H6: on Gravity the record
shows peaks +21 dB over their neighbourhood where the separated track reads
-104 dB. The separated track only locates notes; the level comes from the record.
"""

from __future__ import annotations

import numpy as np
from tone_analyzer.chords import levels_at
from tone_analyzer.notes import detect_notes, midi_name

from tone_builder.audio import SR

# Known-truth sweep, 16/09 (96 notes, 4 guitars, synthetic and real background,
# dominance -6 and 0 dB): 10 dB kept the level error <= 2 dB in 5 of 16 cases,
# 13 dB is the lowest that keeps it in all 16 (worst 1.87 dB). Decided by jpfaria.
PROMINENCE_DB = 13.0
MIN_HARMONICS = 5
DUR_S = 0.6            # the shortest library note is 0.67 s
N_HARM = 16


def midi_hz(midi: int) -> float:
    return 440.0 * 2.0 ** ((midi - 69) / 12.0)


def note_freqs(midi: int) -> list[float]:
    f0 = midi_hz(midi)
    return [f0 * k for k in range(1, N_HARM + 1)]


def freqs_of(entry: dict) -> list[float]:
    return entry.get("freqs_hz") or note_freqs(entry["midi"])


def read_levels(disc: np.ndarray, start_s: float, freqs: list[float]) -> tuple[list, list[bool]] | None:
    h = levels_at(disc, SR, start_s, freqs, dur_s=DUR_S)
    if h is None:
        return None
    return h["level_db"], [p is not None and p >= PROMINENCE_DB for p in h["prominence_db"]]


def entry_tag(entry: dict) -> str:
    return "_".join(str(m) for m in (entry.get("midis") or [entry["midi"]]))


Window = tuple[float | None, float | None]


def in_window(start_s: float, window: Window | None) -> bool:
    """[from, to): an attack exactly at `to` belongs to the next part."""
    if window is None:
        return True
    lo, hi = window
    return (lo is None or start_s >= lo) and (hi is None or start_s < hi)


def build_target(disc: np.ndarray, lead: np.ndarray, available_midis: set[int],
                  window: Window | None = None, stats: dict | None = None) -> list[dict]:
    """Both signals mono at 48 kHz and aligned."""
    out = []
    span = int(DUR_S * SR)
    for n in detect_notes(lead, SR, dur_s=DUR_S):
        if not in_window(n["start_s"], window):
            continue
        if n["midi"] not in available_midis:
            continue
        start = int(round(n["start_s"] * SR))
        if start + span >= min(len(lead), len(disc)):
            continue
        freqs = note_freqs(n["midi"])
        r = read_levels(disc, n["start_s"], freqs)
        if r is None:
            continue
        level, accepted = r
        if sum(accepted) < MIN_HARMONICS:
            continue
        out.append({"kind": "note", "start_s": n["start_s"], "midi": n["midi"], "name": midi_name(n["midi"]),
                    "freqs_hz": freqs, "level_db": level, "accepted": accepted})
    return out
