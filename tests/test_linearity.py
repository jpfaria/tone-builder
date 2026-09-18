"""How non-linear a chain is, with no reference recording: the same notes at two input levels
20 dB apart. A linear chain moves every harmonic by exactly 20 dB, whatever its EQ."""
import numpy as np
import soundfile as sf

from tests.synth import note, write
from tone_builder.linearity import nonlinearity


def _chain(fn):
    def render(src, dst):
        x, sr = sf.read(str(src))
        sf.write(str(dst), fn(x).astype(np.float32), sr, subtype="FLOAT")
    return render


def _dis(tmp_path):
    return [write(tmp_path / "lib" / f"c1-{m}-X.wav", note(m, start_s=0.02)) for m in (52, 64, 69)]


def test_a_linear_chain_with_any_eq_reads_zero(tmp_path):
    eq = _chain(lambda x: 0.3 * np.convolve(x, [1.0, -0.6, 0.2], mode="same"))
    r = nonlinearity(eq, _dis(tmp_path), tmp_path / "w")
    assert r["nonlinearity_db"] < 0.2 and abs(r["compression_db"]) < 0.2


def test_a_clipping_chain_reads_high_and_a_harder_clip_reads_higher(tmp_path):
    soft = nonlinearity(_chain(lambda x: np.tanh(3 * x)), _dis(tmp_path), tmp_path / "a")
    hard = nonlinearity(_chain(lambda x: np.tanh(12 * x)), _dis(tmp_path), tmp_path / "b")
    assert soft["nonlinearity_db"] > 1.0
    assert hard["nonlinearity_db"] > soft["nonlinearity_db"]
    assert hard["compression_db"] > soft["compression_db"] > 0


def test_rank_orders_the_options_cleanest_first(tmp_path):
    from tone_builder.linearity import rank

    chains = {"clean": lambda x: 0.5 * x, "crunch": lambda x: np.tanh(3 * x), "fuzz": lambda x: np.tanh(20 * x)}
    rows = rank(list(chains), lambda name: _chain(chains[name]), _dis(tmp_path), tmp_path / "w", jobs=3)
    assert [r["name"] for r in rows] == ["clean", "crunch", "fuzz"]
    assert rows[0]["nonlinearity_db"] < rows[1]["nonlinearity_db"] < rows[2]["nonlinearity_db"]
