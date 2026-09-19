from pathlib import Path

import numpy as np

from tone_builder import library, recorder


def _note(midi: int, sr: int, dur: float, gain: float = 0.5) -> np.ndarray:
    t = np.arange(int(dur * sr)) / sr
    f0 = 440.0 * 2 ** ((midi - 69) / 12)
    x = sum(10 ** (db / 20) * np.sin(2 * np.pi * k * f0 * t) for k, db in enumerate([0, -6, -12], 1))
    x = x * np.minimum(t / 0.005, 1) * np.exp(-t / 1.5)
    return (gain * x / np.abs(x).max()).astype(np.float32)


def _string_take(midis: list[int], sr: int, noise: float = 1e-4, clip_midi: int | None = None) -> np.ndarray:
    rng = np.random.default_rng(42)
    parts = [np.zeros(int(0.5 * sr), dtype=np.float32)]
    for m in midis:
        n = _note(m, sr, 1.5, gain=3.0 if m == clip_midi else 0.5)
        parts += [np.clip(n, -1, 1), np.zeros(int(0.5 * sr), dtype=np.float32)]
    x = np.concatenate(parts)
    return (x + rng.standard_normal(len(x)).astype(np.float32) * noise).astype(np.float32)


def test_record_uses_given_device_and_channel():
    calls = {}

    def fake_playrec(out, samplerate, device, input_mapping, output_mapping, dtype):
        calls.update(device=device, input_mapping=input_mapping, sr=samplerate, n=len(out))
        return np.zeros((len(out), 1), dtype=np.float32)

    x = recorder.record(2.0, device="Quantum HD 8", channel=3, playrec=fake_playrec)
    assert calls["device"] == "Quantum HD 8"
    assert calls["input_mapping"] == [3]
    assert calls["sr"] == 48000 and calls["n"] == 96000
    assert x.shape == (96000,)


def test_cut_notes_finds_expected():
    sr = 48000
    x = _string_take([64, 65, 66], sr)
    cuts = recorder.cut_notes(x, sr, [64, 65, 66, 67])
    assert sorted(cuts) == [64, 65, 66]
    assert all(len(c) >= int(0.67 * sr) for c in cuts.values())


def test_save_chord_keeps_takes_with_the_right_notes(tmp_path: Path):
    from tests.synth import SR as SYNTH_SR
    from tests.synth import note as snote

    def chord(midis: list[int]) -> np.ndarray:
        return sum(snote(m, seconds=1.0, start_s=0.3) for m in midis)

    sig = np.concatenate([chord([40, 47, 56]), chord([40, 47, 56]), chord([41, 48, 57])])
    voicing = [(6, 40), (5, 47), (3, 56)]
    rep = recorder.save_chord(tmp_path, "g", "pos5", voicing, sig, SYNTH_SR)
    assert rep["accepted"] == [1, 2]
    assert 3 in rep["rejected"]
    assert len(library.list_chords(tmp_path, "g", "pos5")) == 2


def test_save_string_accepts_good_rejects_clipped(tmp_path: Path):
    sr = 48000
    (tmp_path / "g").mkdir()
    library.write_yaml(tmp_path / "g" / "guitarra.yaml", {"name": "test"})
    x = _string_take([64, 65, 66], sr, clip_midi=65)
    report = recorder.save_string(tmp_path, "g", "pos5", 1, x, sr)
    assert report["accepted"] == [64, 66]
    assert report["rejected"] == {65: ["saturation"]}
    assert 67 in report["missing"]
    names = [p.name for p in library.list_notes(tmp_path, "g", "pos5")]
    assert names == ["c1-64-E4.wav", "c1-66-F#4.wav"]
    med = library.read_yaml(tmp_path / "g" / "pos5" / "medicao.yaml")
    assert med["c1-65-F4"]["accepted"] is False
    assert med["c1-64-E4"]["accepted"] is True


def test_save_string_keeps_the_raw_take_so_a_missing_note_can_be_diagnosed(tmp_path: Path):
    sr = 48000
    x = _string_take([64, 66], sr)
    recorder.save_string(tmp_path, "g", "pos5", 1, x, sr)
    raw = tmp_path / "g" / "pos5" / "_takes" / "c1.wav"
    assert raw.exists()
    assert [p.name for p in library.list_notes(tmp_path, "g", "pos5")] == ["c1-64-E4.wav", "c1-66-F#4.wav"]


def _real_take(string: int = 3):
    """Real takes of a bridge pickup (19/09/2026), the ones that showed the defects."""
    import soundfile as sf

    return sf.read(Path(__file__).parent / "data" / f"c{string}-bridge-take.flac", dtype="float32")


def test_cut_notes_keeps_a_note_whose_attack_reads_an_octave_low():
    # 19/09/2026: fret 2 of string 3 (A3=57) read 45 on its first 6 of 21 frames and the whole note was dropped
    x, sr = _real_take()
    assert 57 in recorder.cut_notes(x, sr, list(range(55, 71)))


def test_save_string_measures_noise_even_when_the_cut_starts_on_the_attack(tmp_path: Path):
    x, sr = _real_take()
    report = recorder.save_string(tmp_path, "g", "pos1", 3, x, sr)
    assert not [m for m, why in report["rejected"].items() if why == ["snr"]]


def test_save_string_names_a_note_that_reads_as_its_own_subharmonic(tmp_path: Path):
    # string 1: fret 11 read 63 (an octave low) on 17 of 21 frames, fret 15 read 60 and 67 (f/3, f/2),
    # fret 2 read 54 on the middle frame. None of those is a note of the string: the detector slipped, not the player
    x, sr = _real_take(1)
    report = recorder.save_string(tmp_path, "g", "pos1", 1, x, sr)
    assert report == {"accepted": list(range(64, 80)), "rejected": {}, "missing": []}


def test_a_lower_note_really_played_is_not_renamed_to_its_octave():
    sr = 48000
    spans = recorder.note_spans(_string_take([67], sr), sr, list(range(64, 80)))
    assert list(spans) == [67]


def test_the_noise_read_on_the_take_wins_over_the_one_read_on_the_saved_note():
    # PRS SE Paul's Guitar, 19/09/2026: 13.5 dB on the take, 7.9 dB read again from the note's 20 ms of pre-roll
    sr = 48000
    note = _note(64, sr, 1.0) * np.exp(-np.arange(sr) / sr / 0.03)   # a short note: little energy over the 0.6 s read
    tail = 0.04 * np.sin(2 * np.pi * 300 * np.arange(int(0.02 * sr)) / sr)   # the note before it, still ringing
    piece = np.concatenate([tail, note]).astype(np.float32)
    assert recorder.measure_and_judge(piece, sr, 64)["reasons"] == ["snr"]
    assert recorder.measure_and_judge(piece, sr, 64, recorded_snr_db=13.5)["accepted"] is True
