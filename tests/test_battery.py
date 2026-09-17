import numpy as np
import soundfile as sf

from tests.synth import note, write
from tone_builder.battery import CLASSES, Candidate, run_battery
from tone_builder.target import build_target

TARGET_GAINS = [0, 3, -3, 3, -3, 3, -3, 3]


def _tilt(gains):
    """A fake device: re-synthesises the DI note with extra per-harmonic gains."""
    def render(src, dst):
        midi = int(src.stem.split("-")[1])
        sf.write(str(dst), note(midi, start_s=0.02, gains_db=gains), 48000, subtype="FLOAT")
    return render


def _setup(tmp_path):
    midis = [60, 62, 64, 65, 67, 69, 71, 72]
    assignments = []
    for i, m in enumerate(midis):
        disc = note(m, gains_db=TARGET_GAINS)
        t = build_target(disc, disc, {m})[0]
        di = write(tmp_path / "lib" / f"c1-{m}-X.wav", note(m, start_s=0.02))
        assignments.append({"note": t, "di": di})
    return assignments


RESEARCH = {"blocks": [{"class": "single_drive", "unit": "TS", "era": "record", "sources": ["https://x"]}],
            "not_found": [{"class": "time_fx", "searched": ["https://y"]}]}


def test_sourced_candidate_wins_over_a_better_unsourced_one(tmp_path):
    a = _setup(tmp_path)
    cands = [
        Candidate("ts", "single_drive", "TS", _tilt([0, 2, -2, 2, -2, 2, -2, 2])),
        Candidate("fuzz", "single_drive", "Fuzz", _tilt(TARGET_GAINS)),
    ]
    r, _ = run_battery(_tilt([0] * 8), cands, a, RESEARCH, tmp_path / "w")
    assert r["single_drive"]["status"] == "measured"
    assert r["single_drive"]["sourced"]["best"] == "ts"
    assert r["single_drive"]["unsourced_best"]["name"] == "fuzz"


def test_compressor_that_does_not_compress_is_not_tested(tmp_path):
    a = _setup(tmp_path)
    cands = [Candidate("comp", "compressor", None, _tilt([0] * 8), gain_reduction_db=0.0)]
    r, _ = run_battery(_tilt([0] * 8), cands, a, RESEARCH, tmp_path / "w")
    assert r["compressor"]["status"] == "not_tested"
    assert "3 dB" in r["compressor"]["reason"]


def test_class_without_candidate_takes_reason_from_research(tmp_path):
    r, _ = run_battery(_tilt([0] * 8), [], _setup(tmp_path), RESEARCH, tmp_path / "w")
    assert set(r) == set(CLASSES)
    assert r["time_fx"]["status"] == "no_candidate"
    assert r["time_fx"]["reason"]
    assert r["cab"]["reason"] is None


def test_derived_unit_is_choosable_without_a_fake_source(tmp_path):
    a = _setup(tmp_path)
    cands = [Candidate("pair", "stacked_drives", "TS + BB", _tilt(TARGET_GAINS))]
    r, _ = run_battery(_tilt([0] * 8), cands, a, RESEARCH, tmp_path / "w",
                       derived_units={"stacked_drives": {"TS + BB"}})
    assert r["stacked_drives"]["sourced"]["best"] == "pair"
    assert r["stacked_drives"]["derived_from_sources"] is True
    assert all("derived" not in s for b in RESEARCH["blocks"] for s in b["sources"])
