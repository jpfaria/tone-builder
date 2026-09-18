"""Builds one tone on one device, class by class, every choice under retention.

Order (spec "Fluxo de um timbre"): research -> target -> string choice with the
researched amp (and cab) -> amp settings -> cab settings -> single drive ->
stacked drives -> boost -> compressor (only if it really compresses) -> EQ fitted
on the fit notes -> time FX named by the research -> peak margin -> report.

A device provides:
  resolve(research) -> (dict[class, list[Option]], unresolved unit names)
  renderer(blocks) -> Renderer
  gain_reduction(blocks, dis, workdir) -> float      (compressor alone)
  eq_blocks(dict[band_hz, gain_db]) -> list[block]
  preset(blocks, name) -> dict
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from tone_builder import report as report_mod
from tone_builder import retention
from tone_builder.battery import Candidate, run_battery
from tone_builder.margin import measure_margin
from tone_builder.render import measure
from tone_builder.research import validate
from tone_builder.chords import di_candidates
from tone_builder.strings import choose_dis
from tone_builder.target import build_chord_target, build_target, merge_targets

# Chain order, first to last.
SLOTS = ("compressor", "boost", "drive", "amp", "cab", "eq", "time_fx")
EQ_BANDS_HZ = (250.0, 700.0, 2000.0, 5000.0)
EQ_MAX_DB = 6.0
EQ_UNIT = "fitted EQ"   # the method's own EQ: it has no research source, retention decides


class Unresolved(Exception):
    """Researched units with no model in the device catalog."""


@dataclass
class Option:
    name: str
    klass: str
    unit: str | None
    blocks: list[dict]
    gain_reduction_db: float | None = None
    extra: dict = field(default_factory=dict)


def assemble(state: dict[str, list[dict]]) -> list[dict]:
    return [b for slot in SLOTS for b in state.get(slot, [])]


def eq_gains(points: list[list[tuple[float, float]]], notes: list[int]) -> dict[float, float]:
    """Mean deviation (target - render) of the fit notes' harmonics, per nearest band."""
    acc: dict[float, list[float]] = {b: [] for b in EQ_BANDS_HZ}
    logs = np.log2(EQ_BANDS_HZ)
    for i in notes:
        for hz, d in points[i]:
            acc[EQ_BANDS_HZ[int(np.argmin(np.abs(logs - np.log2(hz))))]].append(d)
    return {b: float(np.clip(np.mean(v), -EQ_MAX_DB, EQ_MAX_DB)) if v else 0.0 for b, v in acc.items()}


