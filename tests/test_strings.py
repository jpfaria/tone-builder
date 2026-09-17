from tests.synth import copy_render, note, write
from tone_builder.strings import choose_strings, library_by_midi
from tone_builder.target import build_target


def _library(root):
    pos = root / "g" / "pos5"
    write(pos / "c1-64-E4.wav", note(64, start_s=0.02, gains_db=[0, 8, -8, 8, -8, 8, -8, 8]))
    write(pos / "c2-64-E4.wav", note(64, start_s=0.02))
    write(pos / "c2-60-C4.wav", note(60, start_s=0.02))
    (root / "g" / "guitarra.yaml").write_text("name: g\n")
    return root


def test_library_by_midi_groups_every_string(tmp_path):
    by = library_by_midi(_library(tmp_path), "g", "pos5")
    assert sorted(p.name for p in by[64]) == ["c1-64-E4.wav", "c2-64-E4.wav"]


def test_string_is_chosen_by_measurement(tmp_path):
    by = library_by_midi(_library(tmp_path), "g", "pos5")
    x = note(64)
    target = build_target(x, x, {64})
    out = choose_strings(target, by, copy_render, tmp_path / "w")
    assert len(out) == 1
    assert out[0]["di"].name == "c2-64-E4.wav"
    assert len(out[0]["alternatives"]) == 2


def test_note_without_library_pair_is_left_out(tmp_path):
    by = library_by_midi(_library(tmp_path), "g", "pos5")
    x = note(67)
    assert choose_strings(build_target(x, x, {67}), by, copy_render, tmp_path / "w") == []
