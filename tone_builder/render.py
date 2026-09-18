"""Rendering is injected: a Renderer turns a DI WAV into a wet WAV. Each device
(OpenRig, M-VAVE, Ampero) provides one; the method never knows which."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Callable

import numpy as np

from tone_builder.audio import load_mono
from tone_builder.compare import mean_deviation, note_deviation
from tone_builder.target import entry_tag

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
    if not os.environ.get("TONE_BUILDER_KEEP_RENDERS"):
        wet.unlink()          # measured and done: tens of thousands of kept renders fill a disk
    if len(x) == 0 or np.abs(x).max() < SILENCE:
        raise RenderError(f"render is silent: {wet}")
    return x


def _signature(render, assignments: list[dict]) -> str:
    # the chain too, when the renderer exposes it: same folder, other settings = other measurement
    key = [getattr(render, "blocks", None)] + [[a["note"]["midi"], a["note"]["start_s"], a["note"]["level_db"], Path(a["di"]).name] for a in assignments]
    return hashlib.sha256(json.dumps(key, sort_keys=True, default=str).encode()).hexdigest()


def measure(render: Renderer, assignments: list[dict], workdir: Path) -> dict:
    """assignments: [{"note": target note, "di": library WAV}] in time order.

    The result is kept in `workdir/measure.json`, keyed by the target notes and DIs: a build killed
    hours in resumes where it stopped."""
    workdir = Path(workdir)
    cache, sig = workdir / "measure.json", _signature(render, assignments)
    if cache.is_file():
        try:
            saved = json.loads(cache.read_text())
            if saved.get("signature") == sig:
                return saved["result"]
        except (ValueError, KeyError):
            pass
    per_note = []
    for i, a in enumerate(assignments):
        x = render_note(render, a["di"], workdir, f"{i:02d}-{entry_tag(a['note'])}")
        per_note.append(note_deviation(a["note"], x))
    result = {"deviation": mean_deviation(per_note),
              "per_note": [None if p is None else p["rms_db"] for p in per_note],
              "points": [[] if p is None else [list(pt) for pt in p["points"]] for p in per_note]}
    result = json.loads(json.dumps(result))          # what a resumed run would read back, exactly
    workdir.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps({"signature": sig, "result": result}))
    return result
