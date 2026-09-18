"""Step 0: the recording rig, researched with sources before anything is measured.

Without it the sweep has no right candidate and a whole block goes missing (on
Gravity the gain pedal was only found when the user asked; it moved 0.9 dB).
The research decides which blocks exist and which units enter the candidate
list; measurement only decides among them.

File format:
  song, part
  blocks:    [{class, unit, era: record|tour, sources: [url, ...]}]
             a block is sourced by a URL that was opened, OR by a first-hand `statement`
             {who, date, channel, quote} (the player told us; there is no page to cite).
             `unit: any` = the source names the class, not the unit ("compressor"): every model of
             that class competes. Not for time_fx: a delay or reverb the number cannot see is never
             picked blindly. `params: {...}` = settings fixed by ear, shipped as given.
  not_found: [{class, searched: [url or query, ...]}]
"""

from __future__ import annotations

from pathlib import Path

import yaml

ANY = "any"   # the source names the class, not the unit
CLASSES = ("single_drive", "stacked_drives", "boost", "compressor", "amp", "cab", "eq", "time_fx")


def load_research(path: Path) -> dict:
    return yaml.safe_load(Path(path).read_text()) or {}


def validate(r: dict) -> list[str]:
    errors = []
    for i, b in enumerate(r.get("blocks") or []):
        label = f"blocks[{i}] {b.get('unit')!r}"
        if b.get("class") not in CLASSES:
            errors.append(f"{label}: unknown class {b.get('class')!r}")
        has_url = any(str(s).startswith(("http://", "https://")) for s in b.get("sources") or [])
        st = b.get("statement") or {}
        has_statement = all(str(st.get(k) or "").strip() for k in ("who", "date", "channel", "quote"))
        if not (has_url or has_statement):
            errors.append(f"{label}: no source URL (a search summary is not a source; open the page) "
                          f"and no first-hand statement {{who, date, channel, quote}}")
        if b.get("unit") == ANY and b.get("class") == "time_fx":
            errors.append(f"{label}: time_fx cannot be 'any' — name the delay/reverb unit")
        if b.get("era") != "record":
            errors.append(f"{label}: era {b.get('era')!r} — only the rig of the recording counts")
    return errors


def sourced_units(r: dict) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for b in r.get("blocks") or []:
        if b.get("era") == "record" and b.get("class") in CLASSES:
            out.setdefault(b["class"], set()).add(b["unit"])
    return out
