# Etapa 1 — tone-analyzer: notas e harmônicos de UM áudio

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** o `tone-analyzer` passa a detectar as notas de um áudio e medir o nível de cada harmônico
H1..H16 de uma nota, e entrega isso nas três saídas (métrica JSON, documentação PDF, espectro PNG);
`compare` e `eq-match` ficam marcados como obsoletos.

**Architecture:** um módulo novo e puro, `tone_analyzer/notes.py`, com as funções já validadas em
`music-setup/tools/openrig/timbre_medida.py` (autocorrelação pura, ataques por envelope, harmônicos
com vizinhança), generalizadas para qualquer taxa de amostragem. O `analyze` consome esse módulo
para acrescentar `notes` ao fingerprint, uma página ao PDF e `spec_notes.png`. Um subcomando novo,
`harmonics`, mede harmônicos num instante e nota dados — é o que o `tone-builder` usa para ler o
disco. Nada aqui compara dois áudios.

**Tech Stack:** Python ≥ 3.11, numpy 2.1.3, scipy 1.14.1, matplotlib 3.9.2, pytest 8.3.3.

**Spec:** `tone-builder/docs/superpowers/specs/2026-09-16-tone-builder-design.md` (seções "tone-analyzer",
"Números que justificam as decisões", "Testes").

**Repo:** `~/Projetos/github.com/jpfaria/tone-analyzer` · linha de base: `python3 -m pytest -q` → 114 passed.

## Global Constraints

- O `tone-analyzer` analisa **um** áudio. Nenhuma função nova recebe dois áudios.
- Pitch = **autocorrelação pura**, sem pós-processamento de oitava (validado 92/96 e 21/21; as
  variantes com correção de oitava deram 84–93/96 e 17/21).
- Janela da nota: **0,6 s** a partir do ataque.
- Harmônico: pico em `f·(1 ± 0,012)`; vizinhança = mediana em `f·[0,90; 0,96] ∪ f·[1,04; 1,10]`.
- Sem efeito colateral fora de `--out-dir`; sem rede (o teste `test_no_network.py` continua valendo).
- Tudo que é persistido (JSON, comentários, docstrings) em inglês; a conversa com o usuário em português.
- Saída determinística: floats passam por `_common.round_for_json`.

---

## File Structure

| arquivo | responsabilidade |
|---|---|
| `tone_analyzer/notes.py` (novo) | pitch, ataques, detecção de notas, harmônicos — funções puras |
| `tone_analyzer/harmonics.py` (novo) | subcomando `harmonics`: harmônicos em instantes/notas dados → JSON |
| `tone_analyzer/analyze.py` (muda) | `notes` no fingerprint (schema 4), página de notas no PDF, `spec_notes.png` |
| `tone_analyzer/cli.py` (muda) | registra `harmonics`; marca `compare`/`eq-match` como obsoletos no uso |
| `tone_analyzer/compare.py`, `eq_match.py` (mudam) | aviso de obsolescência no stderr |
| `tests/_synth.py` (novo) | gera notas sintéticas com harmônicos de amplitude conhecida |
| `tests/test_notes.py` (novo) | testes do `notes.py` |
| `tests/test_harmonics_cli.py` (novo) | testes do subcomando |
| `tests/test_analyze.py`, `tests/test_cli.py` (mudam) | schema 4, saídas novas, aviso de obsolescência |
| `skills/tone-analyzer/SKILL.md`, `README.md`, `.claude-plugin/plugin.json`, `pyproject.toml` | documentação e versão 0.2.0 |

---

### Task 1: gerador de nota sintética para os testes

**Files:**
- Create: `tests/_synth.py`
- Test: `tests/test_notes.py`

**Interfaces:**
- Produces: `harmonic_note(midi: int, sr: int, dur_s: float, harm_db: list[float], attack_s: float = 0.005, decay_s: float = 1.5) -> np.ndarray` (mono float32);
  `note_sequence(midis: list[int], sr: int, note_s: float, gap_s: float, harm_db: list[float]) -> tuple[np.ndarray, list[float]]` (sinal, instantes de início em segundos);
  `midi_to_hz(midi: int) -> float`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_notes.py
"""Tests for tone_analyzer.notes — one audio in, notes and harmonics out."""

from __future__ import annotations

import numpy as np
import pytest

from tests._synth import harmonic_note, midi_to_hz, note_sequence


def test_synth_note_has_requested_fundamental():
    sr = 22050
    x = harmonic_note(69, sr, 1.0, [0.0, -6.0, -12.0])
    spec = np.abs(np.fft.rfft(x * np.hanning(len(x))))
    freqs = np.fft.rfftfreq(len(x), 1 / sr)
    assert abs(freqs[np.argmax(spec)] - 440.0) < 2.0
    assert x.dtype == np.float32
    assert np.abs(x).max() <= 1.0


