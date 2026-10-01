---
tags: [tone-builder, learnings]
created: 2026-09-17
updated: 2026-09-18
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

## 2026-09-18 — One separated guitar track can hold two guitars; a chord-only part gives no notes

- **Gotcha / invariant:** demucs puts every guitar in one stem, so rhythm and lead share the same `reference`. On *Even Flow* the build found only two isolated notes in the whole song, one inside the lead solo, and judged the rhythm chain against the lead guitar. The rhythm part is all chords and ghost notes: 0 isolated notes in 0:00–0:30 and none before the solo.
- **Why it matters:** a `parcial` result with a huge deviation may mean "measured against the wrong guitar", not "bad chain". Check where the measured notes fall in time before trusting the number.
- **Applies to:** songs with two guitarists → restrict the target with `--from/--to` to a section where only the wanted part plays; chord parts need the chord target.

## 2026-09-18 — Chord false notes on the real library are open strings ringing in the samples

- **Gotcha / invariant:** measured after `validate --chords` failed: open strings ring sympathetically within 30 dB of the played fundamental in 19 of 96 library notes, and `salience_set` returns an extra note on 29 of 96 notes played alone — the same open pitches it reported as false notes in chords. A raw prominence gate alone is misleading here (bass bands are near-silent in DI takes, so noise reads as 26–42 dB prominence); an amplitude floor relative to the played note is needed.
- **Why it matters:** the detector is not inventing those notes; the known truth assumes a sample contains only the note played.
- **Applies to:** chord known truth built from single-note samples — either count a note already present in a component sample as true, or record samples with open strings muted.

## 2026-09-18 — Who stores what: analyses are tone-analyzer's, not tone-builder's and not the agent's

- **Gotcha / invariant:** the analysis of ONE audio (fingerprint, harmonics, spectrograms, PDF) is stored by **tone-analyzer**, in its song library: `tone-analyzer tones add --artist … --song … --role … --analysis OUT --reference-kind … --reference … --track …` → `~/.tone-analyzer/tones/<artist>-<song>/`. Look there first with `tones find` so nobody analyzes a song twice. The song's AUDIO is tone-analyzer's too: the full track (`track.<ext>`) and the separated guitar (`<role>/reference.<ext>`) live in that same library entry — there is no `refs/` under `~/.tone-builder/` (jpfaria, 18/09: "refs é do tone analyzer"). `~/.tone-builder/<song>/` keeps only what compares or decides: research, builds, device results, reports.
- **Why it matters:** on 17/09 the agent ran `analyze` with `--out-dir` inside `~/.tone-builder/` and left other results in its session scratchpad; on 18/09 it then wrote here that tone-builder stores analyses. Both wrong (jpfaria, 18/09: "quem guarda a análise é o tone-analyzer"). Same boundary as the spec: information about one audio is tone-analyzer's.
- **Applies to:** every `tone-analyzer analyze/harmonics` run made on behalf of a build; never the scratchpad, never `~/.tone-builder/`.

## 2026-09-18 — Installing tone-analyzer downloads 2.3 GB of song audio unless LFS is skipped

- **Gotcha / invariant:** tone-analyzer's repo keeps its `tones/` library in Git LFS. `pip install git+…/tone-analyzer` clones it and the LFS smudge pulls every song (2.3 GB) into a temp dir — once per install, and again for every dependency that names it. On 18/09 that filled the disk ("no space left on device") and the install failed as "Failed to build 'tone-analyzer'", hiding the cause.
- **Why it matters:** an install needs the code, never the audio. `bootstrap.sh` now exports `GIT_LFS_SKIP_SMUDGE=1` (install: 51 s).
- **Applies to:** any `pip install` of tone-analyzer, mvave, ampero2 or tone-builder outside `bootstrap.sh` — set `GIT_LFS_SKIP_SMUDGE=1` first.

## 2026-09-18 — OpenRig: a new rig slot is not guaranteed; check the active preset before writing

- **Gotcha / invariant:** `apply_rig_nav {Preset: -1}` returns `ChainReloaded` even when no new slot becomes active (seen right after the app restarted and the MCP reconnected). `rename_rig_preset` and `load_chain_preset` then act on whatever slot IS active — here they overwrote "Even Flow (base) tb2" with the solo chain, while `save_chain_preset` still wrote a correct `.yaml`, so `verify` on the file passed and hid it.
- **Why it matters:** `verify` reads `~/.openrig/presets/<name>.yaml`, not the rig slot the user plays; the user opened the slot and found no TS9.
- **Applies to:** every OpenRig write. After the add, read `openrig://chains/<chain>/presets` and require `active_preset` to be the new `New Preset N` before rename/load; after saving, re-read `~/.openrig/project.yaml` and check each touched slot's blocks, not only the preset file.

