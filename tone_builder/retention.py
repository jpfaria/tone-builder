"""No choice without retention: rank on half of the notes, decide on the other.

Gravity, 16/09: five EQ iterations improved the fit notes and worsened the test
notes every time (test 8.1 -> 8.3, 8.6, 9.6, 12.2, 13.5). Round 8 then kept the
Tube Screamer over three alternatives 0.3 dB better on 4 notes because the noise
of that number was not measured; here it is measured.

Noise = 2 x standard error of the paired per-note differences on the test notes.
A candidate is accepted only when its mean improvement exceeds that.
"""

from __future__ import annotations

import numpy as np


def split(n: int) -> tuple[list[int], list[int]]:
    """Notes in time order: even indices fit, odd indices test."""
    return list(range(0, n, 2)), list(range(1, n, 2))


def _mean(values: list[float | None], idx: list[int]) -> float | None:
    xs = [values[i] for i in idx if values[i] is not None]
    return float(np.mean(xs)) if xs else None


def decide(baseline: list[float | None], candidates: dict[str, list[float | None]],
           fit: list[int], test: list[int]) -> dict:
    ranked = sorted((m, name) for name, v in candidates.items() if (m := _mean(v, fit)) is not None)
    if not ranked:
        return {"best": None, "fit_db": None, "test_db": None, "baseline_test_db": _mean(baseline, test),
                "improvement_db": None, "noise_db": None, "accepted": False}
    fit_db, best = ranked[0]
    v = candidates[best]
    diffs = [baseline[i] - v[i] for i in test if baseline[i] is not None and v[i] is not None]
    out = {"best": best, "fit_db": fit_db, "test_db": _mean(v, test),
           "baseline_test_db": _mean(baseline, test), "improvement_db": None,
           "noise_db": None, "accepted": False}
    if len(diffs) < 2:
        return out
    d = np.array(diffs)
    out["improvement_db"] = float(d.mean())
    out["noise_db"] = float(2.0 * d.std(ddof=1) / np.sqrt(len(d)))
    out["accepted"] = bool(out["improvement_db"] > out["noise_db"])
    return out
