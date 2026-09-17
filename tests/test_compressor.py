import numpy as np
import pytest

from tone_builder.compressor import gain_reduction_db, is_tested


def test_half_amplitude_is_6_db_and_counts():
    x = np.random.default_rng(0).normal(0, 0.1, 48000)
    gr = gain_reduction_db(x, 0.5 * x)
    assert gr == pytest.approx(6.0206, abs=1e-3)
    assert is_tested(gr)


def test_under_3_db_is_not_tested():
    x = np.random.default_rng(0).normal(0, 0.1, 48000)
    gr = gain_reduction_db(x, 0.8 * x)
    assert gr == pytest.approx(1.938, abs=1e-3)
    assert not is_tested(gr)
