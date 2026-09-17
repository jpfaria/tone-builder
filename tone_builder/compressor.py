"""A compressor counts as tested only when it measurably compresses.

On 16/09 thresholds of -40/-30/-20 dB removed 1.2/0.1/0.0 dB: the library DI is
quiet and the block did nothing, which almost shipped as "compressor tested".
Measured as in round 8: RMS of the DI minus RMS of the compressor alone on the
same note, with the compressor's output gain at 0.
"""

from __future__ import annotations

import numpy as np

from tone_builder.audio import rms_db

MIN_GAIN_REDUCTION_DB = 3.0


def gain_reduction_db(dry: np.ndarray, wet: np.ndarray) -> float:
    return rms_db(dry) - rms_db(wet)


def is_tested(gr_db: float) -> bool:
    return gr_db >= MIN_GAIN_REDUCTION_DB
