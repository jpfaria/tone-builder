"""Record one string of a guitar, cut the notes, test each one, save only the accepted ones."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile as sf
from tone_analyzer.notes import detect_notes
from tone_analyzer.take import take_metrics

from tone_builder import library
from tone_builder.acceptance import judge_take
from tone_builder.chords import reduce_octaves

SR = 48000
PREROLL_S = 0.02
METRIC_PREROLL_S = 0.15  # the noise floor is read before the attack; 20 ms of pre-roll leaves nothing to read
SUSTAIN_FRAC = 0.6       # a bridge pickup reads an octave low on the attack frames (6 of 21 measured); the string's
                         # expected notes already filter the result, so the detector can be more tolerant here
BEEP_S = 0.15
CHORD_TAKE_S = 2.0
CHORD_PREROLL_S = 0.05   # a chord's own onset detector needs >2 blocks (~43ms) of true silence before the attack
CHORD_MIN_SEP_S = 1.0    # a note ending abruptly mid-chord can look like a second attack; keep only real strums
_METRIC_KEYS = ("midi", "duration_s", "saturated_samples", "snr_db", "peak_db")


def record(seconds: float, device, channel: int, sr: int = SR, playrec=None) -> np.ndarray:
    """Beep on outputs 1-2 at the start, record input `channel` (1-based) of `device`."""
    if playrec is None:
        import sounddevice as sd

        def playrec(*a, **k):
            r = sd.playrec(*a, **k)
            sd.wait()
            return r

    out = np.zeros((int(seconds * sr), 2), dtype=np.float32)
    t = np.arange(int(BEEP_S * sr)) / sr
    out[: len(t), :] = (0.2 * np.sin(2 * np.pi * 1000 * t))[:, None].astype(np.float32)
    rec = playrec(out, samplerate=sr, device=device, input_mapping=[channel],
                  output_mapping=[1, 2], dtype="float32")
    return np.asarray(rec)[:, 0]


def note_spans(signal: np.ndarray, sr: int, expected: list[int]) -> dict[int, tuple[int, int]]:
    """Attack and end sample of each expected note; the longest one when a note was played twice."""
    found = [n for n in detect_notes(signal, sr, sustain_frac=SUSTAIN_FRAC) if n["midi"] in expected]
    spans: dict[int, tuple[int, int]] = {}
    for i, n in enumerate(found):
        nxt = found[i + 1]["start_s"] if i + 1 < len(found) else n["start_s"] + 2.0
        span = (int(round(n["start_s"] * sr)), min(len(signal), int(round(nxt * sr))))
        if n["midi"] not in spans or span[1] - span[0] > spans[n["midi"]][1] - spans[n["midi"]][0]:
            spans[n["midi"]] = span
    return spans


def _piece(signal: np.ndarray, sr: int, span: tuple[int, int], preroll_s: float) -> np.ndarray:
    return signal[max(0, span[0] - int(round(preroll_s * sr))):span[1]]


def cut_notes(signal: np.ndarray, sr: int, expected: list[int]) -> dict[int, np.ndarray]:
    return {m: _piece(signal, sr, sp, PREROLL_S) for m, sp in note_spans(signal, sr, expected).items()}


def measure_and_judge(piece: np.ndarray, sr: int, midi: int) -> dict:
    metrics = take_metrics(piece, sr)
    return {**{k: metrics[k] for k in _METRIC_KEYS}, **judge_take(metrics, midi)}


def save_string(root: Path, guitar: str, position: str, string: int, signal: np.ndarray, sr: int) -> dict:
    expected = library.expected_midis(string)
    pos_dir = root / guitar / position
    pos_dir.mkdir(parents=True, exist_ok=True)
    med_path = pos_dir / "medicao.yaml"
    med = library.read_yaml(med_path) if med_path.exists() else {}
    report: dict = {"accepted": [], "rejected": {}, "missing": []}
    takes = pos_dir / "_takes"   # the raw take: a missing note cannot be diagnosed without it
    takes.mkdir(exist_ok=True)
    sf.write(takes / f"c{string}.wav", signal, sr, subtype="FLOAT")
    spans = note_spans(signal, sr, expected)
    cuts = {m: _piece(signal, sr, sp, PREROLL_S) for m, sp in spans.items()}
    for midi in expected:
        if midi not in cuts:
            report["missing"].append(midi)
            continue
        entry = measure_and_judge(_piece(signal, sr, spans[midi], METRIC_PREROLL_S), sr, midi)
        name = library.note_filename(string, midi)
        med[name[:-4]] = entry
        if entry["accepted"]:
            sf.write(pos_dir / name, cuts[midi], sr, subtype="FLOAT")
            report["accepted"].append(midi)
        else:
            report["rejected"][midi] = entry["reasons"]
    library.write_yaml(med_path, med)
    return report


def save_chord(root: Path, guitar: str, position: str, voicing: list[tuple[int, int]],
               signal: np.ndarray, sr: int, takes: int = 3) -> dict:
    """Up to `takes` strums; a take is kept only when the chord detector hears exactly its notes."""
    from tone_analyzer.chords import detect_chords
    from tone_analyzer.notes import note_onsets
    want = reduce_octaves([m for _, m in voicing])
    out_dir = root / guitar / position / library.CHORDS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    rep: dict = {"accepted": [], "rejected": {}}
    for i, a in enumerate(note_onsets(signal, sr, min_sep_s=CHORD_MIN_SEP_S)[:takes], 1):
        start = max(0, a - int(CHORD_PREROLL_S * sr))
        piece = signal[start:start + int(CHORD_TAKE_S * sr)]
        heard = detect_chords(piece, sr)
        got = tuple(heard[0]["midis"]) if heard else ()
        if got != want:
            rep["rejected"][i] = f"heard {list(got)}, expected {list(want)}"
            continue
        sf.write(out_dir / library.chord_filename(voicing, i), piece, sr, subtype="FLOAT")
        rep["accepted"].append(i)
    return rep
