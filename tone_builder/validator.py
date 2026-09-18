"""Known-truth validator: without it the method is opinion.

A KNOWN guitar note (from the library) is summed with an accompaniment at a
controlled dominance (RMS guitar / RMS accompaniment). The target reading
(harmonic level at k*f0 in the mix, accepted at >= 10 dB prominence) is compared
with the guitar alone.

The accompaniment is synthetic — pink noise plus a bass line with 6 harmonics,
half the power each — because songs cannot go into the repo. The original
validation (16/09) used the real no-guitar stem of Gravity and measured 1.84 dB
error with zero false positives at -6 dB dominance — but with one guitar only
(a Two-Rock render); see the stage 3 plan for the 96-note sweep.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from tone_analyzer.chords import detect_chords, levels_at
from tone_analyzer.notes import harmonic_levels
from tone_analyzer.take import take_onset

from tone_builder import chords as chords_mod
from tone_builder import library
from tone_builder.audio import SR, load_mono
from tone_builder.target import DUR_S, MIN_HARMONICS, PROMINENCE_DB, chord_freqs, midi_hz

# A false positive is a peak accepted in the mix where the guitar alone has no
# harmonic peak (prominence below this). A real guitar harmonic just under
# PROMINENCE_DB, pushed over it by the background, is not a false positive.
NO_PEAK_DB = 6.0


def _pink(n: int, rng: np.random.Generator) -> np.ndarray:
    spec = np.fft.rfft(rng.normal(size=n))
    f = np.fft.rfftfreq(n, 1 / SR)
    spec[1:] /= np.sqrt(f[1:])
    spec[0] = 0
    return np.fft.irfft(spec, n)


def _bass(n: int, rng: np.random.Generator) -> np.ndarray:
    f0 = midi_hz(int(rng.integers(28, 41)))
    t = np.arange(n) / SR
    return sum(np.sin(2 * np.pi * f0 * k * t) / k for k in range(1, 7)) * np.exp(-t * 1.0)


def _unit_rms(x: np.ndarray) -> np.ndarray:
    return x / (np.sqrt(np.mean(x ** 2)) + 1e-20)


def known_truth(notes: list[Path], dominance_db: float = -6.0, seed: int = 0) -> dict:
    rng = np.random.default_rng(seed)
    span = int(DUR_S * SR)
    errors, accepted_total, used, false_pos = [], 0, 0, 0
    for path in notes:
        parsed = library.parse_note_filename(Path(path).name)
        if parsed is None:
            continue
        f0 = midi_hz(parsed[1])
        x = load_mono(path)
        onset = take_onset(x, SR)
        if onset is None or onset + span > len(x):
            continue
        guitar = x[onset:onset + span]
        guitar = 0.35 * guitar / (np.abs(guitar).max() + 1e-12)
        acc = _unit_rms(_unit_rms(_pink(span, rng)) + _unit_rms(_bass(span, rng)))
        g_rms = np.sqrt(np.mean(guitar ** 2))
        mix = guitar + acc * g_rms / 10 ** (dominance_db / 20)
        hm = harmonic_levels(mix, SR, 0.0, f0, dur_s=DUR_S)
        hg = harmonic_levels(guitar, SR, 0.0, f0, dur_s=DUR_S)
        if hm is None or hg is None:
            continue
        ok = [pm is not None and pm >= PROMINENCE_DB and lg is not None
              for pm, lg in zip(hm["prominence_db"], hg["level_db"])]
        if sum(ok) < MIN_HARMONICS:
            continue
        used += 1
        accepted_total += sum(ok)
        false_pos += sum(1 for k, a in enumerate(ok)
                         if a and (hg["prominence_db"][k] is None or hg["prominence_db"][k] < NO_PEAK_DB))
        d = np.array([hm["level_db"][k] - hg["level_db"][k] for k, a in enumerate(ok) if a])
        errors.append(float(np.sqrt(np.mean((d - d.mean()) ** 2))))
    return {"notes": used, "harmonics_per_note": accepted_total / used if used else None,
            "error_db": float(np.mean(errors)) if errors else None, "false_positives": false_pos,
            "dominance_db": dominance_db}


CHORD_SET_OK_PCT = 90.0
STAGGER_S = 0.030      # a strum spreads the strings over up to 30 ms
# The chord detector never sees the mix in `build`: it runs on the separated guitar track, which
# still carries some of the band the separator failed to remove. RESIDUE_DB models that residue as
# pink noise 20 dB below the guitar's own RMS — quiet, but present — while the LEVEL reading (error_db,
# false_positives) keeps using the full mix at the requested `dominance_db`, exactly like the record.
RESIDUE_DB = -20.0
# interval shapes over the root, by name
SHAPES = {
    "power2": [0, 7], "power3": [0, 7, 12],
    "major-E": [0, 7, 12, 16, 19, 24], "minor-E": [0, 7, 12, 15, 19, 24],
    "major-A": [0, 7, 12, 16, 19], "minor-A": [0, 7, 12, 15, 19],
}
ROOTS = range(40, 53)   # E2..E3


def known_truth_chords(by_midi: dict, detector: str, dominance_db: float = -6.0, seed: int = 0,
                       stagger_s: float = STAGGER_S, residue_db: float | None = RESIDUE_DB,
                       workdir: Path = Path("validate-chords")) -> dict:
    rng = np.random.default_rng(seed)
    span = int(DUR_S * SR)
    n = ok = false_notes = false_pos = 0
    errors = []
    for shape, iv in SHAPES.items():
        for root in ROOTS:
            midis = [root + i for i in iv]
            vs = chords_mod.voicings(midis, by_midi)
            if not vs:
                continue
            offs = sorted(rng.uniform(0, stagger_s, len(midis))) if stagger_s else [0.0] * len(midis)
            di = chords_mod.sum_di(vs[0], Path(workdir) / f"{shape}-{root}.wav", offsets_s=list(offs))
            x = load_mono(di)
            a = int(chords_mod.PREROLL_S * SR)
            guitar = x[a:a + span]
            if len(guitar) < span:
                continue
            guitar = 0.35 * guitar / (np.abs(guitar).max() + 1e-12)
            acc = _unit_rms(_unit_rms(_pink(span, rng)) + _unit_rms(_bass(span, rng)))
            g_rms = np.sqrt(np.mean(guitar ** 2))
            mix = np.concatenate([np.zeros(SR // 2), guitar + acc * g_rms / 10 ** (dominance_db / 20), np.zeros(SR // 2)])
            if residue_db is not None:
                residue = _unit_rms(_pink(span, rng)) * g_rms * 10 ** (residue_db / 20)
                sep = np.concatenate([np.zeros(SR // 2), guitar + residue, np.zeros(SR // 2)])
            else:
                sep = np.concatenate([np.zeros(SR // 2), guitar, np.zeros(SR // 2)])
            n += 1
            heard = detect_chords(sep, SR, dur_s=DUR_S, detector=detector)
            got = heard[0]["midis"] if heard else []
            truth_r = chords_mod.reduce_octaves(midis)
            got_r = chords_mod.reduce_octaves(got)
            ok += got_r == truth_r
            false_notes += len(set(got_r) - set(truth_r))
            freqs = chord_freqs(sorted(midis))
            hm = levels_at(mix, SR, 0.5, freqs, dur_s=DUR_S)
            hg = levels_at(guitar, SR, 0.0, freqs, dur_s=DUR_S)
            if hm is None or hg is None:
                continue
            acc_k = [pm is not None and pm >= PROMINENCE_DB and lg is not None
                     for pm, lg in zip(hm["prominence_db"], hg["level_db"])]
            if sum(acc_k) < MIN_HARMONICS:
                continue
            false_pos += sum(1 for k, a_ in enumerate(acc_k)
                             if a_ and (hg["prominence_db"][k] is None or hg["prominence_db"][k] < NO_PEAK_DB))
            d = np.array([hm["level_db"][k] - hg["level_db"][k] for k, a_ in enumerate(acc_k) if a_])
            errors.append(float(np.sqrt(np.mean((d - d.mean()) ** 2))))
    return {"chords": n, "set_ok_pct": 100.0 * ok / n if n else None, "false_notes": false_notes,
            "error_db": float(np.mean(errors)) if errors else None, "false_positives": false_pos,
            "dominance_db": dominance_db, "detector": detector}


def summed_vs_recorded(by_midi: dict, recorded: dict, workdir: Path) -> dict:
    """Level error between a recorded chord and the library sum of the same voicing (informative)."""
    errors = []
    for paths in recorded.values():
        for p in paths:
            v = library.parse_chord_filename(p.name)
            notes = [next((q for q in by_midi.get(m, []) if library.parse_note_filename(q.name)[0] == s), None)
                     for s, m in v]
            if None in notes:
                continue
            summed = load_mono(chords_mod.sum_di(notes, Path(workdir) / f"sum-{p.stem}.wav"))
            rec = load_mono(p)
            freqs = chord_freqs(sorted(m for _, m in v))
            hr = levels_at(rec, SR, (take_onset(rec, SR) or 0) / SR, freqs, dur_s=DUR_S)
            hs = levels_at(summed, SR, chords_mod.PREROLL_S, freqs, dur_s=DUR_S)
            if hr is None or hs is None:
                continue
            ks = [k for k, (a_, b_, pr) in enumerate(zip(hr["level_db"], hs["level_db"], hr["prominence_db"]))
                  if a_ is not None and b_ is not None and pr is not None and pr >= PROMINENCE_DB]
            if len(ks) < MIN_HARMONICS:
                continue
            d = np.array([hr["level_db"][k] - hs["level_db"][k] for k in ks])
            errors.append(float(np.sqrt(np.mean((d - d.mean()) ** 2))))
    return {"pairs": len(errors), "error_db": float(np.mean(errors)) if errors else None}
