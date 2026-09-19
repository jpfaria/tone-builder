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
RING_S = 2.0   # a note ends at the next attack, or after this much of it
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


def note_spans_all(signal: np.ndarray, sr: int, expected: list[int]) -> list[tuple[int, int, int]]:
    """(midi, attack, end) of every attack that names an expected note, in order."""
    return _spans_of(_named_attacks(signal, sr, expected)[0], len(signal), sr)


def _spans_of(found: list[tuple[int, int]], x_len: int, sr: int) -> list[tuple[int, int, int]]:
    return [(midi, a, min(x_len, found[i + 1][0] if i + 1 < len(found) else a + int(RING_S * sr)))
            for i, (a, midi) in enumerate(found)]


def note_spans(signal: np.ndarray, sr: int, expected: list[int]) -> dict[int, tuple[int, int]]:
    """Attack and end sample of each expected note; the longest one when a note was played twice."""
    spans: dict[int, tuple[int, int]] = {}
    for midi, a, end in note_spans_all(signal, sr, expected):
        if midi not in spans or end - a > spans[midi][1] - spans[midi][0]:
            spans[midi] = (a, end)
    return spans


def _named_attacks(signal: np.ndarray, sr: int, expected: list[int]) -> tuple[list[tuple[int, int]], list[int]]:
    """(attack, midi) of every attack that names an expected note, and the attacks too recent to be named yet."""
    x = np.asarray(signal, dtype=np.float64)
    frame, hop = int(round(ta_notes.FRAME_S * sr)), int(round(ta_notes.HOP_S * sr))
    span_n = int(round(NOTE_S * sr))
    found: list[tuple[int, int]] = []
    pending: list[int] = []
    for a in ta_notes.note_onsets(x, sr):
        if a + span_n >= len(x):
            pending.append(a)
            continue
        est = [ta_notes.hz_to_midi(f0) for f0, conf in
               (ta_notes.pitch_autocorr(x[a + k:a + k + frame], sr) for k in range(0, span_n - frame, hop))
               if conf > CONF_MIN]
        midi = _name(np.array(est), expected) if len(est) >= MIN_ESTIMATES else None
        if midi is not None:
            found.append((a, midi))
    return found, pending


def _piece(signal: np.ndarray, sr: int, span: tuple[int, int], preroll_s: float) -> np.ndarray:
    return signal[max(0, span[0] - int(round(preroll_s * sr))):span[1]]


def _beep(sr: int) -> np.ndarray:
    t = np.arange(int(BEEP_S * sr)) / sr
    return np.tile((0.2 * np.sin(2 * np.pi * 1000 * t))[:, None], (1, 2)).astype(np.float32)


def live_blocks(device, channel: int, sr: int = SR, block_s: float = 0.5, max_s: float = 600.0):
    """Beep on outputs 1-2, then yield input `channel` (1-based) of `device` block by block until the reader stops."""
    import queue

    import sounddevice as sd

    sd.play(_beep(sr), samplerate=sr, device=device, mapping=[1, 2], blocking=True)
    q: queue.Queue = queue.Queue()
    # a raw stream has no channel mapping: open the inputs up to `channel` and keep the last one
    with sd.InputStream(samplerate=sr, device=device, channels=channel, dtype="float32",
                        blocksize=int(block_s * sr), callback=lambda data, *_: q.put(data[:, channel - 1].copy())):
        for _ in range(int(max_s / block_s)):
            yield q.get(timeout=5.0)


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


def _save_note(pos_dir: Path, med: dict, string: int, midi: int, signal: np.ndarray,
               span: tuple[int, int], sr: int) -> dict:
    """Judge one note of a take and, accepted, write it. Returns its measurement entry."""
    # the long pre-roll reads the noise before the attack; played over the ring of the note before, that stretch
    # holds a note instead, the take's onset lands on it and nothing can be read: the short pre-roll then decides
    entry = measure_and_judge(_piece(signal, sr, span, METRIC_PREROLL_S), sr, midi)
    if not entry["accepted"]:
        short = measure_and_judge(_piece(signal, sr, span, PREROLL_S), sr, midi)
        entry = short if short["accepted"] else entry
    name = library.note_filename(string, midi)
    if not entry["accepted"] and (med.get(name[:-4]) or {}).get("accepted") and (pos_dir / name).exists():
        return entry   # a worse take never replaces the accepted one on disk
    med[name[:-4]] = entry
    if entry["accepted"]:
        sf.write(pos_dir / name, _piece(signal, sr, span, PREROLL_S), sr, subtype="FLOAT")
    return entry


