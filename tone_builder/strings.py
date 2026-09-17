"""The string a note is played on.

On Gravity the string moved the deviation by up to 10.7 dB (C4: 5.9 dB on
string 2 fret 1, 15.5 dB on string 4 fret 10), more than amp, cab and pedal
together; the old rule "fret closest to 7" was wrong on 7 of 8 notes. So every
string the library has for the note is rendered and measured.
"""

from __future__ import annotations

from pathlib import Path

from tone_builder import library
from tone_builder.compare import note_deviation
from tone_builder.render import Renderer, render_note


def library_by_midi(root: Path, guitar: str, position: str) -> dict[int, list[Path]]:
    out: dict[int, list[Path]] = {}
    for p in library.list_notes(root, guitar, position):
        _, midi = library.parse_note_filename(p.name)
        out.setdefault(midi, []).append(p)
    return out


def choose_strings(target: list[dict], by_midi: dict[int, list[Path]], render: Renderer,
                   workdir: Path) -> list[dict]:
    out = []
    for i, note in enumerate(target):
        alts: dict[str, float | None] = {}
        for di in by_midi.get(note["midi"], []):
            x = render_note(render, di, workdir, f"string-{i:02d}-{di.stem}")
            d = note_deviation(note, x)
            alts[str(di)] = None if d is None else d["rms_db"]
        scored = [(v, k) for k, v in alts.items() if v is not None]
        if not scored:
            continue
        best_dev, best = min(scored)
        out.append({"note": note, "di": Path(best), "deviation": best_dev, "alternatives": alts})
    return out
