from pathlib import Path

import pytest

from tone_builder import library
from tone_builder.validator import known_truth

ROOT = library.library_dir()


def test_known_truth_chords_on_synthetic_library(tmp_path):
    from tests.synth import note, write
    from tone_builder import library
    from tone_builder.validator import known_truth_chords
    by = {}
    for s, base in library.STANDARD_TUNING.items():
        for fret in range(0, 8):
            m = base + fret
            by.setdefault(m, []).append(write(tmp_path / "lib" / library.note_filename(s, m),
                                              note(m, start_s=0.02, n_harm=12)))
    # dominance_db=40: a synthetic sanity check of the plumbing (voicings -> sum_di -> detect_chords),
    # not the real acceptance gate. The accompaniment's bass line is itself a tonal harmonic series
    # (see validator.py docstring); measured (2026-09-18), salience keeps false_notes == 0 only from
    # ~35 dB of guitar dominance up. The real -6 dB gate is tests/test_real_library.py (Task 12), on
    # actual guitar recordings, which have a real attack transient instead of note()'s flat onset.
    r = known_truth_chords(by, "salience", dominance_db=40.0, workdir=tmp_path / "w")
    assert r["chords"] >= 4
    assert r["set_ok_pct"] >= 90.0 and r["false_notes"] == 0


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