def test_synth_sequence_reports_starts():
    sr = 22050
    x, starts = note_sequence([45, 57, 69], sr, note_s=1.0, gap_s=0.5, harm_db=[0.0, -6.0])
    assert starts == pytest.approx([0.5, 2.0, 3.5])
    assert len(x) == int(round(5.0 * sr))
    assert abs(midi_to_hz(69) - 440.0) < 1e-9
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/Projetos/github.com/jpfaria/tone-analyzer && python3 -m pytest tests/test_notes.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'tests._synth'`

- [ ] **Step 3: Write minimal implementation**

```python
# tests/_synth.py
"""Synthetic guitar-like notes with known harmonic amplitudes, for tests only.

Recorded music cannot ship in this public repo, so every audio fixture that
needs a known truth is synthesized here.
"""

from __future__ import annotations

import numpy as np


def midi_to_hz(midi: int) -> float:
    return 440.0 * 2.0 ** ((midi - 69) / 12.0)


def harmonic_note(
    midi: int,
    sr: int,
    dur_s: float,
    harm_db: list[float],
    attack_s: float = 0.005,
    decay_s: float = 1.5,
) -> np.ndarray:
    """Sum of harmonics k=1..len(harm_db) at the given dB (H1 first), plucked envelope."""
    n = int(round(dur_s * sr))
    t = np.arange(n) / sr
    f0 = midi_to_hz(midi)
    x = np.zeros(n)
    for k, db in enumerate(harm_db, start=1):
        if k * f0 >= sr / 2:
            break
        x += 10.0 ** (db / 20.0) * np.sin(2 * np.pi * k * f0 * t)
    env = np.minimum(t / attack_s, 1.0) * np.exp(-t / decay_s)
    x *= env
    peak = np.abs(x).max()
    if peak > 0:
        x *= 0.5 / peak
    return x.astype(np.float32)


def note_sequence(
    midis: list[int],
    sr: int,
    note_s: float,
    gap_s: float,
    harm_db: list[float],
) -> tuple[np.ndarray, list[float]]:
    """Notes separated by silence. Starts after one leading gap."""
    parts = [np.zeros(int(round(gap_s * sr)), dtype=np.float32)]
    starts = []
    t = gap_s
    for m in midis:
        starts.append(round(t, 6))
        parts.append(harmonic_note(m, sr, note_s, harm_db))
        parts.append(np.zeros(int(round(gap_s * sr)), dtype=np.float32))
        t += note_s + gap_s
    return np.concatenate(parts), starts
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_notes.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add tests/_synth.py tests/test_notes.py
git commit -m "test: synthetic notes with known harmonic amplitudes"
```

---

### Task 2: pitch por autocorrelação pura

**Files:**
- Create: `tone_analyzer/notes.py`
- Test: `tests/test_notes.py`

**Interfaces:**
- Consumes: `tests._synth.harmonic_note`, `midi_to_hz`
- Produces: `pitch_autocorr(frame: np.ndarray, sr: int, fmin: float = 70.0, fmax: float = 1400.0) -> tuple[float, float]` → `(f0_hz, confidence)`;
  `hz_to_midi(f_hz: float) -> float`; `midi_name(midi: int) -> str` (ex.: `"A4"`).

- [ ] **Step 1: Write the failing test**

Acrescentar a `tests/test_notes.py`:

```python
from tone_analyzer import notes


@pytest.mark.parametrize("sr", [22050, 44100, 48000])
@pytest.mark.parametrize("midi", [40, 45, 52, 57, 64, 69, 76])
def test_pitch_autocorr_finds_midi(sr, midi):
    x = harmonic_note(midi, sr, 1.0, [0.0, -4.0, -8.0, -12.0, -16.0, -20.0])
    frame = x[int(0.1 * sr):int(0.1 * sr) + int(round(0.171 * sr))]
    f0, conf = notes.pitch_autocorr(frame, sr)
    assert round(notes.hz_to_midi(f0)) == midi
    assert conf > 0.8


def test_midi_name():
    assert notes.midi_name(69) == "A4"
    assert notes.midi_name(60) == "C4"
    assert notes.midi_name(40) == "E2"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_notes.py -v`
Expected: FAIL with `ImportError: cannot import name 'notes'`

- [ ] **Step 3: Write minimal implementation**

```python
# tone_analyzer/notes.py
"""Notes and harmonics of ONE guitar audio.

Pure functions, no I/O. Ported from the method validated against known truth
(see tone-builder spec): plain autocorrelation pitch with no octave
"correction", notes measured over 0.6 s from the attack, harmonic level read at
k*f0 with its neighbourhood median.
"""

from __future__ import annotations

