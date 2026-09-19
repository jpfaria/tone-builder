"""Delivery report. "pronto" only when every battery class has a number or a
written reason and the peak margin passed; anything else is "parcial".

Round 7 of Gravity was called ready with one class tested; the word is now
earned by the data, not written by hand.
"""

from __future__ import annotations

from tone_builder.margin import BOOSTS_DB, margin_ok
from tone_builder.research import CLASSES


def build(battery: dict, margin: dict, baseline_deviation: float | None) -> dict:
    missing = [c for c in CLASSES
               if c not in battery or not (battery[c].get("status") == "measured" or battery[c].get("reason"))]
    ok = margin_ok(margin)
    return {"status": "pronto" if not missing and ok else "parcial", "missing": missing,
            "margin_ok": ok, "margin": margin, "baseline_deviation_db": baseline_deviation,
            "classes": {c: battery.get(c) for c in CLASSES}}


def _fmt(v: float | None) -> str:
    return "—" if v is None else f"{v:.1f}"


def to_markdown(rep: dict) -> str:
    lines = [f"**Status: {rep['status']}**", "",
             f"Baseline deviation: {_fmt(rep['baseline_deviation_db'])} dB", ""]
    if "final_deviation_db" in rep:
        lines += [f"Final deviation: {_fmt(rep['final_deviation_db'])} dB", ""]
    if "output_level" in rep:
        lines += [f"Output level (device's last block, lowered until +18 dB does not clip): {rep['output_level']}", ""]
    if rep["missing"]:
        lines += [f"Classes without a number or a reason: {', '.join(rep['missing'])}", ""]
    lines += ["| class | status | sourced best | test dB | accepted | unsourced best | reason |",
              "|---|---|---|---|---|---|---|"]
    for c in CLASSES:
        e = rep["classes"].get(c) or {}
        s = e.get("sourced") or {}
        u = e.get("unsourced_best") or {}
        lines.append(f"| {c} | {e.get('status', 'missing')} | {s.get('best') or '—'} | {_fmt(s.get('test_db'))} "
                     f"| {s.get('accepted', '—')} | {u.get('name', '—')} {_fmt(u.get('deviation'))} "
                     f"| {e.get('reason') or '—'} |")
    lines += ["", "| DI boost | peak dBFS | saturated samples |", "|---|---|---|"]
    for b in BOOSTS_DB:
        m = rep["margin"].get(b, {})
        lines.append(f"| +{b} dB | {_fmt(m.get('peak_db'))} | {m.get('saturated', '—')} |")
    return "\n".join(lines) + "\n"
