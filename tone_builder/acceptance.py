"""Decides whether a recorded take goes into the library.

Measuring the take is tone-analyzer's job (`take_metrics`); this module only
applies the criteria.
"""

from __future__ import annotations

MIN_DURATION_S = 0.67
# The 96 notes accepted on 2026-09-15 (PRS SE Silver Sky, pos5) measure SNR
# min 10.8 dB, median 18.1 dB. 10 dB keeps every one of them and rejects takes
# whose note is barely above the room/interface noise.
MIN_SNR_DB = 10.0


def judge_take(metrics: dict, expected_midi: int) -> dict:
    reasons: list[str] = []
    if metrics.get("midi") != expected_midi:
        reasons.append("pitch")
    if (metrics.get("duration_s") or 0.0) < MIN_DURATION_S:
        reasons.append("duration")
    if (metrics.get("saturated_samples") or 0) > 0:
        reasons.append("saturation")
    snr = metrics.get("snr_db")
    if snr is None or snr < MIN_SNR_DB:
        reasons.append("snr")
    return {"accepted": not reasons, "reasons": reasons}
