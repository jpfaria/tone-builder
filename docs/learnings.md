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

## Primeiro timbre medido na MK-300 (Gravity, 19/09/2026)

`build --device mvave` de ponta a ponta, com `verify` na preset gravada: 9,21 dB esperados contra
9,26 dB medidos (três repetições, desvio-padrão 0,014 dB). Cadeia final: só o `61DUMBLE_FG`, com
todos os knobs em 50 e o VOL em 70. O drive (`1BLUES_OD`) e o EQ ajustado foram recusados pela
retenção. No OpenRig o mesmo método e a mesma pesquisa deram 7,76 dB.

Três coisas que o primeiro build errou, e que a correção mede:

- **Knob não escrito ficava com o valor da preset carregada.** O `apply_commands` só mandava os
  knobs escolhidos; o resto vinha do buffer (a rodada de 19/09 mediu o Dumble com `Gain=80
  Level=60 Middle=60` herdados da "DIG Alive Base"). Agora todo knob do bloco é escrito: o valor
  escolhido, o default do catálogo, ou o meio da faixa quando o pedal não informa default (`?`).
  Sem isso o número não é reprodutível nem transferível para outra preset.
- **A saída estourava.** Com o nível herdado, o retorno USB passava de 0 dBFS já com o DI sem
  ganho (26 amostras saturadas em +0 dB, 89 190 em +18 dB). O build agora baixa o último bloco da
  cadeia (`output_levels`, o VOL na MK-300) até a margem de +18 dB passar — nível não é timbre. Com
  VOL 70: pico −18,1 / −6,3 / −1,2 dBFS em +0/+12/+18, zero amostras saturadas.
