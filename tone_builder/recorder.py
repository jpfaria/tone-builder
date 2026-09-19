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


def cut_notes(signal: np.ndarray, sr: int, expected: list[int]) -> dict[int, np.ndarray]:
    found = [n for n in detect_notes(signal, sr) if n["midi"] in expected]
    cuts: dict[int, np.ndarray] = {}
    for i, n in enumerate(found):
        start = max(0, int(round((n["start_s"] - PREROLL_S) * sr)))
        nxt = found[i + 1]["start_s"] if i + 1 < len(found) else n["start_s"] + 2.0
        end = min(len(signal), int(round(nxt * sr)))
        piece = signal[start:end]
        if n["midi"] not in cuts or len(piece) > len(cuts[n["midi"]]):
            cuts[n["midi"]] = piece
    return cuts


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
    cuts = cut_notes(signal, sr, expected)
    for midi in expected:
        if midi not in cuts:
            report["missing"].append(midi)
            continue
        entry = measure_and_judge(cuts[midi], sr, midi)
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
