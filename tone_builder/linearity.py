"""How non-linear a chain is, measured with no reference recording.

The same library notes go through the chain at two input levels 20 dB apart. A linear chain moves
every harmonic by exactly 20 dB, whatever its EQ; how far each harmonic is from that is the
distortion, and how much less than 20 dB the fundamental rose is the compression.

On OpenRig's NAM captures every amp reads ~5 dB at the hot level used here (-6 dBFS peak is hot for
a capture), so the number ranks captures against each other; it is not an absolute THD.
17/09/2026: it ranked the AC30 top boost 58th and its normal channel 40th of 106 captures, the
Fender Twin 4th — the same order jpfaria heard ("still a distortion that is not in the original").
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile as sf

from tone_builder.audio import SR, load_mono
from tone_builder.render import Renderer, render_note
from tone_builder.target import midi_hz

HOT_DB, QUIET_DB = -6.0, -26.0
NOTE_S, GAP_S, HARMONICS, FLOOR_DB = 0.6, 0.3, 8, 45.0


def _midi(di: Path) -> int:
    return int(Path(di).stem.split("-")[1])


def _harmonics(y: np.ndarray, start: int, f0: float) -> np.ndarray:
    seg = y[start + int(0.05 * SR): start + int(NOTE_S * SR)]
    n = 1 << 17
    spec = np.abs(np.fft.rfft(seg * np.hanning(len(seg)), n))
    fr = np.fft.rfftfreq(n, 1 / SR)
    return np.array([20 * np.log10(np.max(spec[(fr > k * f0 * 0.98) & (fr < k * f0 * 1.02)]) + 1e-12)
                     for k in range(1, HARMONICS + 1)])


def nonlinearity(render: Renderer, dis: list[Path], workdir: Path) -> dict:
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    gap = np.zeros(int(GAP_S * SR), dtype=np.float32)
    x = np.concatenate([np.concatenate([load_mono(d)[: int(NOTE_S * SR)], gap]) for d in dis])
    x = x / (np.max(np.abs(x)) + 1e-12)
    wet = {}
    for name, db in (("hot", HOT_DB), ("quiet", QUIET_DB)):
        # the file stem keeps the library naming (cN-<midi>-X) so fake renderers in tests can parse it
        src = workdir / f"c0-{_midi(dis[0])}-{name}.wav"
        sf.write(str(src), (x * 10 ** (db / 20)).astype(np.float32), SR, subtype="FLOAT")
        wet[name] = render_note(render, src, workdir, f"wet-{name}").astype(np.float64)
    devs, comp = [], []
    for j, d in enumerate(dis):
        start = int(j * (NOTE_S + GAP_S) * SR)
        f0 = midi_hz(_midi(d))
        hq, hh = _harmonics(wet["quiet"], start, f0), _harmonics(wet["hot"], start, f0)
        ok = hq > np.max(hq) - FLOOR_DB                    # a harmonic lost in the floor says nothing
        delta = (hh - hq) - (HOT_DB - QUIET_DB)
        devs.append(float(np.sqrt(np.mean(delta[ok] ** 2))))
        comp.append(float(-delta[0]))
    return {"nonlinearity_db": float(np.mean(devs)), "compression_db": float(np.mean(comp)), "notes": len(dis)}


def rank(names: list[str], renderer_of, dis: list[Path], workdir: Path, jobs: int = 1) -> list[dict]:
    """Every named option measured, cleanest first. `renderer_of(name)` -> Renderer."""
    from concurrent.futures import ThreadPoolExecutor

    from tone_builder.render import RenderError

    def one(item):
        i, name = item
        try:
            return {"name": name, **nonlinearity(renderer_of(name), dis, Path(workdir) / f"{i:04d}")}
        except RenderError as e:
            return {"name": name, "error": str(e)}

    with ThreadPoolExecutor(max_workers=max(1, jobs)) as ex:
        rows = list(ex.map(one, enumerate(names)))
    return sorted(rows, key=lambda r: r.get("nonlinearity_db", float("inf")))
