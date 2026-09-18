"""The DI of a chord: the library's single notes summed per playable voicing, or a chord
recorded in DI. Which one is closer is measured, like the string of a note.

The chord detector reports octave-reduced sets (an exact octave doubling of a chord note is
inaudible to it), so a voicing may add any subset of the detected notes' octave doublings
(+12, +24) as extra strings, on top of the required notes.
"""

from __future__ import annotations

import itertools
from pathlib import Path

import numpy as np
import soundfile as sf
from tone_analyzer.take import take_onset

from tone_builder import library
from tone_builder.audio import SR, load_mono

MAX_SPAN = 3          # fretted notes within 4 frets (max - min <= 3); open strings do not count
MAX_VOICINGS = 32
MAX_NOTES = 6
PREROLL_S = 0.02


def _fret(string: int, midi: int) -> int:
    return midi - library.STANDARD_TUNING[string]


def _extras(midis: list[int]) -> list[int]:
    have = set(midis)
    out = sorted({m + o for m in midis for o in (12, 24)} - have)
    return out


def reduce_octaves(midis: list[int]) -> tuple[int, ...]:
    """The octave-reduced set: drop any note that has a lower note 12/24/36 below it in the set."""
    s = set(midis)
    return tuple(sorted(m for m in s if not ({m - 12, m - 24, m - 36} & s)))


def voicings(midis: list[int], by_midi: dict[int, list[Path]]) -> list[list[Path]]:
    required = list(midis)
    extras = _extras(midis)
    found = []
    for r in range(0, len(extras) + 1):
        for extra_subset in itertools.combinations(extras, r):
            notes = required + list(extra_subset)
            if len(notes) > MAX_NOTES:
                continue
            per = [
                [(s, p) for p in by_midi.get(m, []) for s in [library.parse_note_filename(p.name)[0]]]
                for m in notes
            ]
            if any(not options for options in per):
                continue
            for combo in itertools.product(*per):
                strings = [s for s, _ in combo]
                if len(set(strings)) != len(strings):
                    continue
                fretted = [f for f in (_fret(s, m) for (s, _), m in zip(combo, notes)) if f > 0]
                span = max(fretted) - min(fretted) if fretted else 0
                if span > MAX_SPAN:
                    continue
                paths = [p for _, p in combo]
                found.append((r, span, min(fretted, default=0), [str(p) for p in paths], paths))
    found.sort(key=lambda t: (t[0], t[1], t[2], t[3]))
    return [v for *_, v in found[:MAX_VOICINGS]]


def sum_di(paths: list[Path], out: Path, offsets_s: list[float] | None = None) -> Path:
    """Each note's attack placed at PREROLL_S (+ its offset), summed, peak scaled to the loudest note."""
    offsets_s = offsets_s or [0.0] * len(paths)
    parts, peak = [], 0.0
    for p, off in zip(paths, offsets_s):
        x = load_mono(p)
        a = take_onset(x, SR) or 0
        lead = int(round((PREROLL_S + off) * SR))
        parts.append(np.concatenate([np.zeros(lead), x[a:]]))
        peak = max(peak, float(np.abs(x).max()))
    n = max(len(x) for x in parts)
    y = sum(np.pad(x, (0, n - len(x))) for x in parts)
    y = y * (peak / (np.abs(y).max() + 1e-12))
    out.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(out), y.astype(np.float32), SR, subtype="FLOAT")
    return out


def recorded_by_midis(root: Path, guitar: str, position: str) -> dict[tuple[int, ...], list[Path]]:
    out: dict[tuple[int, ...], list[Path]] = {}
    for p in library.list_chords(root, guitar, position):
        key = reduce_octaves([m for _, m in library.parse_chord_filename(p.name)])
        out.setdefault(key, []).append(p)
    return out


def di_candidates(
    midis: list[int],
    by_midi: dict[int, list[Path]],
    recorded: dict[tuple[int, ...], list[Path]],
    workdir: Path,
) -> list[tuple[Path, str]]:
    cands = []
    for v in voicings(midis, by_midi):
        name = "_".join(f"c{s}-{m}" for s, m in (library.parse_note_filename(p.name) for p in v))
        cands.append((sum_di(v, Path(workdir) / f"{name}.wav"), "summed"))
    cands += [(p, "recorded") for p in recorded.get(reduce_octaves(midis), [])]
    return cands
