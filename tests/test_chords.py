import numpy as np

from tests.synth import SR, note, write
from tone_builder import chords, library
from tone_builder.audio import load_mono


def _lib(tmp_path, pairs):
    """pairs: (string, midi) -> a library note file."""
    out = {}
    for s, m in pairs:
        p = write(tmp_path / "lib" / library.note_filename(s, m), note(m, start_s=0.02 + 0.01 * s))
        out.setdefault(m, []).append(p)
    return out


def test_voicing_uses_distinct_strings_and_a_4_fret_hand(tmp_path):
    by = _lib(tmp_path, [(6, 40), (5, 47), (6, 47), (4, 52), (5, 52)])
    vs = chords.voicings([40, 47, 52], by)
    strings = [[library.parse_note_filename(p.name)[0] for p in v] for v in vs]
    assert [6, 5, 4] in strings
    assert all(len(set(s)) == 3 for s in strings)
    assert [6, 6, 5] not in strings


def test_voicing_rejects_a_stretch_over_4_frets(tmp_path):
    by = _lib(tmp_path, [(6, 41), (5, 50)])     # fret 1 and fret 5
    assert chords.voicings([41, 50], by) == []


def test_summed_di_aligns_attacks(tmp_path):
    by = _lib(tmp_path, [(6, 40), (5, 47)])
    out = chords.sum_di([by[40][0], by[47][0]], tmp_path / "c.wav")
    x = load_mono(out)
    from tone_analyzer.take import take_onset
    assert abs(take_onset(x, SR) / SR - chords.PREROLL_S) < 0.01
    assert np.abs(x).max() <= 1.0


def test_recorded_chord_is_a_candidate(tmp_path):
    by = _lib(tmp_path, [(6, 40), (5, 47)])
    root = tmp_path / "root"
    write(root / "g" / "pos5" / "acordes" / library.chord_filename([(6, 40), (5, 47)], 1), note(40))
    rec = chords.recorded_by_midis(root, "g", "pos5")
    cands = chords.di_candidates([40, 47], by, rec, tmp_path / "work")
    assert {src for _, src in cands} == {"summed", "recorded"}


def test_chord_filename_round_trip():
    v = [(6, 40), (5, 47), (4, 52)]
    assert library.parse_chord_filename(library.chord_filename(v, 2)) == v


def test_voicings_include_optional_octave_doublings(tmp_path):
    # Library has 40 on string 6, 47 on string 5, and also 52 (=40+12) on string 4.
    by = _lib(tmp_path, [(6, 40), (5, 47), (4, 52)])
    vs = chords.voicings([40, 47], by)
    strings_midis = [[library.parse_note_filename(p.name) for p in v] for v in vs]
    plain = [(6, 40), (5, 47)]
    doubled = [(6, 40), (5, 47), (4, 52)]
    assert plain in strings_midis
    assert doubled in strings_midis
    assert strings_midis.index(plain) < strings_midis.index(doubled)


def test_recorded_chord_matches_by_octave_reduced_set(tmp_path):
    # Recorded file has E2(40) + B2(47) + E3(52); 52 is 40+12, so the reduced set is {40, 47}.
    by = _lib(tmp_path, [(6, 40), (5, 47)])
    root = tmp_path / "root"
    write(
        root / "g" / "pos5" / "acordes" / library.chord_filename([(6, 40), (5, 47), (4, 52)], 1),
        note(40),
    )
    rec = chords.recorded_by_midis(root, "g", "pos5")
    cands = chords.di_candidates([40, 47], by, rec, tmp_path / "work")
    assert {src for _, src in cands} == {"summed", "recorded"}
