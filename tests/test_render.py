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


def test_a_measured_render_is_not_kept_on_disk(tmp_path, monkeypatch):
    """A unit like "Fender" is ~300 captures x dozens of notes: kept renders fill the disk."""
    from tests.synth import note, write
    from tone_builder.render import render_note

    di = write(tmp_path / "c1-62-D4.wav", note(62))
    copy = lambda src, dst: write(dst, note(62))
    assert render_note(copy, di, tmp_path / "w", "a").size > 0
    assert not (tmp_path / "w" / "a.wav").exists()
    monkeypatch.setenv("TONE_BUILDER_KEEP_RENDERS", "1")
    render_note(copy, di, tmp_path / "w", "b")
    assert (tmp_path / "w" / "b.wav").exists()


def test_a_measurement_already_on_disk_is_not_rendered_again(tmp_path):
    """A brand-wide unit takes hours; a build killed at capture 323 of 400 must resume, not restart."""
    from tests.synth import note, write
    from tone_builder.render import measure
    from tone_builder.target import build_target

    disc = note(62)
    a = [{"note": build_target(disc, disc, {62})[0], "di": write(tmp_path / "c1-62-D4.wav", note(62, start_s=0.02))}]
    calls = []

    def render(src, dst):
        calls.append(src)
        write(dst, note(62, start_s=0.02))

    first = measure(render, a, tmp_path / "w")
    again = measure(render, a, tmp_path / "w")
    assert len(calls) == 1 and again == first
    other = [{**a[0], "note": {**a[0]["note"], "start_s": 9.9}}]       # another target: the cache must not answer
    measure(render, other, tmp_path / "w")
    assert len(calls) == 2
