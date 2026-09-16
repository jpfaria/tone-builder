# Etapa 2 — tone-builder: esqueleto e biblioteca de guitarras

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** o repo `tone-builder` vira um pacote Python instalável com a biblioteca de guitarras: gravar
uma corda, cortar as notas, **aceitar só nota que passa no teste**, salvar em Git LFS, e reconferir
as notas existentes — com as 96 notas da PRS SE Silver Sky (posição 5) já dentro.

**Architecture:** `tone_builder/library.py` conhece o layout em disco; `acceptance.py` decide
aceitar/rejeitar a partir das métricas que o `tone-analyzer take` mede (a medição é do analyzer, a
decisão é daqui); `recorder.py` grava pela interface escolhida pelo usuário (dispositivo e canal são
parâmetros, a função de gravação é injetável para teste) e usa `tone_analyzer.notes.detect_notes`
para achar as notas; `cli.py` expõe `tone-builder library list|check|record`.

**Tech Stack:** Python ≥ 3.11, numpy, soundfile, sounddevice, PyYAML, tone-analyzer 0.2.0 (git), pytest, Git LFS.

**Spec:** `docs/superpowers/specs/2026-09-16-tone-builder-design.md` (seções "Biblioteca de guitarras",
"Regra de fronteira", "Testes").

**Repo:** `~/Projetos/github.com/jpfaria/tone-builder`

## Global Constraints

- Medir é do `tone-analyzer`; **decidir** é do `tone-builder`. Nenhuma métrica de áudio é recalculada aqui.
- Nenhuma nota é salva sem passar no teste: pitch = nota esperada; duração ≥ **0,67 s**; **zero** amostras
  saturadas; SNR ≥ **10 dB** (as 96 notas aceitas em 15/09 medem SNR mínima 10,8 dB, mediana 18,1 dB).
- Dispositivo e canal de gravação **nunca** fixos no código: são perguntados/passados.
- WAVs de `biblioteca/` em **Git LFS**. Tomadas brutas não entram no repo.
- Música de artista **nunca** entra no repo.
- `guitarra.yaml` só com o que o usuário disse ou os docs trazem; campo sem fonte fica ausente.
- Testes automáticos não tocam hardware nem escrevem fora de diretório temporário.
- Persistido em inglês (código, chaves YAML, mensagens de CLI); conversa em português.

---

## File Structure

| arquivo | responsabilidade |
|---|---|
| `pyproject.toml`, `bootstrap.sh`, `.gitignore`, `.gitattributes`, `.github/workflows/ci.yml` | pacote, venv, LFS, CI |
| `tone_builder/__init__.py` | versão |
| `tone_builder/library.py` | layout: nomes de arquivo, afinação, listar guitarras/posições/notas, ler/gravar `guitarra.yaml` e `medicao.yaml` |
| `tone_builder/acceptance.py` | decide aceitar/rejeitar uma tomada a partir de `take_metrics` |
| `tone_builder/recorder.py` | gravar (injetável), cortar notas, testar, salvar, relatório |
| `tone_builder/cli.py` | `tone-builder library list|check|record` |
| `biblioteca/prs-silver-sky-se/guitarra.yaml`, `biblioteca/prs-silver-sky-se/pos5/*.wav`, `medicao.yaml` | dados iniciais |
| `tests/test_library.py`, `tests/test_acceptance.py`, `tests/test_recorder.py`, `tests/test_cli.py`, `tests/test_real_library.py` | testes |

---

### Task 1: pacote, LFS e CI

**Files:**
- Create: `pyproject.toml`, `bootstrap.sh`, `.gitignore`, `.gitattributes`, `.github/workflows/ci.yml`, `tone_builder/__init__.py`, `tests/__init__.py`, `tests/test_package.py`

**Interfaces:**
- Produces: pacote `tone_builder` com `__version__ = "0.1.0"`; console script `tone-builder = tone_builder.cli:main`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_package.py
import tone_builder


