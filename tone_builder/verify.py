"""After the tone is written to the device: render what was SAVED and measure it
again on the same notes. It must match the number the build reported.

A hardware pedal does not render the same note twice alike (MK-300, Alive solo,
18/09/2026: 0.2 dB between identical re-amps with modulation off, up to 0.5 dB with
a Univibe on). So the saved preset is rendered `repeats` times and the tolerance is
3 sigma of the difference between one build render and the mean of the repeats,
never below TOLERANCE_DB."""

from __future__ import annotations

import statistics
from pathlib import Path

from tone_builder.render import Renderer, measure

TOLERANCE_DB = 0.1
REPEATS = 3


def verify(report: dict, target: list[dict], saved: Renderer, workdir: Path, repeats: int = REPEATS) -> dict:
    # a chord and a note may start together; a report or target written before chords has no "kind"
    def key(n: dict) -> tuple[str, float]:
        return n.get("kind", "note"), round(n["start_s"], 3)
    by_key = {key(n): n for n in target}
    assignments = [{"note": by_key[key(n)], "di": Path(n["di"])} for n in report["notes"]]
    runs = []
    for i in range(repeats):
        d = Path(workdir) / f"r{i}" if repeats > 1 else Path(workdir)
        d.mkdir(parents=True, exist_ok=True)
        runs.append(measure(saved, assignments, d)["deviation"])
    expected = report.get("final_deviation_db")
    if any(r is None for r in runs):
        return {"deviation_db": None, "expected_db": expected, "diff_db": None, "runs_db": runs,
                "repeat_sd_db": None, "tolerance_db": None, "match": False}
    mean = statistics.fmean(runs)
    sd = statistics.stdev(runs) if repeats > 1 else 0.0
    tolerance = max(TOLERANCE_DB, 3 * sd * (1 + 1 / repeats) ** 0.5)
    diff = None if expected is None else mean - expected
    return {"deviation_db": mean, "expected_db": expected, "diff_db": diff, "runs_db": runs,
            "repeat_sd_db": sd, "tolerance_db": tolerance, "match": diff is not None and abs(diff) <= tolerance}