import numpy as np

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# Frame and hop were 8192 / 1024 samples at 48 kHz when the method was validated.
FRAME_S = 8192 / 48000
HOP_S = 1024 / 48000


def hz_to_midi(f_hz: float) -> float:
    return 69.0 + 12.0 * np.log2(f_hz / 440.0)


def midi_name(midi: int) -> str:
    return f"{NOTE_NAMES[midi % 12]}{midi // 12 - 1}"


def pitch_autocorr(
    frame: np.ndarray, sr: int, fmin: float = 70.0, fmax: float = 1400.0
) -> tuple[float, float]:
    """Plain autocorrelation pitch. Returns (f0_hz, normalized peak in 0..1).

    No octave post-processing: every variant tried lost accuracy (spec).
    """
    n = len(frame)
    w = frame.astype(np.float64) * np.hanning(n)
    ac = np.fft.irfft(np.abs(np.fft.rfft(w, 2 * n)) ** 2)[:n]
    ac = ac / (ac[0] + 1e-12)
    lo = max(1, int(sr / fmax))
    hi = min(n - 1, int(sr / fmin))
    k = lo + int(np.argmax(ac[lo:hi]))
    return float(sr / k), float(ac[k])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_notes.py -v`
Expected: all passed (2 + 21 + 1)

- [ ] **Step 5: Commit**

```bash
git add tone_analyzer/notes.py tests/test_notes.py
git commit -m "feat(notes): plain autocorrelation pitch, sample-rate agnostic"
```

---

### Task 3: ataques e detecção de notas

**Files:**
- Modify: `tone_analyzer/notes.py`
- Test: `tests/test_notes.py`

**Interfaces:**
- Consumes: `pitch_autocorr`, `hz_to_midi`, `midi_name`, `FRAME_S`, `HOP_S`
- Produces: `note_onsets(signal: np.ndarray, sr: int, floor_rel_db: float = 30.0, min_sep_s: float = 0.5) -> list[int]` (amostras);
  `detect_notes(signal: np.ndarray, sr: int, dur_s: float = 0.6, conf_min: float = 0.8, sustain_frac: float = 0.75, min_estimates: int = 6) -> list[dict]`
  onde cada dict = `{"start_s": float, "midi": int, "name": str, "f0_hz": float}`.

- [ ] **Step 1: Write the failing test**

```python
def test_note_onsets_find_each_attack():
    sr = 22050
    x, starts = note_sequence([45, 57, 69], sr, note_s=1.0, gap_s=0.5, harm_db=[0.0, -6.0, -12.0])
    found = [i / sr for i in notes.note_onsets(x, sr)]
    assert len(found) == 3
    for f, s in zip(found, starts):
        assert abs(f - s) < 0.06


def test_detect_notes_names_each_note():
    sr = 44100
    x, starts = note_sequence([45, 57, 69], sr, note_s=1.0, gap_s=0.5,
                              harm_db=[0.0, -4.0, -8.0, -12.0, -16.0])
    got = notes.detect_notes(x, sr)
    assert [n["midi"] for n in got] == [45, 57, 69]
    assert [n["name"] for n in got] == ["A2", "A3", "A4"]
    assert got[2]["f0_hz"] == pytest.approx(440.0, rel=0.03)


def test_detect_notes_ignores_silence():
    sr = 22050
    assert notes.detect_notes(np.zeros(3 * sr, dtype=np.float32), sr) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_notes.py -v`
Expected: FAIL with `AttributeError: module 'tone_analyzer.notes' has no attribute 'note_onsets'`

- [ ] **Step 3: Write minimal implementation**

Acrescentar a `tone_analyzer/notes.py`:

```python
def note_onsets(
    signal: np.ndarray, sr: int, floor_rel_db: float = 30.0, min_sep_s: float = 0.5
) -> list[int]:
    """Attack sample indices: envelope rises >1.5x after a lower block."""
    x = np.asarray(signal, dtype=np.float64)
    block = max(1, int(round(1024 * sr / 48000)))
    if len(x) < 5 * block:
        return []
    env = np.array([np.abs(x[i:i + block]).max() for i in range(0, len(x) - block, block)])
    peak = env.max()
    if peak <= 0:
        return []
    lim = peak * 10.0 ** (-floor_rel_db / 20.0)
    out: list[int] = []
    last = -1e9
    for k in range(2, len(env) - 2):
        t = k * block / sr
        if (env[k] > lim and env[k] > env[k - 1] * 1.5
                and env[k] >= env[k + 1] * 0.8 and t - last > min_sep_s):
            out.append(k * block)
            last = t
    return out


