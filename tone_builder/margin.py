"""Delivery needs zero saturated samples with the DI boosted +12 and +18 dB
(a preset with only 4 dB of headroom was heard crackling)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile as sf
from tone_analyzer.take import saturated_samples

from tone_builder.render import Renderer, RenderError

BOOSTS_DB = (0, 12, 18)


HEADROOM = 10 ** (-0.5 / 20)


def measure_margin(render: Renderer, dis: list[Path], workdir: Path) -> dict:
    workdir.mkdir(parents=True, exist_ok=True)
    out = {}
    for boost in BOOSTS_DB:
        peak, sat = -120.0, 0
        for i, di in enumerate(dis):
            x, sr = sf.read(str(di), always_2d=False)
            src = workdir / f"{i:02d}-{Path(di).stem}+{boost}.wav"
            # a DI cannot be louder than full scale: past it the interface would have clipped the guitar itself
            gain = min(10 ** (boost / 20), HEADROOM / (float(np.abs(x).max()) + 1e-12))
            sf.write(str(src), x * gain, sr, subtype="FLOAT")
            wet = workdir / f"wet{i:02d}+{boost}.wav"
            render(src, wet)
            if not wet.exists():
                raise RenderError(f"render wrote nothing: {wet}")
            y, _ = sf.read(str(wet), always_2d=False)
            peak = max(peak, float(20 * np.log10(np.abs(y).max() + 1e-12)))
            sat += saturated_samples(y)
        out[boost] = {"peak_db": peak, "saturated": sat}
    return out


def margin_ok(m: dict) -> bool:
    return all(m.get(b, {}).get("saturated", 1) == 0 for b in BOOSTS_DB)