- **Classe sem número e sem motivo.** Os drives empilhados falhavam em todos os pares ("a MK-300
  tem um bloco DS") e a classe saía vazia, o que derruba o relatório para `parcial` sem dizer
  por quê. Quando nenhum par renderiza, o erro do aparelho vira o motivo da classe.

Nome de unidade é por aparelho: `Dumble ODS John Mayer` e `Marshall BluesBreaker` resolvem no
OpenRig e não na MK-300 (0,25 e 0,38, abaixo do corte de 0,5). A pesquisa foi copiada para
`research-mvave.yaml` com `Dumble` e `Bluesbreaker` — mesmas fontes, nomes que o catálogo dela
reconhece. O `Bluesbreaker` só passou a resolver depois de corrigir a `mvave`: um apelido escrito
com `_` (`blues_od`) nunca batia com o nome do modelo (`1BLUES_OD`).

O nome da preset na MK-300 tem 20 caracteres: `DIG - John Mayer - Gravity (solo)` não cabe, foi
gravada como `DIG Gravity Solo` na slot 104.

## Margem: DI quente não pode ser reforçado além do fundo de escala (20/09/2026)

O teste de margem reforçava o DI em +12/+18 dB com `np.clip`. Com humbucker (DI a −6,6 dBFS) o DI já saía
ceifado ANTES do aparelho; os topos planos voltavam como "saturação" em qualquer nível de saída, o build baixava
o VOL da MK-300 até 50 (−61 dBFS de retorno) e morria com "no signal". O reforço agora para em −0,5 dBFS.

- **MK-300 V73 e NAM (19-20/09/2026, *Sweet Child O' Mine*):** o NAM escolhido na pedaleira **não**
  aparece na imagem do preset (448 bytes): entre um preset com NAM e um vazio só mudam nome, `AMP
  enabled` e um knob. Carregar o preset por MIDI (`mvave load`) perde o NAM — medido: re-amp a
  13,9 dB do NAM do OpenRig carregando por MIDI, contra 5,1 dB com o preset escolhido no pé.
  Escrever `model AMP ...` também o derruba. Por isso `--keep-block AMP`: o bloco não é escrito nem
  medido, e a classe sai no relatório como `fixed_on_device`.
  Os índices de AMP acima do catálogo (120+) não são slots de NAM: entregam o DI seco atenuado
  (−35 dBFS, 6,3 dB do DI puro, contra −6,2 dBFS de um amp de fábrica).
- **Escolha do DI repetia re-amp (28/09/2026, *Welcome to Paradise*, Ampero II):** `choose_dis`
  renderizava cada digitação candidata de novo para cada ataque do alvo. No OpenRig isso só custa
  CPU; na pedaleira cada render é um re-amp real, e um riff com dezenas de Eb5 virou o mesmo som em
  loop por meia hora ("vc ta enviando o mesmo som sempre"). Agora cada DI passa pela cadeia uma vez
  e é medido contra todos os ataques que o oferecem.
- **Cifra antes de medir (28/09/2026, *Welcome to Paradise*):** o João: "medir acorde por acorde… vc tem
  que baixar a cifra da música, encontrar os acordes; se não achar, pedir alguns acordes para mim. Se não
  fica impossível". Do Cifra Club saíram 7 power chords; o alvo caiu de 52 ataques × 441 voicings para
  8 ataques com a digitação da tab. O Cifra Club só entrega a tab com JS (curl volta 424 bytes): ler no
  browser (`self.__next_f` traz o texto da tab).
- **Pedaleira: modelo fixado na pesquisa, nada de chute por nome (28/09/2026, *Welcome to Paradise*):** o
  `resolve` da Ampero aceitou Checkboard, Greenback e EVM para "Marshall 4x12 V30" só por serem "Marshall 4x12"
  (o João: "não fica testando com coisa nada a ver, não podemos ficar chutando"). Quando a pedaleira não tem o
  modelo, sobe o IR/NAM da unidade pesquisada e o bloco da pesquisa ganha `ampero2: ["CAB:User IR 3"]` —
  esses são os únicos candidatos. E Plexi não tem knob "Gain": o ganho é o `Volume` (há `Output` depois).
- **Ampero: editar só na cena 1 (28/09/2026, *Welcome to Paradise*):** `param`/`model`/`input-source` com a
  pedaleira em outra cena derrubam o firmware v1.7.0 ("Record the error and restart: SceneNum == SCENE_1",
  PresetInterface.c:2279) — aconteceu duas vezes, e o João teve de reiniciar. O `reamp` escreve o input source,
  então também conta. Para medir o nível de cada cena: ficar na cena 1 e ligar nela, uma por vez, a
  variação de cada cena (`powers 1 …`); só no fim gravar os `powers` de todas. A `ampero2` agora recusa
  edição fora da cena 1 (hotone-ampero-2 2519fa1). O app editor Ampero II aberto também disputa o MIDI.
- **"Pronto" com 6,5 dB e o som nada a ver (28/09/2026, *Welcome to Paradise*, Ampero):** o riff da cifra
  pela A26-4 contra a guitarra separada, mesmo RMS, por oitava: faltavam ~9 dB em 1–4 kHz (Ampero pico em
  250 Hz; disco pico em 2 kHz) e o crest era 7,4 dB contra 10,2 (ganho demais — só a captura `gain_max`
  do NAM Dookie tinha subido). O desvio por harmônico em 8 ataques não viu; o EQ foi rejeitado pela
  retenção. Agora a skill exige a checagem do riff antes de entregar. O João: "pq vc não fez isso desde o início?"
- **Riff check resolveu o que o build não viu (28/09/2026, *Welcome to Paradise*, Ampero A28-1):** EQ ajustado
  pelo espectro do riff inteiro (8 bandas, 3 iterações de −0,8 × diferença) levou a pior banda 250 Hz–4 kHz de
  4,6 → 1,9 dB (SLP+ Volume 80 + IR V30 ev_mix) e 4,7 → 2,5 dB (NAM Dookie max). O IR 1960BV V30 SM57 ficou
  *mais escuro* que o ev_mix (−5,7 dB em 4 kHz). A Ampero recusa IR curto (734 amostras: ack com status 00,
  nada no inventário): completar com silêncio até 200 ms. `powers` de uma cena às vezes não pega — conferir
  com `show` antes de dar por salvo.

## 2026-09-29 — As capturas do Marshall 1959BJA são só cabeçote: sem gabinete soam limpas e ásperas

- **Gotcha / invariant:** `nam_marshall_1959bja_a2` e `nam_marshall_1959bja_super_bowl_a2` não têm gabinete
  dentro. Medido em 6 acordes do build de *Welcome to Paradise*: sem cab, a faixa 6–12 kHz fica só 16–20 dB
  abaixo de 0,5–2 kHz; com `ir_marshall_4x12_v30` cai para 29–33 dB. É a assinatura de um cabeçote pelo
  load box, não de um rig completo.
- **Why it matters:** usada sozinha numa chain, a captura soa "clean demais" e fina — foi a queixa do João
  em 29/09, resolvida pondo um cab. Na mesma medição o knob de gain dessa captura mexeu pouco na saturação
  (fator de crista 10,1 dB no gain 2, 9,9 dB no gain 10; o `input_db` de +6/+12 dB também), e todas as
  variantes ficaram 5–6 dB mais escuras que o disco acima de 1,5 kHz.
- **Applies to:** toda chain ou build com essas duas capturas; o manifest não diz "amp only", então
  conferir a resposta acima de 6 kHz antes de assumir que uma captura NAM já traz gabinete.