def detect_notes(
    signal: np.ndarray,
    sr: int,
    dur_s: float = 0.6,
    conf_min: float = 0.8,
    sustain_frac: float = 0.75,
    min_estimates: int = 6,
) -> list[dict]:
    """Notes that hold one pitch over dur_s from their attack."""
    x = np.asarray(signal, dtype=np.float64)
    frame = int(round(FRAME_S * sr))
    hop = int(round(HOP_S * sr))
    span = int(round(dur_s * sr))
    found: list[dict] = []
    for a in note_onsets(x, sr):
        if a + span >= len(x):
            continue
        est = []
        f0s = []
        for k in range(0, span - frame, hop):
            f0, conf = pitch_autocorr(x[a + k:a + k + frame], sr)
            if conf > conf_min:
                est.append(int(round(hz_to_midi(f0))))
                f0s.append(f0)
        if len(est) < min_estimates:
            continue
        midi = int(np.bincount(est).argmax())
        hits = np.array(est) == midi
        if hits.mean() < sustain_frac:
            continue
        found.append({
            "start_s": a / sr,
            "midi": midi,
            "name": midi_name(midi),
            "f0_hz": float(np.median(np.array(f0s)[hits])),
        })
    return found
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_notes.py -v`
Expected: all passed

- [ ] **Step 5: Commit**

```bash
git add tone_analyzer/notes.py tests/test_notes.py
git commit -m "feat(notes): attack detection and sustained-note detection"
```

---

### Task 4: nível e destaque de cada harmônico

**Files:**
- Modify: `tone_analyzer/notes.py`
- Test: `tests/test_notes.py`

**Interfaces:**
- Consumes: `midi_to_hz` (testes)
- Produces: `harmonic_levels(signal: np.ndarray, sr: int, start_s: float, f0_hz: float, dur_s: float = 0.6, n_harm: int = 16) -> dict | None`
  → `{"level_db": list[float|None], "neighbour_db": list[float|None], "prominence_db": list[float|None], "relative_db": list[float|None]}`,
  todas com `n_harm` itens (`None` onde o harmônico passa de 0,9·Nyquist); `None` se sobrar menos de 0,3 s de sinal.

- [ ] **Step 1: Write the failing test**

```python
def test_harmonic_levels_recover_known_amplitudes():
    sr = 48000
    harm = [0.0, -6.0, -12.0, -18.0, -24.0, -30.0]
    x = harmonic_note(57, sr, 1.0, harm, decay_s=50.0)
    h = notes.harmonic_levels(x, sr, 0.05, midi_to_hz(57))
    rel = h["relative_db"]
    for k, db in enumerate(harm):
        assert rel[k] == pytest.approx(db, abs=0.5)
    assert all(p >= 10.0 for p in h["prominence_db"][:len(harm)])
    assert len(h["level_db"]) == 16


def test_harmonic_absent_has_low_prominence():
    sr = 48000
    x = harmonic_note(57, sr, 1.0, [0.0, -6.0, -200.0, -12.0], decay_s=50.0)
    rng = np.random.default_rng(42)
    x = x + (rng.standard_normal(len(x)) * 1e-4).astype(np.float32)
    h = notes.harmonic_levels(x, sr, 0.05, midi_to_hz(57))
    assert h["prominence_db"][2] < 10.0
    assert h["prominence_db"][1] >= 10.0


def test_harmonic_levels_marks_above_nyquist_and_short_signal():
    sr = 22050
    x = harmonic_note(88, sr, 1.0, [0.0, -6.0])        # E6, 1319 Hz
    h = notes.harmonic_levels(x, sr, 0.05, midi_to_hz(88))
    assert h["level_db"][15] is None                  # 16*1319 Hz > 0.9 * 11025
    assert notes.harmonic_levels(x[: int(0.2 * sr)], sr, 0.0, midi_to_hz(88)) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_notes.py -v`
Expected: FAIL with `AttributeError: ... no attribute 'harmonic_levels'`

- [ ] **Step 3: Write minimal implementation**

Acrescentar a `tone_analyzer/notes.py`:

```python
PEAK_TOL = 0.012
NEIGH_LO = (0.90, 0.96)
NEIGH_HI = (1.04, 1.10)


