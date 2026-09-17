import pytest

from tests.synth import copy_render, note, silent_render, write
from tone_builder.render import RenderError, measure, render_note
from tone_builder.target import build_target


def test_silent_render_is_rejected(tmp_path):
    di = write(tmp_path / "di.wav", note(62, start_s=0.02))
    with pytest.raises(RenderError):
        render_note(silent_render, di, tmp_path / "w", "x")


def test_render_that_writes_nothing_is_rejected(tmp_path):
    di = write(tmp_path / "di.wav", note(62, start_s=0.02))
    with pytest.raises(RenderError):
        render_note(lambda s, d: None, di, tmp_path / "w", "x")


def test_measure_keeps_assignment_order(tmp_path):
    x = note(62)
    t = build_target(x, x, {62})[0]
    good = write(tmp_path / "good.wav", note(62, start_s=0.02))
    bad = write(tmp_path / "bad.wav", note(62, start_s=0.02, gains_db=[0, 6, -6, 6, -6, 6, -6, 6]))
    r = measure(copy_render, [{"note": t, "di": good}, {"note": t, "di": bad}], tmp_path / "w")
    assert r["per_note"][0] < 0.5 < 5.0 < r["per_note"][1]
    assert r["deviation"] == pytest.approx(sum(r["per_note"]) / 2)
