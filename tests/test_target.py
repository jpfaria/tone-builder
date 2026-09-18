import numpy as np
import pytest

from tests.synth import SR, note
from tone_builder.target import (MIN_HARMONICS, build_chord_target, build_target, chord_freqs,
                                  freqs_of, in_window, midi_hz)


def _chord(midis, **k):
    return sum(note(m, **k) for m in midis)


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


def test_chord_frequencies_drop_shared_harmonics():
    f = chord_freqs([40, 52])          # E2 and E3: every E3 harmonic is an E2 harmonic
    e2 = midi_hz(40)
    assert all(abs(x / e2 - round(x / e2)) < 0.03 for x in f)
    assert not any(abs(x - 2 * e2) / x < 0.024 for x in f)


def test_chord_target_reads_the_record_on_each_note():
    # seconds=1.0 (vs. the note() default 1.5): at 1.5s the decaying E2+B2+G#3 mix beats into a
    # second spurious onset around 1.47s (note_onsets sees env rise 1.5x on the interference
    # hump) that has nothing to do with the code under test; 1.0s keeps the one real attack.
    x = _chord([40, 47, 56], n_harm=12, seconds=1.0)
    t = build_chord_target(x, x)
    assert len(t) == 1 and t[0]["kind"] == "chord" and t[0]["midis"] == [40, 47, 56]
    assert t[0]["name"] == "E2+B2+G#3"
    assert sum(t[0]["accepted"]) >= MIN_HARMONICS


def test_chord_target_honours_the_window_and_counts():
    x = _chord([40, 47, 56], n_harm=12, seconds=1.0)
    stats = {}
    assert build_chord_target(x, x, window=(1.0, None), stats=stats) == []
    assert stats["outside_window"] == 1


def test_a_note_at_a_chord_attack_is_dropped_the_chord_wins():
    from tone_builder.target import merge_targets
    notes = [{"kind": "note", "start_s": 1.02, "midi": 40},     # the power chord's root, 20 ms after
             {"kind": "note", "start_s": 3.0, "midi": 45}]      # a note on its own
    chords = [{"kind": "chord", "start_s": 1.0, "midis": [40, 47]}]
    stats = {}
    out = merge_targets(notes, chords, stats)
    assert [(e["kind"], e["start_s"]) for e in out] == [("chord", 1.0), ("note", 3.0)]
    assert stats["notes_in_chord"] == 1
