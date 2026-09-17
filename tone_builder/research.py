"""Step 0: the recording rig, researched with sources before anything is measured.

Without it the sweep has no right candidate and a whole block goes missing (on
Gravity the gain pedal was only found when the user asked; it moved 0.9 dB).
The research decides which blocks exist and which units enter the candidate
list; measurement only decides among them.

File format:
  song, part
  blocks:    [{class, unit, era: record|tour, sources: [url, ...]}]
  not_found: [{class, searched: [url or query, ...]}]
"""

from __future__ import annotations

from pathlib import Path

import yaml

CLASSES = ("single_drive", "stacked_drives", "boost", "compressor", "amp", "cab", "eq", "time_fx")


def load_research(path: Path) -> dict:
    return yaml.safe_load(Path(path).read_text()) or {}


def validate(r: dict) -> list[str]:
    errors = []
    for i, b in enumerate(r.get("blocks") or []):
        label = f"blocks[{i}] {b.get('unit')!r}"
        if b.get("class") not in CLASSES:
            errors.append(f"{label}: unknown class {b.get('class')!r}")
        if not any(str(s).startswith(("http://", "https://")) for s in b.get("sources") or []):
            errors.append(f"{label}: no source URL (a search summary is not a source; open the page)")
        if b.get("era") != "record":
            errors.append(f"{label}: era {b.get('era')!r} — only the rig of the recording counts")
    return errors


def sourced_units(r: dict) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for b in r.get("blocks") or []:
        if b.get("era") == "record" and b.get("class") in CLASSES:
            out.setdefault(b["class"], set()).add(b["unit"])
    return out
