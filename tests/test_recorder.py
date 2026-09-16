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
