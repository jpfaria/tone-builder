---
name: tone-builder
description: Use when the user wants the tone of a specific song, solo or artist recreated on OpenRig, a Hotone Ampero II or an M-VAVE MK-300 — "cria o timbre da Gravity na MK-300", "timbre do solo de X no OpenRig e na Ampero", "timbra essa música em todas as pedaleiras" — or wants a guitar's note library recorded or checked. The openrig, ampero2 and mvave tone-builder skills hand this job here.
---

# tone-builder

The method lives in code: `${CLAUDE_PLUGIN_ROOT}/docs/metodo.md` says why each step exists.
The number decides between researched candidates; the user's ear never validates.

```bash
"${CLAUDE_PLUGIN_ROOT}/bootstrap.sh"; TB="${CLAUDE_PLUGIN_ROOT}/.venv/bin/tone-builder"
```

## Collect — ask only what no file answers

| need | where to look first | missing → |
|---|---|---|
| record audio (full mix) | `~/.openrig/evaluations/<song>/refs/original.*` | ask; without it nothing is measured: stop |
| separated guitar track | `refs/lead.wav`, `refs/guitar*.wav` | ask |
| guitar + selector position | `$TB library list` — one recorded → use it | ask which; offer `library record` |
| devices | the request | ask |
| preset name / slot | — never ask | `DIG - <Artist> - <Song> (<part>)`; if that name already exists (`~/.openrig/presets/`, `ampero2 patches`, `mvave presets`) append ` tb2`, ` tb3`…; next empty slot; never overwrite |

## Flow

1. **Research (step 0)** → `research.yaml` (format: `exemplos/gravity-john-mayer/research.yaml`).
   Open every page; quote it. A search summary is not a source. Record rig ≠ tour rig.
   Every class `single_drive stacked_drives boost compressor amp cab eq time_fx` is either a block
   or a `not_found` entry with what was searched — or the report comes out `parcial`.
2. `$TB build --device openrig|ampero2|mvave --disc … --lead … --research … --guitar … --position …
   --name … --out <song>/tb/<device>-v<N> [--plugins-root …] [--reamp-patch …]` — minutes to hours: run it
   in the background, one device at a time.
   - exit 3 lists units with no catalog model: check the catalog; if truly absent set
     `absent_from_catalog: true` on that block (it becomes the class reason). Never type a model id.
3. Read `report.md`. Relay **status as written** (`pronto`/`parcial`), the chain, the test-note
   deviation, `unsourced_best`, the margin and every class reason.
4. Write to the device as a **new** preset/slot, read it back from the device/disk, then
   `$TB verify --device … --build-dir … --saved <preset yaml | patch | slot>` — must print `"match": true`.

## Devices

| device | writes with | blocked when |
|---|---|---|
| OpenRig | MCP: new preset, `save`, then reread `~/.openrig/presets/<name>.yaml`; `--saved` = that file | — |
| MK-300 | `preset.yaml` `commands` via `mvave`, then `mvave save N NAME` | no MIDI port → report "not connected", do the other devices |
| Ampero II | `commands` via `ampero2`, `ampero2 save DEST NAME` | no patch with input SOURCE = USB OUT 3/4 (touchscreen only) → report it, do the others |

## Never

| don't | because |
|---|---|
| `tone-analyzer compare` / `eq-match` / `proximity_pct` | invalid on single notes (bands 74–84 dB down between harmonics) |
| say "pronto" when `report.md` says `parcial` | the word comes from the data |
| add a block no source names, or drop a cited one | the research decides blocks; the number decides settings |
| stop to ask "sigo?" between steps or devices | the request already covers it |
| overwrite a named preset or slot | always a new one |
