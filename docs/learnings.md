---
tags: [tone-builder, learnings]
created: 2026-09-17
updated: 2026-09-17
source: claude-code-sessions
---

# tone-builder — Learnings

Method rules live in [metodo.md](metodo.md); effect detection in [pesquisa/2026-09-17-deteccao-de-efeitos.md](pesquisa/2026-09-17-deteccao-de-efeitos.md).

## 2026-09-17 — Plugin cache goes stale while the version stays the same

- **Gotcha / invariant:** `claude plugin update` does not pick up repo changes while `plugin.json` keeps the same version (0.2.0); only uninstall + install refreshed it. The stale cache still pointed at `~/.openrig/evaluations` and its venv had a tone-analyzer without `separate`.
- **Why it matters:** the agent follows the cached SKILL.md, not the working tree.
- **Applies to:** every SKILL.md / dependency change → bump `plugin.json` version.

## 2026-09-17 — `build` invocation traps

- **Gotcha / invariant:** `--plugins-root` is not discovered automatically (catalog: `~/Projetos/github.com/jpfaria/OpenRig-plugins/plugins/source`, or `/Applications/OpenRig.app/Contents/Resources/plugins`); the position is `pos5`, not `5`; the audio reader does not open m4a (convert with `ffmpeg -ar 48000` to WAV); `research.yaml` `unit` names must match catalog names (e.g. `Marshall Plexi 50W`, `Marshall JCM 800`, `Fender Bassman`), and a unit with no model gets `absent_from_catalog: true`.
- **Why it matters:** each one made the Even Flow build fail or drop a block.
- **Applies to:** `tone-builder build`, `research.yaml`.

## 2026-09-17 — Measuring how clean an amp capture is

- **Gotcha / invariant:** play the same DI note at two levels 20 dB apart; in a linear system every harmonic rises exactly 20 dB, and the deviation is the capture's distortion, independent of EQ. Over 106 OpenRig captures: Fender Twin normal ranked 4th, AC30 normal 40th, AC30 top boost (volume 3) 58th — matching the user's ear ("there's distortion that isn't in the original").
- **Why it matters:** "volume 3 on a clean-ish channel" is not clean; pick clean amps by this ranking.
- **Applies to:** amp candidate choice for clean tones.

## 2026-09-17 — OpenRig block edits: defaults and silent resets

- **Gotcha / invariant:** OpenRig amp blocks come with a noise gate on at −30.5 dB, which cuts light picking (user had to attack hard); `replace_block_model` resets the block's EQ; reverting a channel via parameter option landed on top boost instead of normal. Re-read `~/.openrig/project.yaml` after `save_project` to confirm what was stored.
- **Applies to:** chain edits through the OpenRig MCP.

## 2026-09-18 — Who stores what: analyses are tone-analyzer's, not tone-builder's and not the agent's

- **Gotcha / invariant:** the analysis of ONE audio (fingerprint, harmonics, spectrograms, PDF) is stored by **tone-analyzer**, in its song library: `tone-analyzer tones add --artist … --song … --role … --analysis OUT --reference-kind … --reference … --track …` → `~/.tone-analyzer/tones/<artist>-<song>/`. Look there first with `tones find` so nobody analyzes a song twice. The song's AUDIO is tone-analyzer's too: the full track (`track.<ext>`) and the separated guitar (`<role>/reference.<ext>`) live in that same library entry — there is no `refs/` under `~/.tone-builder/` (jpfaria, 18/09: "refs é do tone analyzer"). `~/.tone-builder/<song>/` keeps only what compares or decides: research, builds, device results, reports.
- **Why it matters:** on 17/09 the agent ran `analyze` with `--out-dir` inside `~/.tone-builder/` and left other results in its session scratchpad; on 18/09 it then wrote here that tone-builder stores analyses. Both wrong (jpfaria, 18/09: "quem guarda a análise é o tone-analyzer"). Same boundary as the spec: information about one audio is tone-analyzer's.
- **Applies to:** every `tone-analyzer analyze/harmonics` run made on behalf of a build; never the scratchpad, never `~/.tone-builder/`.
