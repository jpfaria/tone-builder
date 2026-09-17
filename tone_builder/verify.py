"""After the tone is written to the device: render what was SAVED and measure it
again on the same notes. It must match the number the build reported."""

from __future__ import annotations

from pathlib import Path

from tone_builder.render import Renderer, measure

TOLERANCE_DB = 0.1


def verify(report: dict, target: list[dict], saved: Renderer, workdir: Path) -> dict:
    by_start = {round(n["start_s"], 3): n for n in target}
    assignments = [{"note": by_start[round(n["start_s"], 3)], "di": Path(n["di"])} for n in report["notes"]]
    m = measure(saved, assignments, Path(workdir))
    expected = report.get("final_deviation_db")
    diff = None if expected is None or m["deviation"] is None else m["deviation"] - expected
    return {"deviation_db": m["deviation"], "expected_db": expected, "diff_db": diff,
            "match": diff is not None and abs(diff) <= TOLERANCE_DB}
