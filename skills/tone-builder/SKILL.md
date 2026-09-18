---
name: tone-builder
description: Use when the user wants the tone of a specific song, solo or artist recreated on OpenRig, a Hotone Ampero II or an M-VAVE MK-300 — "cria o timbre da Gravity na MK-300", "timbre do solo de X no OpenRig e na Ampero", "timbra essa música em todas as pedaleiras" — or wants a guitar's note library recorded or checked. The openrig, ampero2 and mvave tone-builder skills hand this job here.
---

# tone-builder

The method lives in code: `${CLAUDE_PLUGIN_ROOT}/docs/metodo.md` says why each step exists.
The number decides between researched candidates; the user's ear never validates a number. The ear only supplies what the number cannot measure (time effects), and the research says so in writing.

```bash
"${CLAUDE_PLUGIN_ROOT}/bootstrap.sh"; TB="${CLAUDE_PLUGIN_ROOT}/.venv/bin/tone-builder"; TA="${CLAUDE_PLUGIN_ROOT}/.venv/bin/tone-analyzer"
```

## Collect — ask only what no file answers

Who stores what: the song's AUDIO and its analysis are tone-analyzer's (`~/.tone-analyzer/tones/<artist>-<song>/`: full track + separated guitar). `~/.tone-builder/<song>/` holds only what compares or decides: `research.yaml`, builds, device results, reports — never audio, never a `refs/` folder. `~/.openrig/` belongs to the OpenRig app: only its `presets/` is touched — to check a name is free and to save the OpenRig preset. `<song>` = `<song>-<artist>` slug, e.g. `gravity-john-mayer`.

| need | where to look first | missing → |
|---|---|---|
| record audio (full mix) | `$TA tones find "<song>"` — in the library → pass only `--artist --song`, no `--disc` | handed over → pass its path as `--disc`, where it is; `build` has tone-analyzer separate, analyze and store it (~3 min). m4a/AAC → `ffmpeg -ar 48000` to WAV first. None → ask; without it nothing is measured: stop |
| separated guitar track | the same library entry (`<role>/reference.*`) | never ask and never separate by hand: `build` does it through tone-analyzer. The user handed one over → pass it as `--lead` together with `--disc`: tone-analyzer stores it as that role's reference instead of separating |
| guitar + selector position | `$TB library list` — one recorded → use it | ask which; offer `library record` |
| devices | the request | ask |
| preset name / slot | — never ask | `DIG - <Artist> - <Song> (<part>)`; if that name already exists (`~/.openrig/presets/`, `ampero2 patches`, `mvave presets`) append ` tb2`, ` tb3`…; next empty slot; never overwrite |

## Flow

1. **Research (step 0)** → `research.yaml` (format: `exemplos/gravity-john-mayer/research.yaml`).
   Open every page; quote it. A search summary is not a source. Record rig ≠ tour rig.
   Every class `single_drive stacked_drives boost compressor amp cab eq time_fx` is either a block
   or a `not_found` entry with what was searched — or the report comes out `parcial`.
   No page names the rig → ask the user to ask the player; the answer is a source:
   `statement: {who, date, channel, quote}` on the block, instead of `sources`.
   The source names a class but no unit ("compressor") → `unit: any`: every model of that class
   competes (never for `time_fx`). A delay/reverb the source names only by class → the block's `unit` is the device unit the
   user approved by ear, its amounts go in `params: {...}`, and a comment says who set them and
   when; the number cannot see time effects. A brand alone ("Fender") is a unit: it opens every
   capture of that brand.
   A named unit with hundreds of captures and a tone the user calls clean or dirty →
   `$TB linearity --device openrig --unit "<unit>" …` ranks its captures by measured cleanliness.
2. `$TB build --device openrig|ampero2|mvave --artist … --song … [--role guitars] [--disc … [--lead …]] --research … --guitar … --position …
   --name … --out ~/.tone-builder/<song>/<device>-v<N> [--plugins-root …] [--work-patch …]` — minutes to hours: run it
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
| Ampero II | `--work-patch` = an empty slot; `commands` via `ampero2` (they end with `input-source input`), `ampero2 save DEST NAME` | no MIDI port → report "not connected", do the others |

## Never

| don't | because |
|---|---|
| `tone-analyzer compare` / `eq-match` / `proximity_pct` | invalid on single notes (bands 74–84 dB down between harmonics) |
| say "pronto" when `report.md` says `parcial` | the word comes from the data |
| add a block no source names, or drop a cited one | the research decides blocks; the number decides settings |
| stop to ask "sigo?" between steps or devices | the request already covers it |
| overwrite a named preset or slot | always a new one |
