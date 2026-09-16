from tone_builder.acceptance import judge_take

GOOD = {"midi": 64, "duration_s": 0.9, "saturated_samples": 0, "snr_db": 18.0}


def test_good_take_is_accepted():
    assert judge_take(GOOD, 64) == {"accepted": True, "reasons": []}


def test_each_criterion_rejects():
    assert judge_take({**GOOD, "midi": 52}, 64)["reasons"] == ["pitch"]
    assert judge_take({**GOOD, "midi": None}, 64)["reasons"] == ["pitch"]
    assert judge_take({**GOOD, "duration_s": 0.5}, 64)["reasons"] == ["duration"]
    assert judge_take({**GOOD, "saturated_samples": 1}, 64)["reasons"] == ["saturation"]
    assert judge_take({**GOOD, "snr_db": 9.9}, 64)["reasons"] == ["snr"]
    assert judge_take({**GOOD, "snr_db": None}, 64)["reasons"] == ["snr"]


def test_all_reasons_reported_together():
    bad = {"midi": 50, "duration_s": 0.1, "saturated_samples": 10, "snr_db": 2.0}
    r = judge_take(bad, 64)
    assert r["accepted"] is False
    assert r["reasons"] == ["pitch", "duration", "saturation", "snr"]