def build_tone(disc: np.ndarray, lead: np.ndarray, by_midi: dict, research: dict, device,
               workdir: Path, name: str, window=None, chords: dict | None = None) -> dict:
    """chords: {"detector": str, "recorded": {octave-reduced midis: [DI]}}, or None for notes only."""
    errors = validate(research)
    if errors:
        raise ValueError("research is invalid:\n  " + "\n  ".join(errors))
    options, unresolved = device.resolve(research)
    if unresolved:
        raise Unresolved(unresolved)
    if not options.get("amp"):
        raise ValueError("the research names no amp with a model in the device catalog")
    stats: dict = {}
    target = build_target(disc, lead, set(by_midi), window=window, stats=stats)
    if chords is not None:
        target = merge_targets(target, build_chord_target(disc, lead, window=window,
                                                          detector=chords["detector"], stats=stats), stats)

    def seen() -> str:
        return " ".join(f"{k}={v}" for k, v in sorted(stats.items())) or "no attack found"

    if not target:
        raise ValueError(f"no target note or chord: nothing on the separated track matches the library "
                         f"with enough harmonics ({seen()})")

    workdir = Path(workdir)
    state: dict[str, list[dict]] = {"amp": options["amp"][0].blocks}
    if options.get("cab"):
        state["cab"] = options["cab"][0].blocks

    def candidates_for(entry: dict) -> list:
        if entry["kind"] == "note":
            return [(p, "library-note") for p in by_midi.get(entry["midi"], [])]
        cands = di_candidates(entry["midis"], by_midi, chords["recorded"], workdir / "chords")
        if not cands:
            stats["chords_no_voicing"] = stats.get("chords_no_voicing", 0) + 1
        return cands

    assignments = choose_dis(target, candidates_for, device.renderer(assemble(state)), workdir / "strings")
    if not assignments:
        raise ValueError(f"no target note or chord could be measured with the researched amp ({seen()})")
    fit, _ = retention.split(len(assignments))
    classes: dict[str, dict] = {}

    def step(klass: str, slot: str, opts: list[Option], extra_units: set[str] = frozenset()) -> dict:
        by_name = {o.name: o for o in opts}
        cands = [Candidate(o.name, klass, o.unit, device.renderer(assemble({**state, slot: o.blocks})),
                           o.gain_reduction_db) for o in opts]
        res, base = run_battery(device.renderer(assemble(state)), cands, assignments, research, workdir / klass,
                                derived_units={klass: set(extra_units)} if extra_units else None,
                                jobs=getattr(device, "jobs", 1))
        entry = res[klass]
        entry["baseline_deviation_db"] = base["deviation"]
        entry.pop("per_note_all", None)
        classes[klass] = entry
        s = entry.get("sourced")
        if s and s.get("accepted"):
            state[slot] = by_name[s["best"]].blocks
        return entry

    absent: dict[str, list[str]] = {}
    for b in research.get("blocks") or []:
        if b.get("absent_from_catalog"):
            absent.setdefault(b["class"], []).append(b["unit"])

    def note_absent(entry: dict, klass: str) -> None:
        if klass in absent:
            msg = f"researched with no catalog model: {', '.join(absent[klass])}"
            entry["reason"] = f"{entry['reason']}; {msg}" if entry.get("reason") else msg

    note_absent(step("amp", "amp", options.get("amp", [])), "amp")
    note_absent(step("cab", "cab", options.get("cab", [])), "cab")
    single = step("single_drive", "drive", options.get("single_drive", []))
    note_absent(single, "single_drive")

    # stacked: the best setting (on fit notes) of each drive unit, every ordered pair
    best_by_unit: dict[str, Option] = {}
    per_note = single.get("per_note") or {}
    for o in options.get("single_drive", []):
        if o.name not in per_note:
            continue
        v = [per_note[o.name][i] for i in fit if per_note[o.name][i] is not None]
        if not v:
            continue
        cur = best_by_unit.get(o.unit)
        if cur is None or np.mean(v) < cur.extra["fit"]:
            best_by_unit[o.unit] = Option(o.name, o.klass, o.unit, o.blocks, extra={"fit": float(np.mean(v))})
    pairs = [Option(f"{a.name} -> {b.name}", "stacked_drives", f"{a.unit} + {b.unit}", a.blocks + b.blocks)
             for a, b in itertools.permutations(best_by_unit.values(), 2)]
    entry = step("stacked_drives", "drive", pairs, {p.unit for p in pairs})
    if not pairs and not entry.get("reason"):
        entry["reason"] = f"fewer than 2 sourced drive units measured ({len(best_by_unit)})"

    note_absent(step("boost", "boost", options.get("boost", [])), "boost")

    comps = []
    for o in options.get("compressor", []):
        o.gain_reduction_db = device.gain_reduction(o.blocks, [a["di"] for a in assignments], workdir / "gr" / o.name)
        comps.append(o)
    step("compressor", "compressor", comps)

    current = measure(device.renderer(assemble(state)), assignments, workdir / "eq-base")
    gains = eq_gains(current["points"], fit)
    eq_opt = Option("fitted-eq", "eq", EQ_UNIT, device.eq_blocks(gains), extra={"gains": gains})
    eq_entry = step("eq", "eq", [eq_opt], {EQ_UNIT})
    eq_entry["fitted_gains_db"] = {str(k): v for k, v in gains.items()}

    tfx = options.get("time_fx", [])
    tfx_entry = step("time_fx", "time_fx", tfx)
    if tfx:
        # a time/feel block named by the research ships even when the harmonic number cannot see it
        seen, blocks = set(), []
        for o in tfx:
            if o.unit not in seen:
                seen.add(o.unit)
                blocks += o.blocks
        state["time_fx"] = blocks
        tfx_entry["shipped"] = sorted(seen)

    final_blocks = assemble(state)
    final = measure(device.renderer(final_blocks), assignments, workdir / "final")
    margin = measure_margin(device.renderer(final_blocks), [a["di"] for a in assignments], workdir / "margin")
    rep = report_mod.build(classes, margin, final["deviation"])
    rep["absent_from_catalog"] = absent
    rep["final_deviation_db"] = final["deviation"]
    rep["notes"] = [{"name": a["note"]["name"], "kind": a["note"]["kind"], "start_s": a["note"]["start_s"],
                     "di": str(a["di"]), "source": a["source"], "deviation_db": d}
                    for a, d in zip(assignments, final["per_note"])]
    return {"report": rep, "preset": device.preset(final_blocks, name), "blocks": final_blocks, "target": target}
