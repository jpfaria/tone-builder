from pathlib import Path

import pytest

from tone_builder import library
from tone_builder.validator import known_truth

ROOT = library.library_dir()


def _notes():
    notes = library.list_notes(ROOT, "prs-silver-sky-se", "pos5")
    if not notes or notes[0].stat().st_size < 1024:
        pytest.skip("LFS objects not pulled")
    return notes[::4]


def test_known_truth_on_library_at_minus_6_db():
    r = known_truth(_notes(), dominance_db=-6.0)
    assert r["notes"] >= 12, r
    assert r["false_positives"] == 0, r
    assert r["error_db"] <= 2.0, r


def test_error_shrinks_when_the_guitar_dominates():
    notes = _notes()
    assert known_truth(notes, dominance_db=12.0)["error_db"] < known_truth(notes, dominance_db=-6.0)["error_db"]