- **MK-300 (18/09/2026, *Alive*):** a pedaleira não repete o mesmo re-amp — 0,2 dB entre passadas
  idênticas sem modulação, até 0,5 dB com Univibe; por isso o `verify` renderiza 3 vezes e usa 3σ.
  Uma chamada `mvave` travou 1h40 em `rtmidi close_port` com o comando já enviado: o `Runner`
  mata e repete toda chamada de aparelho que passa de 120 s.

## 2026-09-18 — A long OpenRig build dies when the app is reinstalled under it: render from a snapshot

- **Gotcha / invariant:** `openrig-render` and the plugin catalog live inside `/Applications/OpenRig.app`. While OpenRig itself is being developed the app is reinstalled several times a day; each reinstall removes the binary (17:47: `FileNotFoundError`) or its `libnam_wrapper.dylib` (19:37: `dyld: library not loaded`) for a few seconds and a 2-hour build exits.
- **Why it matters:** two builds lost on 18/09. Measurements are now cached per candidate (`measure.json`), so a rerun in the same `--out` resumes; and the renderer waits up to 2 minutes for a missing binary. Neither helps against a half-copied app.
- **Applies to:** any OpenRig build longer than a few minutes → `cp -R /Applications/OpenRig.app ~/.tone-builder/_runtime/` and run with `OPENRIG_RENDER=~/.tone-builder/_runtime/OpenRig.app/Contents/MacOS/openrig-render --plugins-root ~/.tone-builder/_runtime/OpenRig.app/Contents/Resources/plugins`. Also detach it (`nohup … & disown`): a background task dies with the Claude session.

## 2026-09-18 — Chord detection fails on the real library; the chord level reading passes

