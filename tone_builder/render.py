"""Rendering is injected: a Renderer turns a DI WAV into a wet WAV. Each device
(OpenRig, M-VAVE, Ampero) provides one; the method never knows which."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import numpy as np

from tone_builder.audio import load_mono
from tone_builder.compare import mean_deviation, note_deviation

Renderer = Callable[[Path, Path], None]
SILENCE = 1e-4


class RenderError(Exception):
    pass


def render_note(render: Renderer, di: Path, workdir: Path, tag: str) -> np.ndarray:
    workdir.mkdir(parents=True, exist_ok=True)
    wet = workdir / f"{tag}.wav"
    render(Path(di), wet)
    if not wet.exists():
        raise RenderError(f"render wrote nothing: {wet}")
    x = load_mono(wet)
    if len(x) == 0 or np.abs(x).max() < SILENCE:
        raise RenderError(f"render is silent: {wet}")
    return x


def measure(render: Renderer, assignments: list[dict], workdir: Path) -> dict:
    """assignments: [{"note": target note, "di": library WAV}] in time order."""
    per_note = []
    for i, a in enumerate(assignments):
        x = render_note(render, a["di"], workdir, f"{i:02d}-{a['note']['midi']}")
        per_note.append(note_deviation(a["note"], x))
    return {"deviation": mean_deviation(per_note),
            "per_note": [None if p is None else p["rms_db"] for p in per_note],
            "points": [[] if p is None else p["points"] for p in per_note]}
