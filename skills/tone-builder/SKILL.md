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
| real chords for the library | — | `$TB library record-chord <guitar> <position> <c6-40_c5-47_c4-52> --device … --channel …` (string-midi per note; 3 strums; `library check` confirms the set) |
| devices | the request | ask |
| preset name / slot | — never ask | `DIG - <Artist> - <Song> (<part>)`; if that name already exists (`~/.openrig/presets/`, `ampero2 patches`, `mvave presets`) append ` tb2`, ` tb3`…; next empty slot; never overwrite |

## Flow

1. **Research (step 0)** → the **`tone-builder:gear-researcher`** agent writes
   `research.yaml` (format: `exemplos/gravity-john-mayer/research.yaml`), then the
   **`tone-builder:research-auditor`** agent verifies it. Dispatch the researcher with `song`,
   `artist`, `part` and the `research_path`; dispatch the auditor with that path; on `VERDICT: FAIL`
   send its report back to the researcher as `audit_report` and audit again. Never build past a FAIL,
   and never research the rig yourself in this conversation — the pages belong in their context, the
   verdict in yours. Relay the auditor's uncovered classes and its `NOTE:` lines to the user.
   Two parts (rhythm and solo) → two researchers at once, one file each.
   What only you can supply, in the dispatch prompt:
   - No page names the rig → ask the user to ask the player; the answer ships as
     `statement: {who, date, channel, quote}` instead of `sources`.
   - A delay or reverb named only by class → the `unit` is the device unit the user approved by ear
     and its amounts go in `params: {...}`; pass them as `ear_params`. The number cannot see time
     effects, so without them that class stays `not_found`.
   - A named unit with hundreds of captures and a tone the user calls clean or dirty →
     `$TB linearity --device openrig --unit "<unit>" …` ranks its captures by measured cleanliness.
2. `$TB build --device openrig|ampero2|mvave --artist … --song … [--role guitars] [--disc … [--lead …]] --research … --guitar … --position …
   --name … --out ~/.tone-builder/<song>/<device>-v<N> [--plugins-root …] [--work-patch …]` — minutes to hours: run it
   in the background, one device at a time.
   - Two guitars in the song → `--role rhythm|solo` (a role stored in the song's tone-analyzer entry,
     its own separated stem); the part lives in one stretch → `--from M:SS --to M:SS` (only attacks
     inside it are targeted).
   - Chords are measured automatically (2+ notes at one attack; DI = every playable voicing of the
     library, plus recorded chords, chosen by measurement). `--no-chords` = single notes only;
     `--chord-detector salience|basic-pitch` (default salience).
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
