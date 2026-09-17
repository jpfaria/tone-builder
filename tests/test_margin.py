import numpy as np
import soundfile as sf

from tests.synth import note, write
from tone_builder.margin import margin_ok, measure_margin


def _hot(src, dst):
    x, sr = sf.read(str(src))
    sf.write(str(dst), np.clip(4 * x, -1, 1), sr, subtype="FLOAT")


def test_boosted_di_that_saturates_fails(tmp_path):
    di = write(tmp_path / "di.wav", note(62, start_s=0.02, amp=0.1))
    m = measure_margin(_hot, [di], tmp_path / "w")
    assert m[0]["saturated"] == 0
    assert m[18]["saturated"] > 0
    assert not margin_ok(m)


def test_quiet_chain_passes(tmp_path):
    di = write(tmp_path / "di.wav", note(62, start_s=0.02, amp=0.01))
    m = measure_margin(lambda s, d: sf.write(str(d), sf.read(str(s))[0], 48000, subtype="FLOAT"), [di], tmp_path / "w")
    assert margin_ok(m)
    assert set(m) == {0, 12, 18}
    assert all(p.parent == tmp_path / "w" for p in (tmp_path / "w").iterdir())