- **Gotcha / invariant:** `validate --chords` on prs-silver-sky-se pos5 (78 chords built from real library notes, strings spread 0–30 ms, residue 20 dB under): salience finds the right octave-reduced set in **61.5 %** with **31 false notes**, at every dominance (detection runs on the separated track, not the mix). The level reading passes: error 1.59 dB at −6 dB (0.77 at +6), zero false positives. 26 of the 31 false notes are open-string pitches (D3 ×8, A2 ×6, B3 ×6, G3 ×4, E2 ×2): the likely cause is sympathetic ringing of open strings in the real samples, which synthetic tones never have (not yet measured on the samples themselves). The synthetic tests in tone-analyzer passed; the real library is what showed it.
- **Also measured, in tone-analyzer (task 2b, synthetic strums):** staggered strums (0–30 ms) are found 59/60 exact with 0 false notes after the chord-onset fix; a second strum over a chord still ringing is found ~65 % of the time, and about half of those (34 of 65) read the wrong set — the 0.6 s window mixes the chord still ringing.
- **Why it matters:** a chord target with an extra open-string note compares against a DI that lacks it; `build` still runs, but chord deviations are not yet trustworthy. The criterion (≥ 90 %, 0 false notes, ≤ 2 dB) was not loosened; `test_chord_known_truth_on_the_shipped_library` is `xfail(strict=True)` and will flip when it passes. basic-pitch was not measured (needs pipx, not installed here).
- **Applies to:** any change to `detect_chords` or its thresholds → rerun `tone-builder validate --chords --guitar prs-silver-sky-se --position pos5`; real legato strumming (Even Flow's rhythm part) hits the "strum over ringing chord" weakness.

## Gravador de corda: captador da ponte derrubava notas (19/09/2026)

Na posição 1 da PRS cada tomada perdia duas ou três notas diferentes, sem erro de execução. Duas causas,
achadas na tomada bruta (`_takes/c<corda>.wav`, que o gravador agora guarda):

- A autocorrelação escorrega para um sub-harmônico da nota: uma oitava abaixo em 6 de 21 quadros na
  casa 2 da 3ª corda, em 17 de 21 na casa 11 da 1ª, e f/3 depois f/2 na casa 15 da 1ª. O `detect_notes`
  descartava a nota ou lhe dava outro nome. O gravador agora nomeia a nota ele mesmo (`note_spans`):
  um quadro que lê 12, 19 ou 24 semitons abaixo de uma nota esperada da corda conta para ela, e leitura
  direta desempata (um Sol de verdade não vira o Sol da oitava de cima). O `pitch_autocorr` do
  tone-analyzer não foi tocado.
- `snr_db` vinha vazio quando o corte começava a menos de 10 ms do ataque. O ruído agora é medido num
  corte com 150 ms de pré-rolagem; a nota salva continua com 20 ms.

As mesmas tomadas passaram de 10 e 13 aceitas em 16 para 16 em 16 (`tests/data/c3-` e `c1-bridge-take.flac`).
- O detector de ataques do tone-analyzer perdia o ataque que sobe em dois blocos (6ª corda, casas 1 e 11:
  envelope 0,015 → 0,197 → 0,247). Corrigido lá (`note_onsets`), commit d06464e. Com as três correções as
  quatro tomadas brutas guardadas dão 16 notas em 16.

## Gravador de corda escuta em vez de contar tempo (19/09/2026)

Pedido do João: "não tinha que ser por tempo e sim por detecção". `library record` agora escuta
(`recorder.listen_string`): nomeia e julga cada nota quando ela fecha, avisa no terminal, termina sozinho
quando as 16 notas da corda entraram (ou após 12 s sem ataque) e aceita a nota errada tocada de novo na
mesma sessão. Invariante medida: uma nota só fecha pelo tempo (2 s) se não houver um ataque recente demais
para ser nomeado dentro dela; sem isso a janela avançava por cima do ataque seguinte e perdia 1 a 4 notas
por corda. As 10 tomadas brutas guardadas, repassadas em blocos de 0,5 s, dão 16 em 16.
- Primeira sessão real por detecção (Paul's Guitar, braço): nota tocada por cima do som da anterior não era
  medida (os 150 ms antes do ataque continham a nota anterior, o início da tomada caía nela e não saía nem
  altura nem ruído) — o corte curto de 20 ms decide nesse caso; e um ruído de manuseio no fim, nomeado como
  nota já aceita, rebaixava a nota aceita — uma tomada pior nunca substitui a aceita. 94 de 96 na primeira
  passada; as duas que faltaram não foram tocadas de forma legível (corda solta colada no bipe, casa 15 pulada).
- Corda errada (19/09, ponte com split): a 3ª foi tocada na vez da 4ª e o erro se propagou por três cordas;
  11 das 16 notas de uma corda existem na vizinha, então foram salvas com o nome da corda errada. Só a nota
  que a corda não tem denuncia: duas notas fora da faixa da corda (até 5 semitons abaixo ou acima) → a tomada
  inteira é desfeita, o áudio vai para `_takes/c<n>-wrong-string.wav` e a mesma corda é pedida de novo.
  22 tomadas reais sem alarme falso; as três tomadas erradas foram pegas.
- Entrada muda: o gravador avisa em 5 s quando o canal está em silêncio (pico ≤ −90 dBFS) e encerra, em vez
  de esperar corda por corda. Antes de culpar o gravador, medir TODAS as entradas da interface: a guitarra
  aqui alterna entre a In 1 e os canais 16/17 (DI pelo ADA), e pela DI chegou a −1 dBFS, quase clipando.

## 2026-09-19 — Piso de 4 dB: duas tomadas da mesma nota já diferem tanto

- **Gotcha / invariant:** a variação de palhetada entre duas tomadas da mesma nota, mesma guitarra e mesma
  posição, dá 4,3 dB de erro na forma do espectro (3,1–4,0 nos harmônicos 1–6). Nenhuma comparação de timbre
  feita com uma tomada por nota distingue menos que isso.
- **Why it matters:** diferença de desvio menor que ~4 dB entre dois candidatos não é diferença. No *Alive*
  a Paul's na ponte (5,1–5,7 dB) e a Silver Sky no braço (4,7–5,8 dB) ficaram empatadas por esse piso, e quem
  decidiu foi a pesquisa, não o número. Pela mesma régua, inferir uma posição de captador a partir das outras
  duas erra 8,4 dB e não serve: posição que se quer usar, grava-se.
- **Applies to:** toda leitura de desvio no relatório e toda escolha entre candidatos. Medição e método em
  [pesquisa/2026-09-19-inferir-posicao-de-captador.md](pesquisa/2026-09-19-inferir-posicao-de-captador.md).

## 2026-09-19 — A pesquisa é por aparelho: nome fora do catálogo mata o build no começo

- **Gotcha / invariant:** o mesmo `research.yaml` não serve para dois aparelhos. Quatro builds de Pearl Jam
  morreram na largada porque a pesquisa dizia `TS-9` (o catálogo tem `TS9`) e citava amps que a MK-300 não
  tem. Cada aparelho ganha a sua cópia (`research-mvave.yaml`, `research-solo-mvave.yaml`), com o nome do
  catálogo dele e o que não existe marcado como ausente.
- **Why it matters:** o build gasta horas e a falha aparece nos primeiros segundos — conferir os nomes nos
  dois catálogos antes de enfileirar. Uma unidade pesquisada que não existe no catálogo também deixava o
  relatório em `parcial` sem motivo nas classes `compressor` e `time_fx` (corrigido em 19/09).
- **Applies to:** todo build que reaproveita pesquisa feita para outro aparelho.
