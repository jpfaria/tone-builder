"""Record one string of a guitar, cut the notes, test each one, save only the accepted ones."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile as sf
from tone_analyzer import notes as ta_notes
from tone_analyzer.take import take_metrics

from tone_builder import library
from tone_builder.acceptance import judge_take
from tone_builder.chords import reduce_octaves

SR = 48000
PREROLL_S = 0.02
METRIC_PREROLL_S = 0.15  # the noise floor is read before the attack; 20 ms of pre-roll leaves nothing to read
SUSTAIN_FRAC = 0.75
NOTE_S = 0.6
CONF_MIN = 0.8
MIN_ESTIMATES = 6
# Plain autocorrelation slips to a subharmonic of the note on a bridge pickup: string 1 of the PRS read f/2 on
# 17 of 21 frames of fret 11, and f/3 then f/2 on fret 15. The recorder knows which notes the string holds, so a
# frame reading 12, 19 or 24 semitones under an expected note counts for that note.
SUBHARMONICS = (12, 19, 24)
BEEP_S = 0.5   # 0.15 s went unnoticed on a real session (19/09/2026)
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


def _name(estimates: np.ndarray, expected: list[int]) -> int | None:
    """The expected note most frames agree on, a subharmonic read counting for it; direct reads break a tie."""
    best, best_score = None, (0.0, 0.0)
    for m in expected:
        direct = np.abs(estimates - m) <= 0.5
        folded = direct | np.any([np.abs(estimates - (m - s)) <= 0.5 for s in SUBHARMONICS], axis=0)
        score = (float(folded.mean()), float(direct.mean()))
        if direct.any() and score > best_score:
            best, best_score = m, score
    return best if best_score[0] >= SUSTAIN_FRAC else None


def note_spans(signal: np.ndarray, sr: int, expected: list[int]) -> dict[int, tuple[int, int]]:
    """Attack and end sample of each expected note; the longest one when a note was played twice."""
    x = np.asarray(signal, dtype=np.float64)
    frame, hop = int(round(ta_notes.FRAME_S * sr)), int(round(ta_notes.HOP_S * sr))
    span_n = int(round(NOTE_S * sr))
    found: list[tuple[int, int]] = []
    for a in ta_notes.note_onsets(x, sr):
        if a + span_n >= len(x):
            continue
        est = [ta_notes.hz_to_midi(f0) for f0, conf in
               (ta_notes.pitch_autocorr(x[a + k:a + k + frame], sr) for k in range(0, span_n - frame, hop))
               if conf > CONF_MIN]
        midi = _name(np.array(est), expected) if len(est) >= MIN_ESTIMATES else None
        if midi is not None:
            found.append((a, midi))
    spans: dict[int, tuple[int, int]] = {}
    for i, (a, midi) in enumerate(found):
        end = min(len(x), found[i + 1][0] if i + 1 < len(found) else a + int(2.0 * sr))
        if midi not in spans or end - a > spans[midi][1] - spans[midi][0]:
            spans[midi] = (a, end)
    return spans


def _piece(signal: np.ndarray, sr: int, span: tuple[int, int], preroll_s: float) -> np.ndarray:
    return signal[max(0, span[0] - int(round(preroll_s * sr))):span[1]]


def cut_notes(signal: np.ndarray, sr: int, expected: list[int]) -> dict[int, np.ndarray]:
    return {m: _piece(signal, sr, sp, PREROLL_S) for m, sp in note_spans(signal, sr, expected).items()}


def measure_and_judge(piece: np.ndarray, sr: int, midi: int, recorded_snr_db: float | None = None) -> dict:
    """`recorded_snr_db`: the noise read on the take. A saved note keeps 20 ms of pre-roll: too little to read it
    again (none, or the tail of the note before it), so the figure of the take wins whenever there is one."""
    metrics = take_metrics(piece, sr)
    if recorded_snr_db is not None:
        metrics = {**metrics, "snr_db": recorded_snr_db}
    if metrics["midi"] is not None and midi - metrics["midi"] in SUBHARMONICS:
        metrics = {**metrics, "midi": midi}   # the single middle frame slipped to a subharmonic; note_spans named it
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
