"""The song's chords from its cifra (tab): what is measured and with which voicing.

Measuring every detected attack against every playable voicing re-amped 441 voicings for
Welcome to Paradise, about 975 renders on the Ampero. A song is a handful of chords: the tab
says which, and in which shape, so each chord is measured on a few of its attacks with the one
voicing the record used.

cifra.yaml:
    source: https://...            # the page the chords came from, or who gave them
    tuning_semitones: -1           # the record's tuning against standard (half step down = -1)
    chords:
      - name: Eb5
        shape: {5: 7, 4: 9, 3: 9}  # string: fret, as the tab writes it (in the record's tuning)
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import yaml
from tone_analyzer.chords import detect_chords
from tone_analyzer.notes import midi_name

from tone_builder import library
from tone_builder.audio import SR
from tone_builder.target import (DEFAULT_DETECTOR, DUR_S, MIN_HARMONICS, _count, chord_freqs,
                                 in_window, read_levels)

PER_CHORD = 3


def load(path: Path) -> list[dict]:
    """[{name, midis, shape: [(string, midi)]}]; midis are the sounding pitches on the record."""
    doc = yaml.safe_load(Path(path).read_text())
    tune = int(doc.get("tuning_semitones") or 0)
    out = []
    for c in doc["chords"]:
        shape = sorted(((int(s), library.STANDARD_TUNING[int(s)] + tune + int(f)) for s, f in c["shape"].items()),
                       key=lambda t: -t[0])
        out.append({"name": c["name"], "midis": sorted(m for _, m in shape), "shape": shape})
    return out


def playable(chord: dict, by_midi: dict[int, list[Path]]) -> bool:
    """Every note of the shape exists in the library on that string."""
    return all(any(library.parse_note_filename(p.name)[0] == s for p in by_midi.get(m, [])) for s, m in chord["shape"])


def match(detected: list[int], chords: list[dict]) -> dict | None:
    """The chord whose pitch classes hold every detected one (2+ of them); same pitch classes
    in two registers -> the one whose lowest note is closest to the detected lowest."""
    pcs = {m % 12 for m in detected}
    if len(pcs) < 2:
        return None
    fits = [c for c in chords if pcs <= {m % 12 for m in c["midis"]}]
    if not fits:
        return None
    return min(fits, key=lambda c: abs(c["midis"][0] - min(detected)))


def target(disc: np.ndarray, lead: np.ndarray, chords: list[dict], per_chord: int = PER_CHORD,
           window=None, detector: str = DEFAULT_DETECTOR, stats: dict | None = None) -> list[dict]:
    """Up to per_chord attacks of each chord, the loudest, read at the chord's own harmonics."""
    by_chord: dict[str, list[dict]] = {}
    span = int(DUR_S * SR)
    for c in detect_chords(lead, SR, dur_s=DUR_S, detector=detector):
        _count(stats, "chords_seen")
        if not in_window(c["start_s"], window):
            _count(stats, "outside_window")
            continue
        if int(round(c["start_s"] * SR)) + span >= min(len(lead), len(disc)):
            continue
        ch = match(c["midis"], chords)
        if ch is None:
            _count(stats, "not_in_cifra")
            continue
        freqs = chord_freqs(ch["midis"])
        r = read_levels(disc, c["start_s"], freqs)
        if r is None or sum(r[1]) < MIN_HARMONICS:
            _count(stats, "chords_few_harmonics")
            continue
        by_chord.setdefault(ch["name"], []).append(
            {"kind": "chord", "start_s": c["start_s"], "midis": ch["midis"], "shape": ch["shape"],
             "name": f"{ch['name']} ({'+'.join(midi_name(m) for m in ch['midis'])})",
             "freqs_hz": freqs, "level_db": r[0], "accepted": r[1]})
    out = []
    for entries in by_chord.values():
        out += sorted(entries, key=lambda e: -float(np.mean(e["level_db"])))[:per_chord]
    return sorted(out, key=lambda e: e["start_s"])


def shape_notes(entry: dict, by_midi: dict[int, list[Path]]) -> list[Path]:
    return [next(p for p in by_midi[m] if library.parse_note_filename(p.name)[0] == s) for s, m in entry["shape"]]
