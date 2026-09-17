"""The full block battery. Testing one class and calling it done is how Gravity
was declared ready with only single drives tested (round 7); round 8 had to
test stacked drives, boost and a compressor that really compresses.

Candidates with and without a research source are ranked apart. The raw
ranking put a ZVEX Fuzz Factory (6.7 dB, no source) ahead of the Tube Screamer
(8.2 dB, sourced); only sourced candidates can be chosen.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from tone_builder import retention
from tone_builder.compressor import MIN_GAIN_REDUCTION_DB, is_tested
from tone_builder.render import Renderer, RenderError, measure
from tone_builder.research import CLASSES, sourced_units

__all__ = ["CLASSES", "Candidate", "run_battery"]


@dataclass
class Candidate:
    name: str
    klass: str
    unit: str | None
    render: Renderer
    gain_reduction_db: float | None = None


def run_battery(baseline: Renderer, candidates: list[Candidate], assignments: list[dict],
                research: dict, workdir: Path,
                derived_units: dict[str, set[str]] | None = None) -> tuple[dict[str, dict], dict]:
    """Returns (result per class, baseline measurement)."""
    base = measure(baseline, assignments, workdir / "baseline")
    fit, test = retention.split(len(assignments))
    sourced = sourced_units(research)
    # Units built from sourced ones (a pair of sourced drives) or by the method itself
    # (the fitted EQ): choosable under retention, flagged as derived, never given a URL.
    derived = derived_units or {}
    for k, units in derived.items():
        sourced.setdefault(k, set()).update(units)
    not_found = {n.get("class"): n for n in research.get("not_found") or []}
    out: dict[str, dict] = {}
    for klass in CLASSES:
        pool = [c for c in candidates if c.klass == klass]
        entry = {"status": "no_candidate", "sourced": None, "unsourced_best": None,
                 "reason": None, "errors": [], "measured": {}, "derived_from_sources": bool(derived.get(klass))}
        if klass in not_found:
            entry["reason"] = f"research found no source: {not_found[klass].get('searched')}"
        if klass == "compressor" and pool:
            kept = [c for c in pool if c.gain_reduction_db is not None and is_tested(c.gain_reduction_db)]
            if not kept:
                entry["status"] = "not_tested"
                entry["reason"] = (f"no setting reached {MIN_GAIN_REDUCTION_DB:g} dB of measured gain "
                                   f"reduction: {[c.gain_reduction_db for c in pool]}")
                out[klass] = entry
                continue
            pool = kept
        results = {}
        for c in pool:
            try:
                results[c.name] = measure(c.render, assignments, workdir / klass / c.name)
            except RenderError as e:
                entry["errors"].append(f"{c.name}: {e}")
        if results:
            entry["status"] = "measured"
            entry["measured"] = {k: v["deviation"] for k, v in results.items()}
            entry["per_note"] = {k: v["per_note"] for k, v in results.items()}
            with_src = {c.name: results[c.name]["per_note"] for c in pool
                        if c.name in results and c.unit in sourced.get(klass, set())}
            if with_src:
                entry["sourced"] = retention.decide(base["per_note"], with_src, fit, test)
            without = [(results[c.name]["deviation"], c.name) for c in pool
                       if c.name in results and c.name not in with_src and results[c.name]["deviation"] is not None]
            if without:
                d, n = min(without)
                entry["unsourced_best"] = {"name": n, "deviation": d}
        out[klass] = entry
    return out, base
