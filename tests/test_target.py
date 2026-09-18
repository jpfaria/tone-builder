import numpy as np
import pytest

from tests.synth import SR, note
from tone_builder.target import MIN_HARMONICS, build_target, freqs_of, in_window, midi_hz


def test_target_note_takes_level_from_the_record():
    x = note(62)
    t = build_target(x, x, {62})
    assert len(t) == 1
    assert t[0]["midi"] == 62
    assert sum(t[0]["accepted"]) >= MIN_HARMONICS
    assert abs((t[0]["level_db"][1] - t[0]["level_db"][0]) - (-6.0)) < 1.0


def test_note_without_library_pair_is_skipped():
    x = note(62)
    assert build_target(x, x, {60}) == []


def test_record_without_the_guitar_gives_no_target():
    lead = note(62)
    disc = np.random.default_rng(0).normal(0, 0.3, len(lead))
    assert build_target(disc, lead, {62}) == []


def test_window_keeps_only_attacks_inside_it():
    x = np.concatenate([note(62), note(64)])   # attacks at 0.5 s and 3.0 s
    assert [n["midi"] for n in build_target(x, x, {62, 64}, window=(2.0, None))] == [64]
    assert [n["midi"] for n in build_target(x, x, {62, 64}, window=(None, 2.0))] == [62]


def test_in_window_bounds():
    assert in_window(1.0, None) and in_window(1.0, (1.0, 2.0)) and not in_window(2.0, (1.0, 2.0))


def test_note_entry_carries_kind_and_frequencies():
    x = note(62)
    t = build_target(x, x, {62})[0]
    assert t["kind"] == "note"
    assert t["freqs_hz"][2] == pytest.approx(3 * midi_hz(62))
    assert len(t["freqs_hz"]) == len(t["level_db"]) == len(t["accepted"])


def test_old_target_json_without_frequencies_still_reads():
    assert freqs_of({"midi": 69})[1] == pytest.approx(880.0)
