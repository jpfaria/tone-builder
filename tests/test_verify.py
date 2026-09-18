import soundfile as sf

from tests.synth import note, write
from tone_builder.target import build_target
from tone_builder.verify import TOLERANCE_DB, verify


def _render(gains):
    def r(src, dst):
        midi = int(src.stem.split("-")[1])
        sf.write(str(dst), note(midi, start_s=0.02, gains_db=gains), 48000, subtype="FLOAT")
    return r


def _case(tmp_path):
    disc = note(62, gains_db=[0, 4, -4, 4, -4, 4, -4, 4])
    target = build_target(disc, disc, {62})
    di = write(tmp_path / "c2-62-D4.wav", note(62, start_s=0.02))
    report = {"notes": [{"name": "D4", "start_s": target[0]["start_s"], "di": str(di), "deviation_db": None}]}
    return target, report


def test_saved_preset_that_renders_the_same_passes(tmp_path):
    target, report = _case(tmp_path)
    first = verify(report, target, _render([0, 1, -1, 1, -1, 1, -1, 1]), tmp_path / "a")
    report["final_deviation_db"] = first["deviation_db"]
    again = verify(report, target, _render([0, 1, -1, 1, -1, 1, -1, 1]), tmp_path / "b")
    assert again["match"] is True and abs(again["diff_db"]) <= TOLERANCE_DB


def test_saved_preset_that_differs_fails(tmp_path):
    target, report = _case(tmp_path)
    report["final_deviation_db"] = verify(report, target, _render([0, 4, -4, 4, -4, 4, -4, 4]), tmp_path / "a")["deviation_db"]
    bad = verify(report, target, _render([0, -4, 4, -4, 4, -4, 4, -4]), tmp_path / "b")
    assert bad["match"] is False


def _jitter(base, amp):
    """A device that does not repeat itself: each call moves the harmonics a little."""
    calls = [0]

    def r(src, dst):
        calls[0] += 1
        s = amp if calls[0] % 2 else -amp
        _render([g + (s if i else 0) * (-1) ** i for i, g in enumerate(base)])(src, dst)
    return r


def test_device_that_does_not_repeat_itself_widens_the_tolerance(tmp_path):
    target, report = _case(tmp_path)
    base = [0, 1, -1, 1, -1, 1, -1, 1]
    report["final_deviation_db"] = verify(report, target, _jitter(base, 0.5), tmp_path / "a", repeats=1)["deviation_db"]
    r = verify(report, target, _jitter(base, 0.5), tmp_path / "b", repeats=4)
    assert r["repeat_sd_db"] > 0 and r["tolerance_db"] > TOLERANCE_DB
    assert r["match"] is True


def test_different_preset_still_fails_on_a_device_that_does_not_repeat_itself(tmp_path):
    target, report = _case(tmp_path)
    report["final_deviation_db"] = verify(report, target, _jitter([0, 4, -4, 4, -4, 4, -4, 4], 0.5),
                                          tmp_path / "a", repeats=1)["deviation_db"]
    bad = verify(report, target, _jitter([0, -4, 4, -4, 4, -4, 4, -4], 0.5), tmp_path / "b", repeats=4)
    assert bad["match"] is False