def _open_position(root: Path, guitar: str, position: str) -> tuple[Path, Path, dict]:
    pos_dir = root / guitar / position
    (pos_dir / "_takes").mkdir(parents=True, exist_ok=True)   # the raw take: a missing note cannot be diagnosed without it
    med_path = pos_dir / "medicao.yaml"
    return pos_dir, med_path, library.read_yaml(med_path) if med_path.exists() else {}


def save_string(root: Path, guitar: str, position: str, string: int, signal: np.ndarray, sr: int) -> dict:
    expected = library.expected_midis(string)
    pos_dir, med_path, med = _open_position(root, guitar, position)
    report: dict = {"accepted": [], "rejected": {}, "missing": []}
    sf.write(pos_dir / "_takes" / f"c{string}.wav", signal, sr, subtype="FLOAT")
    spans = note_spans(signal, sr, expected)
    for midi in expected:
        if midi not in spans:
            report["missing"].append(midi)
            continue
        entry = _save_note(pos_dir, med, string, midi, signal, spans[midi], sr)
        if entry["accepted"]:
            report["accepted"].append(midi)
        else:
            report["rejected"][midi] = entry["reasons"]
    library.write_yaml(med_path, med)
    return report


IDLE_S = 12.0        # silence after the last attack that ends the session with notes still missing
FIRST_NOTE_S = 30.0  # time to get to the guitar before the first note
DEAD_S, DEAD_PEAK = 5.0, 10 ** (-80 / 20)   # a plugged guitar idles near -64 dBFS; an empty input reads -100
KEEP_S = 0.3         # audio kept before the next window: the attack detector needs the rise, the noise read its silence


def listen_string(root: Path, guitar: str, position: str, string: int, blocks, sr: int, say=print) -> dict:
    """Listen to one string until its 16 notes are in: each note is named, judged and announced as it closes.

    Any order, any pace; a note played again replaces the one before, so a wrong one is simply played again.
    Ends by itself when nothing is missing, or after IDLE_S without an attack. `blocks` yields mono audio.
    """
    expected = library.expected_midis(string)
    pos_dir, med_path, med = _open_position(root, guitar, position)
    state: dict[int, list[str] | None] = {}      # midi -> None when accepted, else the reasons of its last try
    have = [m for m in expected if (med.get(library.note_filename(string, m)[:-4]) or {}).get("accepted")
            and (pos_dir / library.note_filename(string, m)).exists()]
    if len(have) < len(expected):                # a string half done: only what it lacks is waited for
        state.update({m: None for m in have})
        if have:
            say(f"already in: {len(have)}; waiting for {[m for m in expected if m not in have]}")
    heard_any = False
    buf = np.zeros(0, dtype=np.float32)
    done = 0                                     # samples of buf already settled
    last_attack = 0
    dead = False
    for block in blocks:
        buf = np.concatenate([buf, np.asarray(block, dtype=np.float32)])
        window = buf[done:]
        settled = 0
        found, pending = _named_attacks(window, sr, expected)
        for midi, a, end in _spans_of(found, len(window), sr):
            last_attack = max(last_attack, done + a)
            heard_any = True
            if end == len(window) and len(window) - a < int(RING_S * sr):
                break                            # still ringing: wait for more audio
            if any(a < p < end for p in pending):
                break                            # an attack too recent to be named may be where this note ends
            entry = _save_note(pos_dir, med, string, midi, window, (a, end), sr)
            if not entry["accepted"] and midi in state and state[midi] is None:
                settled = end
                continue                         # already in: a later noise named after it changes nothing
            state[midi] = None if entry["accepted"] else entry["reasons"]
            name = library.note_filename(string, midi)[:-4]
            to_go = sum(1 for m in expected if state.get(m, []) is not None)
            say(f"ok  {name}   ({to_go} to go)" if entry["accepted"]
                else f"NO  {name}: {', '.join(entry['reasons'])} - play it again")
            settled = end
        if settled:
            library.write_yaml(med_path, med)
            done += max(0, settled - int(KEEP_S * sr))
        if all(state.get(m, []) is None for m in expected):
            break
        if len(buf) >= int(DEAD_S * sr) and float(np.abs(buf).max()) < DEAD_PEAK:
            say(f"no signal on this input (peak {20 * np.log10(float(np.abs(buf).max()) + 1e-12):.0f} dBFS): "
                "is the guitar on this channel?")
            dead = True
            break
        if (len(buf) - last_attack) / sr > (IDLE_S if heard_any else FIRST_NOTE_S):
            break
    if not dead:
        sf.write(pos_dir / "_takes" / f"c{string}.wav", buf, sr, subtype="FLOAT")
    library.write_yaml(med_path, med)
    return {"accepted": [m for m in expected if m in state and state[m] is None],
            "rejected": {m: state[m] for m in expected if state.get(m)},
            "missing": [m for m in expected if m not in state], **({"no_signal": True} if dead else {})}


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