def harmonic_levels(
    signal: np.ndarray,
    sr: int,
    start_s: float,
    f0_hz: float,
    dur_s: float = 0.6,
    n_harm: int = 16,
) -> dict | None:
    """Level at k*f0 and the neighbourhood median, k = 1..n_harm, in dB."""
    x = np.asarray(signal, dtype=np.float64)
    ini = int(round(start_s * sr))
    n = min(int(round(dur_s * sr)), len(x) - ini)
    if n < int(0.3 * sr):
        return None
    seg = x[ini:ini + n] * np.hanning(n)
    power = np.abs(np.fft.rfft(seg, 4 * n)) ** 2
    freqs = np.fft.rfftfreq(4 * n, 1 / sr)
    level, neigh, prom, rel = [], [], [], []
    for k in range(1, n_harm + 1):
        f = f0_hz * k
        peak = (freqs > f * (1 - PEAK_TOL)) & (freqs < f * (1 + PEAK_TOL))
        around = (((freqs > f * NEIGH_LO[0]) & (freqs < f * NEIGH_LO[1]))
                  | ((freqs > f * NEIGH_HI[0]) & (freqs < f * NEIGH_HI[1])))
        if f > 0.9 * sr / 2 or not peak.any() or not around.any():
            level.append(None); neigh.append(None); prom.append(None)
            continue
        lv = 10.0 * np.log10(power[peak].max() + 1e-30)
        nb = 10.0 * np.log10(np.median(power[around]) + 1e-30)
        level.append(float(lv)); neigh.append(float(nb)); prom.append(float(lv - nb))
    h1 = level[0]
    rel = [None if (v is None or h1 is None) else float(v - h1) for v in level]
    return {"level_db": level, "neighbour_db": neigh, "prominence_db": prom, "relative_db": rel}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_notes.py -v`
Expected: all passed

- [ ] **Step 5: Commit**

```bash
git add tone_analyzer/notes.py tests/test_notes.py
git commit -m "feat(notes): per-harmonic level and prominence over its neighbourhood"
```

---

### Task 5: subcomando `harmonics`

**Files:**
- Create: `tone_analyzer/harmonics.py`
- Modify: `tone_analyzer/cli.py`
- Test: `tests/test_harmonics_cli.py`

**Interfaces:**
- Consumes: `notes.harmonic_levels`, `notes.detect_notes`, `notes.midi_name`, `_common.load_audio`, `_common.mono_mixdown`, `_common.round_for_json`
- Produces: CLI `tone-analyzer harmonics <in.wav> [--at SEC --midi M]... [--auto] [--out-dir DIR]`
  → escreve `harmonics.json` = `{"schema_version": 1, "source": {"path", "sample_rate_hz"}, "notes": [{"start_s", "midi", "name", "f0_hz", "level_db", "neighbour_db", "prominence_db", "relative_db"}]}` e imprime o diretório na última linha.
  `--auto` usa `detect_notes`; `--at/--midi` em pares medem num instante e nota dados (é como o tone-builder lê o disco).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_harmonics_cli.py
"""`tone-analyzer harmonics`: harmonic levels of ONE audio, at given or detected notes."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import soundfile as sf

from tests._synth import note_sequence
from tone_analyzer import cli


def _wav(tmp_path: Path) -> tuple[Path, list[float]]:
    sr = 44100
    x, starts = note_sequence([45, 57, 69], sr, 1.0, 0.5, [0.0, -6.0, -12.0, -18.0])
    p = tmp_path / "notes.wav"
    sf.write(p, x, sr, subtype="FLOAT")
    return p, starts


def test_harmonics_at_given_note(tmp_path: Path):
    wav, starts = _wav(tmp_path)
    out = tmp_path / "out"
    rc = cli.main(["harmonics", str(wav), "--at", str(starts[2]), "--midi", "69", "--out-dir", str(out)])
    assert rc == 0
    data = json.loads((out / "harmonics.json").read_text())
    assert data["schema_version"] == 1
    n = data["notes"][0]
    assert n["midi"] == 69 and n["name"] == "A4"
    assert n["relative_db"][1] == pytest.approx(-6.0, abs=0.7)
    assert len(n["level_db"]) == 16


def test_harmonics_auto_detects_notes(tmp_path: Path):
    wav, _ = _wav(tmp_path)
    out = tmp_path / "out"
    rc = cli.main(["harmonics", str(wav), "--auto", "--out-dir", str(out)])
    assert rc == 0
    data = json.loads((out / "harmonics.json").read_text())
    assert [n["midi"] for n in data["notes"]] == [45, 57, 69]


def test_harmonics_rejects_unpaired_at_midi(tmp_path: Path, capsys):
    wav, _ = _wav(tmp_path)
    rc = cli.main(["harmonics", str(wav), "--at", "1.0", "--out-dir", str(tmp_path / "o")])
    assert rc == 2
    assert "--at" in capsys.readouterr().err
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_harmonics_cli.py -v`
Expected: FAIL — `cli.main(["harmonics", ...])` returns 2 with "unknown command 'harmonics'"

- [ ] **Step 3: Write minimal implementation**

