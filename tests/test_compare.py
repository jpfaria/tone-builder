import numpy as np

from tests.synth import note
from tone_builder.compare import mean_deviation, note_deviation
from tone_builder.target import build_target


def _target():
    x = note(62)
    return build_target(x, x, {62})[0]


def test_same_note_has_no_deviation():
    assert note_deviation(_target(), note(62, start_s=0.02))["rms_db"] < 0.5


def test_alternating_6_db_error_measures_6_db():
    g = [0, 6, -6, 6, -6, 6, -6, 6]
    d = note_deviation(_target(), note(62, start_s=0.02, gains_db=g))
    assert abs(d["rms_db"] - 6.0) < 1.0


def test_level_does_not_count():
    a = note_deviation(_target(), note(62, start_s=0.02, gains_db=[0, 6, -6, 6, -6, 6, -6, 6]))
    b = note_deviation(_target(), 0.1 * note(62, start_s=0.02, gains_db=[0, 6, -6, 6, -6, 6, -6, 6]))
    assert abs(a["rms_db"] - b["rms_db"]) < 0.1


def test_silent_render_gives_none():
    assert note_deviation(_target(), np.zeros(48000)) is None


def test_mean_skips_missing_notes():
    assert mean_deviation([{"rms_db": 2.0}, None, {"rms_db": 4.0}]) == 3.0
    assert mean_deviation([None]) is None
