# Etapa 3 — tone-builder: o método

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** o método validado em 16/09 (alvo no disco lido nos harmônicos, comparação por nota,
escolha de corda, retenção, bateria completa com portão do compressor, margem de pico, relatório
"pronto"/"parcial", pesquisa com fonte, validador de verdade conhecida) vira código testado no
`tone-builder`, **sem conhecer aparelho nenhum**: o render entra como função injetada.

**Architecture:** um módulo por decisão em `tone_builder/`. A medição de UM áudio vem do
`tone-analyzer` (`detect_notes`, `harmonic_levels`, `take_onset`, `saturated_samples`); daqui só sai
o que compara ou decide. Todo render é um `Renderer = Callable[[Path, Path], None]` (DI → wet) que
a etapa 4 implementa para o OpenRig; os testes usam dublês que processam o WAV em numpy.

**Tech Stack:** Python ≥ 3.11, numpy 2.1.3, scipy 1.14.1, soundfile, PyYAML, tone-analyzer v0.2.1, pytest.

**Spec:** `docs/superpowers/specs/2026-09-16-tone-builder-design.md` (seções "Números", "Regra de
fronteira", "Fluxo de um timbre", "Testes", "Erros", "Ordem de implementação" item 3).

**Origem do código:** `music-setup/tools/openrig/timbre_medida.py` e `valida_timbre_medida.py`
(commit c3a698d) e `music-setup/docs/metodo-timbre.md` (procedimento, rodadas 5–8).

## Global Constraints

- Medir UM áudio é do `tone-analyzer`; nenhuma métrica de áudio é reimplementada aqui.
- Alvo = **disco** lido em k·f0; a pista separada só localiza nota e tempo.
- Janela da nota: **0,6 s** a partir do ataque, nos dois lados.
- Harmônico aceito no alvo: destaque **≥ 10 dB** sobre a vizinhança. Nota entra com **≥ 5** aceitos.
- Nível removido pela média dos harmônicos aceitos; desvio da nota = RMS do resto.
- Nenhuma escolha sem **retenção** (ajusta numa metade das notas, decide na outra).
- Compressor só conta como testado com redução de ganho medida **≥ 3 dB**.
- Candidatos **com fonte** e **sem fonte** ranqueados separados; só com fonte pode ser escolhido.
- Margem: **zero** amostras saturadas com o DI em **+12** e **+18 dB**.
- Relatório: "pronto" só se toda classe da bateria tem número ou motivo e a margem passou; senão "parcial".
- Validador: erro ≤ **2 dB** a **−6 dB** de dominância, **zero** falso positivo.
- Render que sai em silêncio (pico < 1e-4) reprova o candidato.
- Testes não tocam hardware nem escrevem fora de `tmp_path`. Música de artista nunca entra no repo.
- Código, chaves e mensagens em inglês; "pronto"/"parcial" são os dois valores de status da spec.

---

## File Structure

| arquivo | responsabilidade |
|---|---|
| `tone_builder/audio.py` | ler WAV em mono 48 kHz; `rms_db` |
| `tone_builder/target.py` | alvo: notas da pista + nível dos harmônicos no disco |
| `tone_builder/compare.py` | desvio de uma nota renderizada contra a nota do alvo |
| `tone_builder/render.py` | `Renderer`, `RenderError`, renderizar e medir as notas atribuídas |
| `tone_builder/strings.py` | notas da biblioteca por MIDI; escolha da corda por medição |
| `tone_builder/retention.py` | divisão ajuste/teste e decisão com ruído medido |
| `tone_builder/compressor.py` | redução de ganho e portão de 3 dB |
| `tone_builder/margin.py` | DI +12/+18 e amostras saturadas |
| `tone_builder/research.py` | validação do arquivo de pesquisa (fonte, era da gravação) |
| `tone_builder/battery.py` | classes da bateria, rodar candidatos, decisão por classe |
| `tone_builder/report.py` | status pronto/parcial e texto do relatório |
| `tone_builder/validator.py` | verdade conhecida com acompanhamento sintético |
| `tone_builder/cli.py` | `tone-builder target` e `tone-builder validate` |
| `docs/metodo.md` | a parte genérica de `music-setup/docs/metodo-timbre.md` |

---

### Task 1: áudio, alvo e comparação

**Files:** Create `tone_builder/audio.py`, `tone_builder/target.py`, `tone_builder/compare.py`;
Test `tests/test_target.py`, `tests/test_compare.py`; Modify `pyproject.toml` (scipy==1.14.1).

**Interfaces — Produces:**
- `audio.SR = 48000`; `audio.load_mono(path) -> np.ndarray` (48 kHz); `audio.to_mono_48k(x, sr) -> np.ndarray`; `audio.rms_db(x) -> float`
- `target.PROMINENCE_DB = 10.0`, `target.MIN_HARMONICS = 5`, `target.DUR_S = 0.6`
- `target.midi_hz(midi) -> float`
- `target.build_target(disc: ndarray, lead: ndarray, available_midis: set[int]) -> list[dict]` — ambos já a 48 kHz; cada item `{"start_s", "midi", "name", "level_db": list[float|None], "accepted": list[bool]}`
- `compare.note_deviation(target_note: dict, wet: ndarray) -> dict | None` — wet a 48 kHz; `{"rms_db", "harmonics", "points": list[(hz, db)]}`
- `compare.mean_deviation(per_note: list[dict | None]) -> float | None`

- [ ] **Step 1: testes que falham** — sinal sintético com harmônicos conhecidos:
  - disco = pista = nota MIDI 62 (soma de 8 harmônicos a −6 dB/harmônico) a partir de 0,5 s → `build_target` devolve 1 nota MIDI 62 com ≥ 5 aceitos e `level_db[1]-level_db[0]` ≈ −6 dB (±1).
  - MIDI fora de `available_midis` → lista vazia.
  - disco só ruído branco na hora da nota → nota descartada (< 5 aceitos).
  - `note_deviation` de uma nota contra ela mesma → `rms_db` < 0,5; com H2..H8 atenuados em 6 dB alternados (+6/−6) → `rms_db` ≈ 6 (±1); o nível (ganho de −20 dB no wet inteiro) não muda o resultado (±0,1).
  - wet em silêncio → `None`.
- [ ] **Step 2:** `pytest tests/test_target.py tests/test_compare.py` → FAIL (módulos não existem).
- [ ] **Step 3: implementação**

```python
# tone_builder/audio.py
from __future__ import annotations
from math import gcd
from pathlib import Path
import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

SR = 48000

def to_mono_48k(x: np.ndarray, sr: int) -> np.ndarray:
    x = np.asarray(x, dtype=np.float64)
    if x.ndim > 1:
        x = x.mean(axis=1)
    if sr != SR:
        g = gcd(SR, sr)
        x = resample_poly(x, SR // g, sr // g)
    return x

def load_mono(path: Path) -> np.ndarray:
    x, sr = sf.read(str(path), always_2d=False)
    return to_mono_48k(x, sr)

def rms_db(x: np.ndarray) -> float:
    return float(20.0 * np.log10(np.sqrt(np.mean(np.square(x, dtype=np.float64))) + 1e-12))
```

```python
# tone_builder/target.py
"""The target: where the guitar plays (separated track) and how loud each
harmonic is (the record). Separation deletes harmonics above ~H6, so the
separated track never gives a level."""
from __future__ import annotations
import numpy as np
from tone_analyzer.notes import detect_notes, harmonic_levels, midi_name
from tone_builder.audio import SR

PROMINENCE_DB = 10.0   # with 10 dB the background adds <= 0.4 dB to the peak
MIN_HARMONICS = 5
DUR_S = 0.6

def midi_hz(midi: int) -> float:
    return 440.0 * 2.0 ** ((midi - 69) / 12.0)

def build_target(disc: np.ndarray, lead: np.ndarray, available_midis: set[int]) -> list[dict]:
    out = []
    span = int(DUR_S * SR)
    for n in detect_notes(lead, SR, dur_s=DUR_S):
        if n["midi"] not in available_midis:
            continue
        start = int(round(n["start_s"] * SR))
        if start + span >= min(len(lead), len(disc)):
            continue
        h = harmonic_levels(disc, SR, n["start_s"], midi_hz(n["midi"]), dur_s=DUR_S)
        if h is None:
            continue
        accepted = [p is not None and p >= PROMINENCE_DB for p in h["prominence_db"]]
        if sum(accepted) < MIN_HARMONICS:
            continue
        out.append({"start_s": n["start_s"], "midi": n["midi"], "name": midi_name(n["midi"]),
                    "level_db": h["level_db"], "accepted": accepted})
    return out
```

```python
# tone_builder/compare.py
"""Deviation of a rendered note from the target note, on the target's accepted
harmonics, with level removed (mean of the differences)."""
from __future__ import annotations
import numpy as np
from tone_analyzer.notes import harmonic_levels
from tone_analyzer.take import take_onset
from tone_builder.audio import SR
from tone_builder.target import DUR_S, MIN_HARMONICS, midi_hz

def note_deviation(target_note: dict, wet: np.ndarray) -> dict | None:
    onset = take_onset(wet, SR)
    if onset is None:
        return None
    f0 = midi_hz(target_note["midi"])
    h = harmonic_levels(wet, SR, onset / SR, f0, dur_s=DUR_S)
    if h is None:
        return None
    ks = [k for k, (ok, t, w) in enumerate(zip(target_note["accepted"], target_note["level_db"], h["level_db"]))
          if ok and t is not None and w is not None]
    if len(ks) < MIN_HARMONICS:
        return None
    d = np.array([target_note["level_db"][k] - h["level_db"][k] for k in ks])
    d = d - d.mean()
    return {"rms_db": float(np.sqrt(np.mean(d ** 2))), "harmonics": len(ks),
            "points": [(f0 * (k + 1), float(v)) for k, v in zip(ks, d)]}

def mean_deviation(per_note: list[dict | None]) -> float | None:
    vals = [p["rms_db"] for p in per_note if p is not None]
    return float(np.mean(vals)) if vals else None
```

- [ ] **Step 4:** testes → PASS; `pytest` inteiro verde.
- [ ] **Step 5:** commit `feat(method): target on the record's harmonics and per-note deviation`.

### Task 2: render injetado e escolha da corda

**Files:** Create `tone_builder/render.py`, `tone_builder/strings.py`; Test `tests/test_render.py`, `tests/test_strings.py`.

**Interfaces — Consumes:** Task 1; `library.list_notes`, `library.parse_note_filename`.
**Produces:**
- `render.Renderer = Callable[[Path, Path], None]`; `render.RenderError(Exception)`; `render.SILENCE = 1e-4`
- `render.render_note(render, di: Path, workdir: Path, tag: str) -> np.ndarray` (48 kHz mono; `RenderError` se não escreveu ou saiu em silêncio)
- `render.measure(render, assignments: list[dict], workdir: Path) -> dict` — `assignments` itens `{"note": target_note, "di": Path}`; devolve `{"deviation": float|None, "per_note": list[float|None]}`
- `strings.library_by_midi(root, guitar, position) -> dict[int, list[Path]]`
- `strings.choose_strings(target, by_midi, render, workdir) -> list[dict]` — para cada nota do alvo com par na biblioteca, mede todas as cordas com o `render` de referência e fica com a menor; itens `{"note", "di", "deviation", "alternatives": {str(path): float|None}}`; notas sem par ficam de fora.

- [ ] **Step 1: testes que falham** — dublê `copy_render` (copia o WAV) e `silent_render` (escreve zeros); biblioteca falsa em `tmp_path` com duas cordas para MIDI 64 onde só uma bate com o alvo sintético; `choose_strings` escolhe a que bate; `render_note` com `silent_render` → `RenderError`; `measure` devolve `per_note` na ordem das atribuições.
- [ ] **Step 2:** FAIL.
- [ ] **Step 3: implementação**

```python
# tone_builder/render.py
from __future__ import annotations
from pathlib import Path
from typing import Callable
import numpy as np
from tone_builder.audio import load_mono
from tone_builder.compare import note_deviation, mean_deviation

Renderer = Callable[[Path, Path], None]
SILENCE = 1e-4

class RenderError(Exception):
    pass

def render_note(render: Renderer, di: Path, workdir: Path, tag: str) -> np.ndarray:
    workdir.mkdir(parents=True, exist_ok=True)
    wet = workdir / f"{tag}.wav"
    render(Path(di), wet)
    if not wet.exists():
        raise RenderError(f"render wrote nothing: {wet}")
    x = load_mono(wet)
    if len(x) == 0 or np.abs(x).max() < SILENCE:
        raise RenderError(f"render is silent: {wet}")
    return x

def measure(render: Renderer, assignments: list[dict], workdir: Path) -> dict:
    per_note = []
    for i, a in enumerate(assignments):
        x = render_note(render, a["di"], workdir, f"{i:02d}-{a['note']['midi']}")
        per_note.append(note_deviation(a["note"], x))
    return {"deviation": mean_deviation(per_note),
            "per_note": [None if p is None else p["rms_db"] for p in per_note]}
```

```python
# tone_builder/strings.py
"""The string a note is played on moved the deviation by up to 10.7 dB in
Gravity; the old rule (fret closest to 7) was wrong on 7 of 8 notes. The
string is chosen by measuring every string the library has for that note."""
from __future__ import annotations
from pathlib import Path
from tone_builder import library
from tone_builder.render import Renderer, render_note
from tone_builder.compare import note_deviation

def library_by_midi(root: Path, guitar: str, position: str) -> dict[int, list[Path]]:
    out: dict[int, list[Path]] = {}
    for p in library.list_notes(root, guitar, position):
        _, midi = library.parse_note_filename(p.name)
        out.setdefault(midi, []).append(p)
    return out

def choose_strings(target: list[dict], by_midi: dict[int, list[Path]], render: Renderer, workdir: Path) -> list[dict]:
    out = []
    for i, note in enumerate(target):
        alts = {}
        for di in by_midi.get(note["midi"], []):
            x = render_note(render, di, workdir, f"string-{i:02d}-{di.stem}")
            d = note_deviation(note, x)
            alts[str(di)] = None if d is None else d["rms_db"]
        scored = [(v, k) for k, v in alts.items() if v is not None]
        if not scored:
            continue
        best_dev, best = min(scored)
        out.append({"note": note, "di": Path(best), "deviation": best_dev, "alternatives": alts})
    return out
```

- [ ] **Step 4:** PASS. **Step 5:** commit `feat(method): injected renderer and string choice by measurement`.

### Task 3: retenção, compressor e margem

**Files:** Create `tone_builder/retention.py`, `tone_builder/compressor.py`, `tone_builder/margin.py`;
Test `tests/test_retention.py`, `tests/test_compressor.py`, `tests/test_margin.py`.

**Produces:**
- `retention.split(n: int) -> tuple[list[int], list[int]]` — notas em ordem de tempo; pares = ajuste, ímpares = teste.
- `retention.decide(baseline: list[float|None], candidates: dict[str, list[float|None]], fit, test) -> dict` — `{"best", "fit_db", "test_db", "baseline_test_db", "improvement_db", "noise_db", "accepted"}`. Ranking pela média no ajuste; melhora = média pareada (base − melhor) no teste; `noise_db = 2 · desvio-padrão(ddof=1)/√n` das diferenças pareadas; `accepted = improvement_db > noise_db`. Menos de 2 notas pareadas no teste → `accepted False`, `noise_db None`.
- `compressor.MIN_GAIN_REDUCTION_DB = 3.0`; `compressor.gain_reduction_db(dry, wet) -> float` (RMS do DI − RMS do compressor sozinho, ganho de saída 0, como na rodada 8); `compressor.is_tested(gr) -> bool`.
- `margin.BOOSTS_DB = (0, 12, 18)`; `margin.measure_margin(render, dis: list[Path], workdir) -> dict[int, {"peak_db", "saturated"}]`; `margin.margin_ok(m) -> bool`.

- [ ] **Step 1: testes que falham**
  - **EQ superajustado reprovado** (spec): base `[8]*8`; candidato "eq" = `5` nas notas de ajuste e `12` nas de teste → `best == "eq"`, `accepted False`.
  - melhora real e consistente: candidato 1 dB melhor em todas as 8 notas com ruído ±0,1 → `accepted True`.
  - melhora dentro do ruído: diferenças no teste `[+2, −1.5, +1.8, −1.9]` → `accepted False`.
  - `split(8) == ([0,2,4,6],[1,3,5,7])`.
  - compressor: wet = DI × 0,5 → redução ≈ 6,02 dB, testado; wet = DI × 0,8 → 1,9 dB, **não testado**.
  - margem: dublê que multiplica por 4 e corta em ±1 → com DI de pico 0,1, `+18 dB` satura e `margin_ok` False; dublê identidade com DI de pico 0,01 → True. Os DIs reforçados ficam só em `workdir`.
- [ ] **Step 2:** FAIL.
- [ ] **Step 3: implementação**

```python
# tone_builder/retention.py
"""No choice without retention: fit on half of the notes, decide on the other.
Gravity, 16/09: five EQ iterations improved the fit notes and worsened the test
notes every time (8.1 -> 8.3 ... 13.5)."""
from __future__ import annotations
import numpy as np

def split(n: int) -> tuple[list[int], list[int]]:
    return list(range(0, n, 2)), list(range(1, n, 2))

def _mean(v, idx):
    xs = [v[i] for i in idx if v[i] is not None]
    return float(np.mean(xs)) if xs else None

def decide(baseline, candidates, fit, test) -> dict:
    ranked = sorted((m, name) for name, v in candidates.items() if (m := _mean(v, fit)) is not None)
    if not ranked:
        return {"best": None, "accepted": False}
    fit_db, best = ranked[0]
    v = candidates[best]
    diffs = [baseline[i] - v[i] for i in test if baseline[i] is not None and v[i] is not None]
    out = {"best": best, "fit_db": fit_db, "test_db": _mean(v, test),
           "baseline_test_db": _mean(baseline, test), "improvement_db": None,
           "noise_db": None, "accepted": False}
    if len(diffs) < 2:
        return out
    d = np.array(diffs)
    out["improvement_db"] = float(d.mean())
    out["noise_db"] = float(2.0 * d.std(ddof=1) / np.sqrt(len(d)))
    out["accepted"] = out["improvement_db"] > out["noise_db"]
    return out
```

```python
# tone_builder/compressor.py
"""A compressor counts as tested only when it measurably compresses: on 16/09
thresholds of -40/-30/-20 dB removed 1.2/0.1/0.0 dB because the library DI is
quiet. Measured on the compressor alone, output gain 0."""
from __future__ import annotations
import numpy as np
from tone_builder.audio import rms_db

MIN_GAIN_REDUCTION_DB = 3.0

def gain_reduction_db(dry: np.ndarray, wet: np.ndarray) -> float:
    return rms_db(dry) - rms_db(wet)

def is_tested(gr_db: float) -> bool:
    return gr_db >= MIN_GAIN_REDUCTION_DB
```

```python
# tone_builder/margin.py
"""Delivery needs zero saturated samples with the DI boosted +12 and +18 dB
(a preset with 4 dB of headroom was heard crackling)."""
from __future__ import annotations
from pathlib import Path
import numpy as np
import soundfile as sf
from tone_analyzer.take import saturated_samples
from tone_builder.render import Renderer, RenderError

BOOSTS_DB = (0, 12, 18)

def measure_margin(render: Renderer, dis: list[Path], workdir: Path) -> dict:
    workdir.mkdir(parents=True, exist_ok=True)
    out = {}
    for boost in BOOSTS_DB:
        peak, sat = -120.0, 0
        for i, di in enumerate(dis):
            x, sr = sf.read(str(di), always_2d=False)
            src = workdir / f"di{i:02d}+{boost}.wav"
            sf.write(str(src), np.clip(x * 10 ** (boost / 20), -1, 1), sr, subtype="FLOAT")
            wet = workdir / f"wet{i:02d}+{boost}.wav"
            render(src, wet)
            if not wet.exists():
                raise RenderError(f"render wrote nothing: {wet}")
            y, _ = sf.read(str(wet), always_2d=False)
            peak = max(peak, float(20 * np.log10(np.abs(y).max() + 1e-12)))
            sat += saturated_samples(y)
        out[boost] = {"peak_db": peak, "saturated": sat}
    return out

def margin_ok(m: dict) -> bool:
    return all(m.get(b, {}).get("saturated", 1) == 0 for b in BOOSTS_DB)
```

- [ ] **Step 4:** PASS. **Step 5:** commit `feat(method): retention with measured noise, compressor gate, peak margin`.

### Task 4: pesquisa, bateria e relatório

**Files:** Create `tone_builder/research.py`, `tone_builder/battery.py`, `tone_builder/report.py`;
Test `tests/test_research.py`, `tests/test_battery.py`, `tests/test_report.py`.

**Produces:**
- `battery.CLASSES = ("single_drive", "stacked_drives", "boost", "compressor", "amp", "cab", "eq", "time_fx")`
- `research.load_research(path) -> dict`; `research.validate(r) -> list[str]` (erros); formato:
  `{"song", "part", "blocks": [{"class", "unit", "era": "record"|"tour", "sources": [url]}], "not_found": [{"class", "searched": [url|query]}]}`.
  Erros: bloco sem URL `http(s)://`; classe fora de `CLASSES`; bloco `era: tour` (não serve para disco).
- `research.sourced_units(r) -> dict[str, set[str]]` (classe → unidades com fonte, só `record`).
- `battery.Candidate` (dataclass): `name: str, klass: str, unit: str | None, render: Renderer, gain_reduction_db: float | None = None`
- `battery.run_battery(baseline: Renderer, candidates: list[Candidate], assignments: list[dict], research: dict, workdir: Path) -> dict[str, dict]` — por classe: `{"status": "measured"|"not_tested"|"no_candidate", "sourced": decide(...)|None, "unsourced_best": {"name","deviation"}|None, "reason": str|None}`. Compressor com `gain_reduction_db` None ou < 3 → excluído e, sem sobrar nenhum, `not_tested` com motivo. Candidato é "com fonte" quando `unit` ∈ `sourced_units(research)[klass]`. Classe sem candidato → `no_candidate`, motivo tirado de `research["not_found"]` quando houver, senão `None`.
- `report.build(battery: dict, margin: dict, baseline_deviation: float) -> dict` — `{"status": "pronto"|"parcial", "missing": [classe sem número nem motivo], "margin_ok": bool, ...}`. "pronto" exige: toda classe de `CLASSES` presente com `status == "measured"` ou `reason` não vazio, e `margin_ok`.
- `report.to_markdown(rep) -> str` — tabela por classe; a palavra "pronto" só aparece quando `status == "pronto"`.

- [ ] **Step 1: testes que falham**
  - pesquisa: URL ausente, `era: tour` e classe inventada geram um erro cada; exemplo válido não gera erro.
  - bateria com dublês de ganho de harmônico (numpy) sobre alvo sintético: candidato sem fonte melhor que o com fonte → `sourced.best` é o com fonte e `unsourced_best` mostra o outro (caso Fuzz Factory × Tube Screamer).
  - compressor com `gain_reduction_db=0.0` → classe `compressor` `not_tested` com motivo contendo "3 dB".
  - relatório: bateria sem a classe `cab` → `status == "parcial"`, `"cab" in missing`, `"pronto" not in to_markdown(...)`; tudo medido + margem ok → "pronto"; tudo medido + margem saturada → "parcial".
- [ ] **Step 2:** FAIL.
- [ ] **Step 3: implementação** — `run_battery`: mede o `baseline` uma vez (`render.measure`), `fit, test = retention.split(len(assignments))`, agrupa candidatos por classe, mede cada um (`RenderError` → candidato fora, anotado em `errors`), separa com/sem fonte, chama `retention.decide(baseline_per_note, {nome: per_note dos com fonte}, fit, test)`; `unsourced_best` = menor `deviation` dos sem fonte. `report.build` percorre `CLASSES`.
- [ ] **Step 4:** PASS. **Step 5:** commit `feat(method): research file, full block battery, pronto/parcial report`.

### Task 5: validador de verdade conhecida

**Files:** Create `tone_builder/validator.py`; Test `tests/test_validator.py`.

**Produces:** `validator.known_truth(notes: list[Path], dominance_db: float = -6.0, seed: int = 0) -> dict` —
`{"notes", "harmonics_per_note", "error_db", "false_positives"}`.

Como: cada nota da biblioteca (DI, pico normalizado a 0,35) é somada a um acompanhamento
**sintético** — ruído rosa + baixo (onda com 6 harmônicos, nota aleatória MIDI 28–40, `seed` fixo) —
escalado para a dominância pedida (RMS guitarra / RMS fundo). Na mistura e na guitarra sozinha
lê `harmonic_levels` no ataque conhecido; aceito = destaque ≥ 10 dB na mistura; falso positivo =
aceito na mistura e < 10 dB na guitarra sozinha; erro da nota = RMS de (mistura − guitarra) nos
aceitos, sem a média. Nota com < 5 aceitos fica fora.

- [ ] **Step 1: teste que falha** — `tests/test_validator.py::test_known_truth_on_library_at_minus_6_db`:
  24 notas (`pos5`, uma a cada 4, ordenadas), `dominance_db=-6` → `error_db <= 2.0`,
  `false_positives == 0`, `notes >= 12`. Pula se os WAVs forem ponteiros LFS. Mais um teste de
  sanidade: dominância +12 dá erro menor que −6.
- [ ] **Step 2:** FAIL (módulo não existe).
- [ ] **Step 3: implementação** (ruído rosa por filtro 1/√f no domínio da frequência).
- [ ] **Step 4:** PASS — **o número medido vai para o commit e para `docs/metodo.md`**. Se não
  passar, não afrouxar o critério: registrar o número e parar para investigar.
- [ ] **Step 5:** commit `feat(method): known-truth validator with synthetic accompaniment`.

### Task 6: CLI e documento do método

**Files:** Modify `tone_builder/cli.py`, `tests/test_cli.py`; Create `docs/metodo.md`; Modify `README.md`.

**Produces:**
- `tone-builder target <disc> <lead> --guitar G --position P [--root R] --out target.json` → escreve o alvo e imprime uma linha por nota (`name  m:ss.s  N harmonics`).
- `tone-builder validate [--guitar prs-silver-sky-se] [--position pos5] [--dominance -6 ...]` → tabela dominância × notas × harmônicos/nota × erro × falsos positivos; sai 1 se −6 dB falhar o critério.
- `docs/metodo.md`: procedimento 0–8, tabela "a biblioteca é a peça mais importante", tabela "nunca
  fazer", "pesquisa é o passo 0", números das rodadas 7–8 — só a parte genérica, sem o que é do
  rig do jpfaria; aponta para cada módulo que implementa cada passo.

- [ ] **Step 1:** testes de CLI que falham (alvo sintético em `tmp_path`; `validate` com biblioteca real, pula sem LFS).
- [ ] **Step 2:** FAIL. **Step 3:** implementar. **Step 4:** PASS e CI verde.
- [ ] **Step 5:** commit `feat(cli): target and validate; docs: the method`; push; em `music-setup/docs/metodo-timbre.md`, apontar para `tone-builder/docs/metodo.md` como fonte do procedimento.

### Task 7 (fora desta etapa): skill do plugin

A skill `tone-builder` só entra junto com o primeiro aparelho (etapa 4): sem render, o fluxo da
skill para no passo 1 e não tem como ser testado de ponta a ponta com subagente (RED/GREEN).
