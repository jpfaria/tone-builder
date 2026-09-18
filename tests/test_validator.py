from pathlib import Path

import pytest

from tone_builder import library
from tone_builder.validator import known_truth

ROOT = library.library_dir()


def _synthetic_chord_library(tmp_path):
    from tests.synth import note, write
    by = {}
    for s, base in library.STANDARD_TUNING.items():
        for fret in range(0, 8):
            m = base + fret
            by.setdefault(m, []).append(write(tmp_path / "lib" / library.note_filename(s, m),
                                              note(m, start_s=0.02, n_harm=12)))
    return by


def test_known_truth_chords_on_synthetic_library_has_the_documented_shape(tmp_path):
    # This is a plumbing smoke test (voicings -> sum_di -> detect_chords -> levels_at), not the
    # real acceptance gate — that is the -6 dB criterion measured on the real library
    # (tests/test_real_library.py, Task 12). At the spec's default stagger/residue/dominance it may
    # not clear that bar; this only checks the result has the right shape and enough chords ran.
    from tone_builder.validator import known_truth_chords
    by = _synthetic_chord_library(tmp_path)
    r = known_truth_chords(by, "salience", workdir=tmp_path / "w")
    assert set(r) == {"chords", "set_ok_pct", "false_notes", "error_db", "false_positives",
                       "dominance_db", "detector"}
    assert r["chords"] >= 4


def test_known_truth_chords_easy_case_is_perfect(tmp_path):
    # No stagger, no separation residue: the detector's easiest possible case. If this fails it is
    # a tone-analyzer detector bug, not a validator calibration issue — report it, do not patch
    # tone-analyzer from here.
    from tone_builder.validator import known_truth_chords
    by = _synthetic_chord_library(tmp_path)
    r = known_truth_chords(by, "salience", stagger_s=0.0, residue_db=None, workdir=tmp_path / "w")
    assert r["set_ok_pct"] == 100.0 and r["false_notes"] == 0, r


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
