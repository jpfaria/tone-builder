"""The shipped library must pass its own acceptance test."""

from pathlib import Path

import pytest

from tone_builder import cli, library

ROOT = library.library_dir()


def _lfs_pointer(p: Path) -> bool:
    return p.stat().st_size < 1024 and p.read_bytes().startswith(b"version https://git-lfs")


def test_prs_silver_sky_se_pos5_has_96_notes_and_at_most_3_rejected(capsys):
    notes = library.list_notes(ROOT, "prs-silver-sky-se", "pos5")
    if notes and _lfs_pointer(notes[0]):
        pytest.skip("LFS objects not pulled")
    assert len(notes) == 96
    cli.main(["library", "check", "prs-silver-sky-se", "pos5", "--root", str(ROOT)])
    out = capsys.readouterr().out
    rejected = [line for line in out.splitlines() if line.startswith("REJECTED")]
    assert len(rejected) <= 3, rejected   # pitch 93/96 measured 2026-09-16; misses are octave errors