```python
# tone_analyzer/harmonics.py
#!/usr/bin/env python3
"""Harmonic levels of ONE audio at given or detected notes.

Pure function: in = one audio path, out = harmonics.json in --out-dir.
`--at SEC --midi M` pairs measure at a given attack time and note — this is how
an orchestrator reads a full mix at notes located elsewhere. `--auto` detects
the notes in this same audio.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from tone_analyzer import _common, notes
from tone_analyzer.analyze import resolve_out_dir

SCHEMA_VERSION = 1
FILENAME = "harmonics.json"


def build(signal, sr: int, audio_path: Path, targets: list[tuple[float, int]]) -> dict:
    mono = _common.mono_mixdown(signal)
    rows = []
    for start_s, midi in targets:
        f0 = 440.0 * 2.0 ** ((midi - 69) / 12.0)
        h = notes.harmonic_levels(mono, sr, start_s, f0)
        if h is None:
            continue
        rows.append({"start_s": start_s, "midi": midi, "name": notes.midi_name(midi), "f0_hz": f0, **h})
    return _common.round_for_json(
        {"schema_version": SCHEMA_VERSION,
         "source": {"path": str(audio_path), "sample_rate_hz": int(sr)},
         "notes": rows},
        ndigits=4,
    )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Harmonic levels of one audio at given or detected notes.")
    p.add_argument("input")
    p.add_argument("--at", type=float, action="append", default=[], help="attack time in seconds")
    p.add_argument("--midi", type=int, action="append", default=[], help="MIDI note for the matching --at")
    p.add_argument("--auto", action="store_true", help="detect the notes in this audio")
    p.add_argument("--out-dir", default=None)
    a = p.parse_args(argv)
    if len(a.at) != len(a.midi) or (not a.auto and not a.at):
        print("harmonics: pass --auto, or --at and --midi in pairs", file=sys.stderr)
        return 2
    audio_path = Path(a.input).expanduser().resolve()
    signal, sr = _common.load_audio(audio_path)
    targets = list(zip(a.at, a.midi))
    if a.auto:
        targets += [(n["start_s"], n["midi"]) for n in notes.detect_notes(_common.mono_mixdown(signal), sr)]
    out_dir = resolve_out_dir(a.out_dir)
    (out_dir / FILENAME).write_text(json.dumps(build(signal, sr, audio_path, targets), indent=2, sort_keys=True))
    print(str(out_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

Em `tone_analyzer/cli.py`, importar e registrar:

```python
from tone_analyzer import analyze, compare, eq_match, harmonics, make_correction_ir

_COMMANDS = {
    "analyze": analyze.main,
    "harmonics": harmonics.main,
    "compare": compare.main,
    "eq-match": eq_match.main,
    "correction-ir": make_correction_ir.main,
}
```

e na `USAGE`, logo após a linha do `analyze`:

```
  harmonics      <in.wav> (--auto | --at SEC --midi M ...) [--out-dir DIR]  harmonics.json
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_harmonics_cli.py tests/test_cli.py -v`
Expected: all passed

- [ ] **Step 5: Commit**

```bash
git add tone_analyzer/harmonics.py tone_analyzer/cli.py tests/test_harmonics_cli.py
git commit -m "feat: harmonics subcommand — harmonic levels at given or detected notes"
```

---

### Task 6: notas nas três saídas do `analyze` (métrica, documentação, espectro)

**Files:**
- Modify: `tone_analyzer/analyze.py` (`SCHEMA_VERSION`, `build_fingerprint`, `main`, PDF)
- Modify: `tests/test_analyze.py`
- Test: `tests/test_analyze.py`

**Interfaces:**
- Consumes: `notes.detect_notes`, `notes.harmonic_levels`, `_common.mono_mixdown`
- Produces: `fingerprint["schema_version"] == 4`; `fingerprint["notes"]` = lista como em `harmonics.json`;
  `render_spec_notes_png(signal, sr, notes_list, audio_path, out_dir) -> Path` (`spec_notes.png`);
  página "Notes" no `analysis.pdf`.

- [ ] **Step 1: Write the failing test**

Em `tests/test_analyze.py`, trocar `assert fp["schema_version"] == 3` por `== 4` e acrescentar:

```python
from tests._synth import note_sequence


def test_analyze_reports_notes_in_all_three_outputs(tmp_path: Path) -> None:
    sr = 44100
    x, _ = note_sequence([45, 57, 69], sr, 1.0, 0.5, [0.0, -6.0, -12.0, -18.0])
    wav = tmp_path / "seq.wav"
    sf.write(wav, x, sr, subtype="FLOAT")
    out = tmp_path / "out"
    assert analyze.main([str(wav), "--out-dir", str(out)]) == 0

    fp = json.loads((out / "fingerprint.json").read_text())
    assert [n["midi"] for n in fp["notes"]] == [45, 57, 69]
    assert fp["notes"][0]["relative_db"][1] == pytest.approx(-6.0, abs=0.7)

    assert (out / "spec_notes.png").stat().st_size > 1000

    # pypdf is not a dependency and matplotlib embeds text as glyphs, so the
    # notes page is checked by page count: cover + global + one per section + notes
    import re
    pages = len(re.findall(rb"/Type\s*/Page\b", (out / "analysis.pdf").read_bytes()))
    assert pages == 2 + len(fp["sections"]) + 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_analyze.py -v`
Expected: FAIL — `schema_version` é 3 e `fp["notes"]` não existe

- [ ] **Step 3: Write minimal implementation**

Em `tone_analyzer/analyze.py`:

```python
from tone_analyzer import _common, notes  # troca o import existente de _common

