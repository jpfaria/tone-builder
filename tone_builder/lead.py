"""The separated guitar track: the one given, the one already beside the record,
or a new one separated by tone-analyzer. It only locates the notes; the level is
always read on the record (separation erases harmonics above ~H6)."""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable

Separator = Callable[[Path, Path], None]


class LeadError(Exception):
    pass


def tone_analyzer_separate(disc: Path, out_dir: Path) -> None:
    """`tone-analyzer separate` from this venv: guitar.wav at 48 kHz in out_dir."""
    exe = Path(sys.executable).parent / "tone-analyzer"
    proc = subprocess.run([str(exe), "separate", str(disc), "--out-dir", str(out_dir)],
                          capture_output=True, text=True)
    if proc.returncode != 0:
        raise LeadError(f"tone-analyzer separate failed (exit {proc.returncode}): "
                        f"{(proc.stderr or proc.stdout).strip()}")


def resolve_lead(disc: Path, lead: Path | None, separate: Separator = tone_analyzer_separate) -> Path:
    if lead is not None:
        if not lead.is_file():
            raise LeadError(f"separated track not found: {lead}")
        return lead
    cached = disc.parent / "lead.wav"
    if cached.is_file():
        return cached
    with tempfile.TemporaryDirectory(prefix="tone-builder-separate-") as tmp:
        separate(disc, Path(tmp))
        guitar = Path(tmp) / "guitar.wav"
        if not guitar.is_file():
            raise LeadError(f"separation of {disc.name} wrote no guitar.wav")
        shutil.copyfile(guitar, cached)
    return cached