def test_version():
    assert tone_builder.__version__ == "0.1.0"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/Projetos/github.com/jpfaria/tone-builder && python3 -m pytest tests/test_package.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'tone_builder'`

- [ ] **Step 3: Write minimal implementation**

```toml
# pyproject.toml
[build-system]
requires = ["setuptools>=69", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "tone-builder"
version = "0.1.0"
description = "Recreates the tone of a recording by measurement, and configures OpenRig, M-VAVE and Ampero II."
readme = "README.md"
requires-python = ">=3.11"
authors = [{ name = "João Paulo Faria" }]
dependencies = [
  "numpy==2.1.3",
  "soundfile==0.12.1",
  "sounddevice==0.5.6",
  "PyYAML>=6.0",
  "tone-analyzer @ git+https://github.com/jpfaria/tone-analyzer@20340ba",
]

[project.optional-dependencies]
dev = ["pytest==8.3.3"]

[project.scripts]
tone-builder = "tone_builder.cli:main"

[tool.setuptools.packages.find]
include = ["tone_builder*"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

```python
# tone_builder/__init__.py
"""tone-builder: recreate a recording's tone by measurement."""

__version__ = "0.1.0"
```

`tests/__init__.py`: arquivo vazio.

```bash
# bootstrap.sh
#!/usr/bin/env bash
# Idempotent venv setup. Subsequent runs are <1 s if pyproject.toml is unchanged.
set -euo pipefail
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STAMP=".venv/.pyproject.sha"
SHA="$(shasum -a 256 pyproject.toml | awk '{print $1}')"
if [ -f "$STAMP" ] && [ "$(cat "$STAMP")" = "$SHA" ]; then exit 0; fi
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet -e ".[dev]"
echo "$SHA" > "$STAMP"
```

```gitignore
# .gitignore
.venv/
__pycache__/
*.egg-info/
.pytest_cache/
*-bruto.wav
bruto/
```

```gitattributes
# .gitattributes
biblioteca/**/*.wav filter=lfs diff=lfs merge=lfs -text
```

```yaml
# .github/workflows/ci.yml
name: ci
on:
  push:
    branches: [main]
  pull_request:
jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python: ["3.11", "3.12"]
    steps:
      - uses: actions/checkout@v4
        with:
          lfs: true
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python }}
      - run: sudo apt-get update && sudo apt-get install -y libsndfile1 libportaudio2
      - run: pip install -e ".[dev]"
      - run: pytest -q
```

Rodar `git lfs install --local` (só neste repo; não mexe no `~/.gitconfig`).

- [ ] **Step 4: Run test to verify it passes**

Run: `pip install -e ".[dev]" && python3 -m pytest tests/test_package.py -q`
Expected: 1 passed

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "chore: python package, Git LFS for library WAVs, CI"
```

---

### Task 2: layout da biblioteca

**Files:**
- Create: `tone_builder/library.py`
- Test: `tests/test_library.py`

**Interfaces:**
- Produces:
  - `STANDARD_TUNING: dict[int, int] = {6: 40, 5: 45, 4: 50, 3: 55, 2: 59, 1: 64}` (corda → MIDI solta)
  - `library_dir() -> Path` — `$TONE_BUILDER_LIBRARY` ou `<repo>/biblioteca`
  - `note_filename(string: int, midi: int) -> str` → `"c1-64-E4.wav"`
  - `parse_note_filename(name: str) -> tuple[int, int] | None` → `(string, midi)`
  - `expected_midis(string: int, frets: range = range(16), tuning: dict[int, int] = STANDARD_TUNING) -> list[int]`
  - `list_guitars(root: Path) -> list[str]`
  - `list_positions(root: Path, guitar: str) -> list[str]`
  - `list_notes(root: Path, guitar: str, position: str) -> list[Path]` (ordenado; ignora arquivos que não seguem o padrão)
  - `read_yaml(path: Path) -> dict` / `write_yaml(path: Path, data: dict) -> None`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_library.py
from pathlib import Path

from tone_builder import library


def test_note_filename_roundtrip():
    assert library.note_filename(1, 64) == "c1-64-E4.wav"
    assert library.note_filename(2, 61) == "c2-61-C#4.wav"
    assert library.parse_note_filename("c2-61-C#4.wav") == (2, 61)
    assert library.parse_note_filename("c6-bruto.wav") is None
    assert library.parse_note_filename("readme.txt") is None


def test_expected_midis_standard_tuning():
    assert library.expected_midis(6)[:3] == [40, 41, 42]
    assert library.expected_midis(1)[-1] == 64 + 15


def test_listing(tmp_path: Path):
    pos = tmp_path / "prs-silver-sky-se" / "pos5"
    pos.mkdir(parents=True)
    for n in ("c1-64-E4.wav", "c1-65-F4.wav", "c1-bruto.wav"):
        (pos / n).write_bytes(b"")
    (tmp_path / "prs-silver-sky-se" / "guitarra.yaml").write_text("name: x\n")
    assert library.list_guitars(tmp_path) == ["prs-silver-sky-se"]
    assert library.list_positions(tmp_path, "prs-silver-sky-se") == ["pos5"]
    assert [p.name for p in library.list_notes(tmp_path, "prs-silver-sky-se", "pos5")] == ["c1-64-E4.wav", "c1-65-F4.wav"]


def test_yaml_roundtrip(tmp_path: Path):
    p = tmp_path / "a.yaml"
    library.write_yaml(p, {"b": 1, "a": [1, 2]})
    assert library.read_yaml(p) == {"b": 1, "a": [1, 2]}


def test_library_dir_env(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("TONE_BUILDER_LIBRARY", str(tmp_path))
    assert library.library_dir() == tmp_path
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_library.py -q`
Expected: FAIL — `ImportError: cannot import name 'library'`

- [ ] **Step 3: Write minimal implementation**

```python
# tone_builder/library.py
"""On-disk layout of the guitar library.

biblioteca/<guitar>/guitarra.yaml
biblioteca/<guitar>/<position>/c<string>-<midi>-<note>.wav
biblioteca/<guitar>/<position>/medicao.yaml
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import yaml
from tone_analyzer.notes import midi_name

STANDARD_TUNING: dict[int, int] = {6: 40, 5: 45, 4: 50, 3: 55, 2: 59, 1: 64}
_NOTE_RE = re.compile(r"^c([1-6])-(\d+)-([A-G]#?-?\d)\.wav$")


def library_dir() -> Path:
    env = os.environ.get("TONE_BUILDER_LIBRARY")
    if env:
        return Path(env)
    return Path(__file__).resolve().parent.parent / "biblioteca"


def note_filename(string: int, midi: int) -> str:
    return f"c{string}-{midi}-{midi_name(midi)}.wav"


def parse_note_filename(name: str) -> tuple[int, int] | None:
    m = _NOTE_RE.match(name)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


def expected_midis(
    string: int, frets: range = range(16), tuning: dict[int, int] = STANDARD_TUNING
) -> list[int]:
    return [tuning[string] + f for f in frets]


def list_guitars(root: Path) -> list[str]:
    return sorted(p.name for p in root.iterdir() if p.is_dir() and (p / "guitarra.yaml").exists())


def list_positions(root: Path, guitar: str) -> list[str]:
    return sorted(p.name for p in (root / guitar).iterdir() if p.is_dir())


def list_notes(root: Path, guitar: str, position: str) -> list[Path]:
    d = root / guitar / position
    return sorted(p for p in d.iterdir() if parse_note_filename(p.name))


def read_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text()) or {}


def write_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_library.py -q`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add tone_builder/library.py tests/test_library.py
git commit -m "feat(library): on-disk layout, note filenames, standard tuning"
```

---

### Task 3: decisão de aceitar uma tomada

**Files:**
- Create: `tone_builder/acceptance.py`
- Test: `tests/test_acceptance.py`

**Interfaces:**
- Consumes: dict no formato de `tone_analyzer.take.take_metrics`
- Produces: `MIN_DURATION_S = 0.67`, `MIN_SNR_DB = 10.0`,
  `judge_take(metrics: dict, expected_midi: int) -> dict` → `{"accepted": bool, "reasons": list[str]}`
  (razões em inglês, uma por critério reprovado: `"pitch"`, `"duration"`, `"saturation"`, `"snr"`).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_acceptance.py
from tone_builder.acceptance import judge_take

GOOD = {"midi": 64, "duration_s": 0.9, "saturated_samples": 0, "snr_db": 18.0}


def test_good_take_is_accepted():
    assert judge_take(GOOD, 64) == {"accepted": True, "reasons": []}


def test_each_criterion_rejects():
    assert judge_take({**GOOD, "midi": 52}, 64)["reasons"] == ["pitch"]
    assert judge_take({**GOOD, "midi": None}, 64)["reasons"] == ["pitch"]
    assert judge_take({**GOOD, "duration_s": 0.5}, 64)["reasons"] == ["duration"]
    assert judge_take({**GOOD, "saturated_samples": 1}, 64)["reasons"] == ["saturation"]
    assert judge_take({**GOOD, "snr_db": 9.9}, 64)["reasons"] == ["snr"]
    assert judge_take({**GOOD, "snr_db": None}, 64)["reasons"] == ["snr"]


def test_all_reasons_reported_together():
    bad = {"midi": 50, "duration_s": 0.1, "saturated_samples": 10, "snr_db": 2.0}
    r = judge_take(bad, 64)
    assert r["accepted"] is False
    assert r["reasons"] == ["pitch", "duration", "saturation", "snr"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_acceptance.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'tone_builder.acceptance'`

- [ ] **Step 3: Write minimal implementation**

```python
# tone_builder/acceptance.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_acceptance.py -q`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add tone_builder/acceptance.py tests/test_acceptance.py
git commit -m "feat(acceptance): accept a take only if pitch, duration, saturation and SNR pass"
```

---

### Task 4: gravar uma corda, cortar, testar e salvar

**Files:**
- Create: `tone_builder/recorder.py`
- Test: `tests/test_recorder.py`

**Interfaces:**
- Consumes: `tone_analyzer.notes.detect_notes`, `tone_analyzer.take.take_metrics`, `library.*`, `acceptance.judge_take`
- Produces:
  - `SR = 48000`, `PREROLL_S = 0.02`
  - `record(seconds: float, device: str | int, channel: int, sr: int = SR, playrec=None) -> np.ndarray`
    — toca um bipe de 0,15 s nas saídas 1–2 no início e grava o canal `channel` (1-based); `playrec`
    injetável com a assinatura de `sounddevice.playrec` (padrão: `sounddevice.playrec` + `sounddevice.wait`).
  - `cut_notes(signal: np.ndarray, sr: int, expected: list[int]) -> dict[int, np.ndarray]`
    — uma fatia por nota esperada detectada, começando `PREROLL_S` antes do ataque e terminando no
    próximo ataque (ou 2,0 s depois); se a mesma nota aparece mais de uma vez, fica a fatia mais longa.
  - `save_string(root: Path, guitar: str, position: str, string: int, signal: np.ndarray, sr: int) -> dict`
    → `{"accepted": [midi], "rejected": {midi: [reasons]}, "missing": [midi]}`; grava só as aceitas
    como `c<string>-<midi>-<nome>.wav` (float 32) e atualiza `medicao.yaml` da posição com as métricas e a
    decisão de cada nota testada.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_recorder.py
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from tone_builder import library, recorder


def _note(midi: int, sr: int, dur: float, gain: float = 0.5) -> np.ndarray:
    t = np.arange(int(dur * sr)) / sr
    f0 = 440.0 * 2 ** ((midi - 69) / 12)
    x = sum(10 ** (db / 20) * np.sin(2 * np.pi * k * f0 * t) for k, db in enumerate([0, -6, -12], 1))
    x = x * np.minimum(t / 0.005, 1) * np.exp(-t / 1.5)
    return (gain * x / np.abs(x).max()).astype(np.float32)


def _string_take(midis: list[int], sr: int, noise: float = 1e-4, clip_midi: int | None = None) -> np.ndarray:
    rng = np.random.default_rng(42)
    parts = [np.zeros(int(0.5 * sr), dtype=np.float32)]
    for m in midis:
        n = _note(m, sr, 1.5, gain=3.0 if m == clip_midi else 0.5)
        parts += [np.clip(n, -1, 1), np.zeros(int(0.5 * sr), dtype=np.float32)]
    x = np.concatenate(parts)
    return (x + rng.standard_normal(len(x)).astype(np.float32) * noise).astype(np.float32)


def test_record_uses_given_device_and_channel():
    calls = {}

    def fake_playrec(out, samplerate, device, input_mapping, output_mapping, dtype):
        calls.update(device=device, input_mapping=input_mapping, sr=samplerate, n=len(out))
        return np.zeros((len(out), 1), dtype=np.float32)

    x = recorder.record(2.0, device="Quantum HD 8", channel=3, playrec=fake_playrec)
    assert calls["device"] == "Quantum HD 8"
    assert calls["input_mapping"] == [3]
    assert calls["sr"] == 48000 and calls["n"] == 96000
    assert x.shape == (96000,)


def test_cut_notes_finds_expected():
    sr = 48000
    x = _string_take([64, 65, 66], sr)
    cuts = recorder.cut_notes(x, sr, [64, 65, 66, 67])
    assert sorted(cuts) == [64, 65, 66]
    assert all(len(c) >= int(0.67 * sr) for c in cuts.values())


def test_save_string_accepts_good_rejects_clipped(tmp_path: Path):
    sr = 48000
    (tmp_path / "g").mkdir()
    library.write_yaml(tmp_path / "g" / "guitarra.yaml", {"name": "test"})
    x = _string_take([64, 65, 66], sr, clip_midi=65)
    report = recorder.save_string(tmp_path, "g", "pos5", 1, x, sr)
    assert report["accepted"] == [64, 66]
    assert report["rejected"] == {65: ["saturation"]}
    assert 67 in report["missing"]
    names = [p.name for p in library.list_notes(tmp_path, "g", "pos5")]
    assert names == ["c1-64-E4.wav", "c1-66-F#4.wav"]
    med = library.read_yaml(tmp_path / "g" / "pos5" / "medicao.yaml")
    assert med["c1-65-F4"]["accepted"] is False
    assert med["c1-64-E4"]["accepted"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_recorder.py -q`
Expected: FAIL — `ImportError: cannot import name 'recorder'`

- [ ] **Step 3: Write minimal implementation**

```python
# tone_builder/recorder.py
"""Record one string of a guitar, cut the notes, test each one, save only the accepted ones."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile as sf
from tone_analyzer.notes import detect_notes
from tone_analyzer.take import take_metrics

from tone_builder import library
from tone_builder.acceptance import judge_take

SR = 48000
PREROLL_S = 0.02
BEEP_S = 0.15


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


def save_string(root: Path, guitar: str, position: str, string: int, signal: np.ndarray, sr: int) -> dict:
    expected = library.expected_midis(string)
    pos_dir = root / guitar / position
    pos_dir.mkdir(parents=True, exist_ok=True)
    med_path = pos_dir / "medicao.yaml"
    med = library.read_yaml(med_path) if med_path.exists() else {}
    report = {"accepted": [], "rejected": {}, "missing": []}
    cuts = cut_notes(signal, sr, expected)
    for midi in expected:
        if midi not in cuts:
            report["missing"].append(midi)
            continue
        metrics = take_metrics(cuts[midi], sr)
        verdict = judge_take(metrics, midi)
        name = library.note_filename(string, midi)
        med[name[:-4]] = {**{k: metrics[k] for k in ("midi", "duration_s", "saturated_samples", "snr_db", "peak_db")},
                          **verdict}
        if verdict["accepted"]:
            sf.write(pos_dir / name, cuts[midi], sr, subtype="FLOAT")
            report["accepted"].append(midi)
        else:
            report["rejected"][midi] = verdict["reasons"]
    library.write_yaml(med_path, med)
    return report
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_recorder.py -q`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add tone_builder/recorder.py tests/test_recorder.py
git commit -m "feat(recorder): record a string with a chosen device/channel, save only accepted notes"
```

---

### Task 5: CLI `library list | check | record`

**Files:**
- Create: `tone_builder/cli.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `library`, `recorder`, `acceptance`, `tone_analyzer.take.take_metrics`
- Produces:
  - `tone-builder library list [--root DIR]` → uma linha por guitarra/posição: `prs-silver-sky-se pos5 96 notes`
  - `tone-builder library check GUITAR POSITION [--root DIR]` → reconfere cada nota salva; imprime aceitas/rejeitadas; sai 1 se alguma rejeitada; reescreve `medicao.yaml`
  - `tone-builder library record GUITAR POSITION STRING --device DEV --channel N [--seconds 45] [--root DIR]`
    → sem `--device` ou `--channel`, sai 2 com mensagem pedindo os dois (nunca assume)
  - `main(argv: list[str] | None = None) -> int`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli.py
from pathlib import Path

import numpy as np
import soundfile as sf

from tests.test_recorder import _note
from tone_builder import cli, library


def _lib(tmp_path: Path) -> Path:
    sr = 48000
    pos = tmp_path / "g" / "pos5"
    pos.mkdir(parents=True)
    library.write_yaml(tmp_path / "g" / "guitarra.yaml", {"name": "test"})
    rng = np.random.default_rng(1)
    for midi in (64, 65):
        x = np.concatenate([rng.standard_normal(int(0.02 * sr)) * 1e-4, _note(midi, sr, 1.0)]).astype(np.float32)
        sf.write(pos / library.note_filename(1, midi), x, sr, subtype="FLOAT")
    sf.write(pos / library.note_filename(1, 66), np.clip(_note(66, sr, 1.0, gain=3.0), -1, 1), sr, subtype="FLOAT")
    return tmp_path


def test_list(tmp_path: Path, capsys):
    root = _lib(tmp_path)
    assert cli.main(["library", "list", "--root", str(root)]) == 0
    assert "g pos5 3 notes" in capsys.readouterr().out


def test_check_flags_bad_note(tmp_path: Path, capsys):
    root = _lib(tmp_path)
    assert cli.main(["library", "check", "g", "pos5", "--root", str(root)]) == 1
    out = capsys.readouterr().out
    assert "c1-66-F#4" in out and "saturation" in out
    assert library.read_yaml(root / "g" / "pos5" / "medicao.yaml")["c1-64-E4"]["accepted"] is True


def test_record_requires_device_and_channel(tmp_path: Path, capsys):
    assert cli.main(["library", "record", "g", "pos5", "1", "--root", str(tmp_path)]) == 2
    assert "--device" in capsys.readouterr().err
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_cli.py -q`
Expected: FAIL — `ImportError: cannot import name 'cli'`

- [ ] **Step 3: Write minimal implementation**

```python
# tone_builder/cli.py
"""tone-builder command line."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import soundfile as sf
from tone_analyzer.take import take_metrics

from tone_builder import library, recorder
from tone_builder.acceptance import judge_take


def _root(a) -> Path:
    return Path(a.root) if a.root else library.library_dir()


def _list(a) -> int:
    root = _root(a)
    for g in library.list_guitars(root):
        for p in library.list_positions(root, g):
            print(f"{g} {p} {len(library.list_notes(root, g, p))} notes")
    return 0


def _check(a) -> int:
    root = _root(a)
    med_path = root / a.guitar / a.position / "medicao.yaml"
    med = library.read_yaml(med_path) if med_path.exists() else {}
    bad = 0
    for path in library.list_notes(root, a.guitar, a.position):
        _, midi = library.parse_note_filename(path.name)
        x, sr = sf.read(path, dtype="float32", always_2d=False)
        if x.ndim == 2:
            x = x.T
        metrics = take_metrics(x, sr)
        verdict = judge_take(metrics, midi)
        med[path.stem] = {**{k: metrics[k] for k in ("midi", "duration_s", "saturated_samples", "snr_db", "peak_db")},
                          **verdict}
        if verdict["accepted"]:
            print(f"ok       {path.stem}")
        else:
            bad += 1
            print(f"REJECTED {path.stem}: {', '.join(verdict['reasons'])}")
    library.write_yaml(med_path, med)
    return 1 if bad else 0


def _record(a) -> int:
    if a.device is None or a.channel is None:
        print("record: pass --device and --channel — where to listen is never assumed", file=sys.stderr)
        return 2
    x = recorder.record(a.seconds, a.device, a.channel)
    rep = recorder.save_string(_root(a), a.guitar, a.position, a.string, x, recorder.SR)
    print(f"accepted: {rep['accepted']}")
    print(f"rejected: {rep['rejected']}")
    print(f"missing:  {rep['missing']}")
    return 0 if not rep["rejected"] and not rep["missing"] else 1


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="tone-builder")
    sub = p.add_subparsers(dest="group", required=True)
    lib = sub.add_parser("library").add_subparsers(dest="cmd", required=True)
    lp = lib.add_parser("list")
    lp.add_argument("--root")
    cp = lib.add_parser("check")
    cp.add_argument("guitar")
    cp.add_argument("position")
    cp.add_argument("--root")
    rp = lib.add_parser("record")
    rp.add_argument("guitar")
    rp.add_argument("position")
    rp.add_argument("string", type=int)
    rp.add_argument("--device")
    rp.add_argument("--channel", type=int)
    rp.add_argument("--seconds", type=float, default=45.0)
    rp.add_argument("--root")
    a = p.parse_args(argv)
    return {"list": _list, "check": _check, "record": _record}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest -q`
Expected: todos passam

- [ ] **Step 5: Commit**

```bash
git add tone_builder/cli.py tests/test_cli.py
git commit -m "feat(cli): tone-builder library list|check|record"
```

---

### Task 6: importar as 96 notas da Silver Sky e reconferir

**Files:**
- Create: `biblioteca/prs-silver-sky-se/guitarra.yaml`, `biblioteca/prs-silver-sky-se/pos5/*.wav` (LFS), `biblioteca/prs-silver-sky-se/pos5/medicao.yaml`
- Create: `tests/test_real_library.py`

**Interfaces:**
- Consumes: CLI `library check`
- Produces: biblioteca inicial no repo.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_real_library.py
"""The shipped library must pass its own acceptance test."""

from pathlib import Path

import pytest

from tone_builder import cli, library

ROOT = library.library_dir()


def _lfs_pointer(p: Path) -> bool:
    return p.stat().st_size < 1024 and p.read_bytes().startswith(b"version https://git-lfs")


def test_silversky_pos5_has_96_accepted_notes(capsys):
    notes = library.list_notes(ROOT, "prs-silver-sky-se", "pos5")
    if notes and _lfs_pointer(notes[0]):
        pytest.skip("LFS objects not pulled")
    assert len(notes) == 96
    rc = cli.main(["library", "check", "prs-silver-sky-se", "pos5", "--root", str(ROOT)])
    out = capsys.readouterr().out
    rejected = [l for l in out.splitlines() if l.startswith("REJECTED")]
    assert len(rejected) <= 3, rejected   # 93/96 pitch on 2026-09-16; the misses are octave errors
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_real_library.py -q`
Expected: FAIL — `FileNotFoundError` (a pasta `biblioteca/prs-silver-sky-se/pos5` não existe)

- [ ] **Step 3: Implementation**

```bash
mkdir -p biblioteca/prs-silver-sky-se/pos5
cp ~/.openrig/evaluations/_biblioteca/prs-silver-sky-se/pos5/c[1-6]-[0-9]*-*.wav biblioteca/prs-silver-sky-se/pos5/
```

```yaml
# biblioteca/prs-silver-sky-se/guitarra.yaml
# Only what jpfaria stated or music-setup documents. Missing = not documented.
name: PRS SE Silver Sky
pickups: stock                     # music-setup/docs/guitarras.md: "originais"
tuning: standard                   # 93/96 notes measure the pitch standard tuning predicts
selector_positions:                # jpfaria, 2026-09-15
  pos1: bridge
  pos2: bridge + middle
  pos3: middle
  pos4: middle + neck
  pos5: neck
recorded:
  pos5: "2026-09-15"
```

Rodar `tone-builder library check prs-silver-sky-se pos5` para gerar `medicao.yaml`.

**As 3 notas que falham no pitch não são apagadas nem escondidas:** elas ficam, marcadas
`accepted: false` com o motivo no `medicao.yaml`, até serem regravadas. O teste tolera exatamente
essas 3.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest -q`
Expected: todos passam; `git lfs ls-files | wc -l` → 96

- [ ] **Step 5: Commit and push**

```bash
git add .gitattributes biblioteca tests/test_real_library.py
git commit -m "data: PRS SE Silver Sky pos5 — 96 notes (LFS) and their measured acceptance"
git push
```

---

## Self-review

- Spec "Biblioteca de guitarras": layout (T2), LFS (T1, T6), teste por nota com os 4 critérios (T3),
  gravação perguntando entrada (T4, T5), bipe (T4), nunca apagar nota boa → aceita só grava as
  aprovadas e não remove existentes (T4), tomada bruta fora (T1 `.gitignore`), música fora (sem
  arquivo de música em nenhuma tarefa), 96 notas iniciais (T6), `guitarra.yaml` só com fonte (T6).
- Fronteira: medição sempre via `tone_analyzer` (`take_metrics`, `detect_notes`); decisão em `acceptance.py`.
- Nomes conferidos: `library_dir`, `note_filename`, `parse_note_filename`, `expected_midis`,
  `list_guitars`, `list_positions`, `list_notes`, `read_yaml`, `write_yaml`, `judge_take`,
  `record`, `cut_notes`, `save_string`, `SR`, `PREROLL_S`.
- Fora desta etapa: skill do tone-builder e manifesto de plugin (etapa 3, com o método).

---

## Resultado da execução (16/09)

Todas as 6 tarefas concluídas; CI verde em Python 3.11 e 3.12 com a biblioteca real reconferida
(LFS baixado, teste não pulado).

**Desvios, todos achados rodando em dado real e não em sintético:**

1. **Cortador de notas nas 6 tomadas brutas reais:** achou 90/96 notas. Diagnóstico medido: um ataque
   não detectado; um A#2 oscilando entre MIDI 46 e 47 descartado pela regra de sustentação; um F3
   lido como MIDI 89 (= `fmax`) por pico na borda da busca. As duas últimas eram defeito de análise
   e foram corrigidas no `tone-analyzer` (pico na borda = confiança 0; sustentação por distância à
   mediana ≤ ½ semitom) → 91/96, sem regressão nas notas cortadas (93/96). A hipótese inicial
   (restringir a faixa de pitch à corda) foi **testada e refutada**: recuperava só 1 nota.
2. **Pin do `tone-analyzer` por commit não atualizava:** com a versão igual (0.2.0), o pip manteve o
   código antigo em silêncio. Correção: `tone-analyzer` 0.2.1, tag `v0.2.1` (padrão de tags do repo),
   e o `tone-builder` fixa pela tag.
3. **Id da guitarra:** `prs-silver-sky-se` (jpfaria), não `silversky-se`.

**Biblioteca importada:** 96 notas, `library check` → 93 aceitas, 3 rejeitadas por pitch
(c1-66-F#4, c2-73-C#5, c3-66-F#4), mantidas com `accepted: false` até regravar.
