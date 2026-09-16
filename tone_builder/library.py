"""On-disk layout of the guitar library.

biblioteca/<guitar>/guitarra.yaml
biblioteca/<guitar>/<position>/c<string>-<midi>-<note>.wav
biblioteca/<guitar>/<position>/medicao.yaml
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import yaml
from tone_analyzer.notes import midi_name

STANDARD_TUNING: dict[int, int] = {6: 40, 5: 45, 4: 50, 3: 55, 2: 59, 1: 64}
_NOTE_RE = re.compile(r"^c([1-6])-(\d+)-([A-G]#?-?\d)\.wav$")


def library_dir() -> Path:
    env = os.environ.get("TONE_BUILDER_LIBRARY")
    if env:
        return Path(env)
    return Path(__file__).resolve().parent.parent / "biblioteca"


def note_filename(string: int, midi: int) -> str:
    return f"c{string}-{midi}-{midi_name(midi)}.wav"


def parse_note_filename(name: str) -> tuple[int, int] | None:
    m = _NOTE_RE.match(name)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


def expected_midis(
    string: int, frets: range = range(16), tuning: dict[int, int] = STANDARD_TUNING
) -> list[int]:
    return [tuning[string] + f for f in frets]


def list_guitars(root: Path) -> list[str]:
    return sorted(p.name for p in root.iterdir() if p.is_dir() and (p / "guitarra.yaml").exists())


def list_positions(root: Path, guitar: str) -> list[str]:
    return sorted(p.name for p in (root / guitar).iterdir() if p.is_dir())


def list_notes(root: Path, guitar: str, position: str) -> list[Path]:
    d = root / guitar / position
    return sorted(p for p in d.iterdir() if parse_note_filename(p.name))


def read_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text()) or {}


def write_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True))