SCHEMA_VERSION = 4
```

Em `build_fingerprint`, antes do `return`, acrescentar ao dicionário:

```python
    mono = _common.mono_mixdown(signal)
    note_rows = []
    for n in notes.detect_notes(mono, sr):
        h = notes.harmonic_levels(mono, sr, n["start_s"], n["f0_hz"])
        if h is not None:
            note_rows.append({**n, **h})
    fingerprint["notes"] = note_rows
```

Nova função de espectro, ao lado de `render_spec_global_png`:

```python
def render_spec_notes_png(signal, sr, notes_list, audio_path: Path, out_dir: Path) -> Path:
    """Global spectrogram with each detected note's attack and name marked."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    mono = _common.mono_mixdown(signal)
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.specgram(mono, NFFT=2048, Fs=sr, noverlap=1536, cmap="magma")
    ax.set_ylim(0, min(8000, sr / 2))
    for n in notes_list:
        ax.axvline(n["start_s"], color="cyan", lw=0.8)
        ax.text(n["start_s"], min(7600, sr / 2 * 0.95), n["name"], color="cyan", fontsize=8)
    ax.set_title(f"Notes — {audio_path.name}")
    ax.set_xlabel("time (s)")
    ax.set_ylabel("Hz")
    path = out_dir / "spec_notes.png"
    fig.tight_layout()
    fig.savefig(path, dpi=100)
    plt.close(fig)
    return path
```

Página no PDF, nova função e chamada em `build_pdf_report` depois das seções:

```python
def _render_pdf_notes_page(pdf, fingerprint: dict[str, Any]) -> None:
    import matplotlib.pyplot as plt

    fig = plt.figure(figsize=PDF_PAGE_FIGSIZE)
    fig.suptitle("Notes", fontsize=14)
    rows = fingerprint.get("notes", [])
    if not rows:
        fig.text(0.05, 0.85, "No sustained notes detected.", fontsize=10)
    for i, n in enumerate(rows[:12]):
        ax = fig.add_subplot(4, 3, i + 1)
        rel = [v if v is not None else float("nan") for v in n["relative_db"]]
        ax.bar(range(1, len(rel) + 1), rel, color="#3a6ea5")
        ax.set_title(f'{n["name"]} @ {n["start_s"]:.2f}s', fontsize=8)
        ax.set_ylim(-60, 10)
        ax.tick_params(labelsize=6)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    pdf.savefig(fig, dpi=PDF_DPI)
    plt.close(fig)
```

```python
        _render_pdf_notes_page(pdf, fingerprint)   # dentro do `with PdfPages(...)`, após o laço das seções
```

Em `main`, depois de `render_spec_global_png(...)`:

```python
    render_spec_notes_png(signal, sr, fingerprint["notes"], audio_path, out_dir)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest -q`
Expected: todos passam (114 da linha de base + os novos); `test_determinism.py` continua passando.

- [ ] **Step 5: Commit**

```bash
git add tone_analyzer/analyze.py tests/test_analyze.py
git commit -m "feat(analyze): notes and harmonics in fingerprint (schema 4), PDF page and spec_notes.png"
```

---

### Task 7: `compare` e `eq-match` obsoletos; documentação e versão 0.2.0

**Files:**
- Modify: `tone_analyzer/compare.py` (`main`), `tone_analyzer/eq_match.py` (`main`), `tone_analyzer/cli.py` (`USAGE`)
- Modify: `skills/tone-analyzer/SKILL.md`, `README.md`, `pyproject.toml`, `.claude-plugin/plugin.json`
- Test: `tests/test_cli.py`

**Interfaces:**
- Produces: `DEPRECATION = "tone-analyzer: '<cmd>' is obsolete — comparing two audios belongs to tone-builder; also invalid for single notes (1/3-octave bands over harmonic valleys)."` impresso no stderr por `compare` e `eq-match`; versão `0.2.0`.

- [ ] **Step 1: Write the failing test**

Em `tests/test_cli.py`:

```python
def test_compare_and_eq_match_warn_obsolete(clean_di_path: Path, tmp_path: Path, capsys):
    cli.main(["compare", str(clean_di_path), str(clean_di_path), "--out-dir", str(tmp_path / "c")])
    assert "obsolete" in capsys.readouterr().err
    cli.main(["eq-match", str(clean_di_path), str(clean_di_path), "--gains", "0,0,0,0,0,0,0,0"])
    assert "obsolete" in capsys.readouterr().err


def test_help_lists_harmonics_and_marks_obsolete(capsys):
    cli.main(["--help"])
    out = capsys.readouterr().out
    assert "harmonics" in out
    assert "obsolete" in out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_cli.py -v`
Expected: FAIL — nenhum "obsolete" no stderr nem no help

- [ ] **Step 3: Write minimal implementation**

No começo de `compare.main` e de `eq_match.main` (primeira linha do corpo):

```python
    print(
        "tone-analyzer: 'compare' is obsolete — comparing two audios belongs to tone-builder; "
        "also invalid for single notes (1/3-octave bands over harmonic valleys).",
        file=sys.stderr,
    )
```

(em `eq_match.py` com `'eq-match'`; importar `sys` onde faltar.)

Em `cli.py`, na `USAGE`, sufixar as duas linhas com `  [obsolete: use tone-builder]`.

`pyproject.toml` e `.claude-plugin/plugin.json`: `version` → `"0.2.0"`; descrição do plugin →
`"Analyzes ONE guitar audio: metrics JSON, PDF report and spectrograms, including detected notes and per-harmonic levels. compare/eq-match are obsolete (comparison lives in tone-builder)."`

`skills/tone-analyzer/SKILL.md`: na seção de modos, acrescentar `harmonics` com a sintaxe da Task 5,
dizer que `analyze` agora traz `notes` (schema 4), `spec_notes.png` e a página "Notes" do PDF, e
marcar `compare`/`eq-match` como obsoletos com o motivo medido (vales de 74–84 dB entre harmônicos
numa nota isolada; separação apaga harmônicos acima de ~H6).

`README.md`: mesma atualização na lista de comandos.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest -q`
Expected: tudo passa

- [ ] **Step 5: Commit and push**

```bash
git add -A
git commit -m "feat!: compare/eq-match obsolete (comparison moves to tone-builder); docs; 0.2.0"
git push
```

---

## Self-review

- Spec "tone-analyzer: analisa UM áudio; métrica, documentação e espectro; pitch, início de nota,
  harmônicos H1..H16 com destaque; compare/eq-match obsoletos" → Tasks 2, 3, 4 (funções), 5
  (medir num instante dado, usado pelo tone-builder), 6 (três saídas), 7 (obsoletos).
- Validador de verdade conhecida e comparação: **não** entram aqui — são do tone-builder (etapa 3).
- Nomes conferidos entre tarefas: `pitch_autocorr`, `hz_to_midi`, `midi_name`, `note_onsets`,
  `detect_notes`, `harmonic_levels`, `render_spec_notes_png`, chaves `level_db`, `neighbour_db`,
  `prominence_db`, `relative_db`.

---

## Adendo durante a execução (16/09)

**Task 2 — desvio do plano:** a 22 050 Hz o E5 saiu uma oitava abaixo (período de 33,46 amostras
entre dois lags inteiros). Corrigido reamostrando o quadro para 48 kHz, a taxa em que o método foi
validado — sem heurística de oitava. Teste inalterado.

**Task 6 — hashes fixados:** atualizados com prova: duas execuções idênticas nos 5 arquivos, e o
fingerprint sem `notes` e com schema 3 dá exatamente os hashes antigos.

**Regra de fronteira nova do jpfaria** (*"tudo que gera dados, gera informação de um áudio, fica no
tone-analyzer"*) acrescenta a Task 8.

### Task 8: métricas de uma tomada e saturação por canal

**Files:**
- Create: `tone_analyzer/take.py`
- Modify: `tone_analyzer/cli.py`, `tone_analyzer/analyze.py` (`global.saturated_samples`)
- Test: `tests/test_take.py`, `tests/test_determinism.py` (hashes, com a mesma prova da Task 6)

**Interfaces:**
- Produces: `saturated_samples(signal: np.ndarray, threshold: float = 0.999) -> int` — conta em **todos os canais**, sem mixdown;
  `take_metrics(signal: np.ndarray, sr: int, dur_s: float = 0.6) -> dict` →
  `{"duration_s", "onset_s", "midi", "name", "f0_hz", "pitch_confidence", "saturated_samples", "peak_db", "noise_floor_db", "signal_db", "snr_db"}`
  (`midi`/`name`/`f0_hz` `None` sem pitch; `noise_floor_db`/`snr_db` `None` com menos de 10 ms antes do ataque);
  CLI `tone-analyzer take <in.wav> [--out-dir DIR]` → `take.json`.
- **Não** decide aprovado/reprovado: isso é do tone-builder.

Critérios dos testes: estéreo saturando só no canal R conta > 0; nota sintética com 50 ms de ruído
baixo antes do ataque dá `midi` certo, `saturated_samples == 0` e `snr_db > 30`; nota clipada conta
> 0; arquivo só de silêncio dá `midi is None`.
