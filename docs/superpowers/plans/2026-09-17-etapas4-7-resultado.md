# Etapas 4–7 — resultado (17/09)

## Etapa 4 — OpenRig

- `tone_builder/devices/openrig.py`: catálogo pelos manifestos (`captures:`), resolução da pesquisa por
  palavras do nome e tipo, render com rejeição de bloco ignorado e reamostragem da entrada,
  compressor LV2 varrido (limiar −30/−50/−70 × razão 4/8, só conta com redução ≥ 3 dB), EQ no
  `lv2_x42_fil4` (aceita `freqN/gainN/qN`: +12 dB em 1 kHz mediu +9,6 dB relativo).
- `tone_builder/build.py` + `tone-builder build`; `tone-builder verify` confere o que foi gravado.
- **Aceite, redefinido pela medição.** O 8,2 dB da rodada 7 não é reproduzível: a ferramenta
  commitada no music-setup dá 10,5 dB (corda pela regra de casa). O port foi validado contra o
  algoritmo antigo nas mesmas 8 notas: alvo idêntico (mesmos harmônicos por nota) e desvio 7,59 ×
  7,54 dB (a diferença é só o detector de ataque).
- Gravity de ponta a ponta (19 min): TS drive 8 tone 5 → Dumble ODS John Mayer hiz, EQ plano
  (retenção reprovou o EQ: melhora 0,70, ruído 1,54), **7,76 dB**, zero saturada a +18 dB, status
  pronto. Números por classe em `music-setup/docs/metodo-timbre.md` (rodada 9).
- **Pendente:** gravar no OpenRig e rodar `verify` — o app está aberto (`adapter-gui --mcp`, `.solvers/issue-947`), mas `127.0.0.1:4123` recusa conexão e o processo não escuta porta TCP (conferido 17/09).

## Etapas 5 e 6 — MK-300 e Ampero II

- `tone_builder/devices/pedal.py`: adaptadores pelos CLIs `mvave` e `ampero2` (resolve, knobs,
  varredura do knob de ganho em 20/40/60/80 % como equivalente das capturas, comandos de escrita,
  `reamp` por USB). Testes com dublê do CLI.
- **Pendente, com aparelho:** MK-300 não estava conectada (nenhuma porta MIDI). Ampero II: o re-amp
  por USB exige um patch com `SOURCE = USB OUT 3/4`, que só se ajusta na tela; não existe nenhum.
  Também pendente: a comparação USB × entrada analógica da MK-300 (spec).

## Etapa 7 — skills dos aparelhos

- Plugin `tone-builder` 0.2.0 com a skill `tone-builder` (RED: sem ela o agente perguntava nome/slot
  e não tinha conferência pós-gravação; GREEN: sem perguntas, pesquisa mantida sob pressão,
  "parcial" repassado, MK-300 desligada relatada; brecha do nome repetido fechada).
- `openrig` 2.0.2, `mvave` 0.2.1, `ampero2` 0.3.1: a skill `tone-builder` de cada um manda o timbre
  com gravação para o plugin tone-builder e mantém só o caminho sem referência (RED: as três julgavam
  com `compare` + `eq-match`; GREEN: nenhuma usa, mesmo com o pedido insistindo).
- Achado pelo teste de base e corrigido: a bateria dava a pares de drives e ao EQ ajustado a fonte
  inventada `https://derived`; agora são `derived_units`, sinalizados no relatório.
