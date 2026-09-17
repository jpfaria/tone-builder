# Método para recriar o timbre de uma gravação

Fonte de verdade do procedimento. Cada passo aponta para o módulo que o implementa. Os números
vêm de medições em *Gravity* (John Mayer, *Continuum*) de 15–16/09/2026; o histórico completo, com
cada tentativa descartada, está em `jpfaria/music-setup` → `docs/metodo-timbre.md`.

## Procedimento

0. **Pesquisa do rig da gravação** — `tone_builder/research.py`.
   Busca na web na sessão, página aberta (resumo de busca não é fonte), URL em cada bloco, rig
   **do disco** separado do rig **de turnê**. Não achou é resultado: vai para `not_found` com o que
   foi buscado. A pesquisa decide quais blocos existem e quais unidades entram na lista; a medição
   só escolhe entre elas.
1. **Alvo = o disco, lido em cada frequência harmônica** — `tone_builder/target.py`.
   A pista separada só localiza onde a guitarra toca e qual é a nota.
2. **Unidade de comparação = uma nota inteira**, 0,6 s a partir do ataque, dos dois lados.
3. **Harmônico entra no alvo com destaque ≥ 13 dB** sobre a vizinhança; nota entra com ≥ 5.
4. **Mesma nota dos dois lados**: a nota do disco contra a mesma nota da biblioteca da guitarra,
   renderizada pelo candidato — `tone_builder/compare.py`, `tone_builder/render.py`.
5. **O nível sai** (média das diferenças); desvio da nota = RMS do resto.
6. **Corda escolhida medindo** todas as cordas que a biblioteca tem para a nota —
   `tone_builder/strings.py`.
7. **Bateria completa**, com retenção em toda escolha — `tone_builder/battery.py`,
   `tone_builder/retention.py`, `tone_builder/compressor.py`.
8. **Margem**: zero amostras saturadas com o DI em +12 e +18 dB — `tone_builder/margin.py`.
9. **Relatório**: "pronto" só com número ou motivo em toda classe e margem aprovada; senão
   "parcial" — `tone_builder/report.py`.

Sempre que mexer no detector de pitch, no portão de destaque ou na janela: `tone-builder validate`.

## O validador (verdade conhecida)

Nota conhecida da biblioteca + acompanhamento sintético (ruído rosa + baixo) em dominância
controlada; o alvo lido na mistura é comparado com o da guitarra sozinha. Critério: erro ≤ 2 dB a
−6 dB, zero falso positivo (pico aceito onde a guitarra sozinha tem destaque < 6 dB).

Medido em 16/09 com as 96 notas da PRS SE Silver Sky (posição 5) e 4 guitarras (DI cru, Dumble,
Two-Rock, chain final de *Gravity*):

| destaque mínimo | casos com erro ≤ 2 dB (de 16) | pior erro |
|---|---|---|
| 10 dB | 5 | 3,68 dB |
| 12 dB | 14 | 2,43 dB |
| **13 dB (em uso)** | **16** | **1,87 dB** |
| 15 dB | 16 | 1,56 dB |

Com 13 dB, fundo sintético: erro 0,70–1,04 dB e zero falso positivo. Fundo real de *Gravity*: erro
0,76–1,87 dB e 0–2 picos de outro instrumento por combinação. O "1,84 dB, zero falso positivo"
anotado antes vinha de uma guitarra só. Dados: `docs/superpowers/plans/2026-09-16-etapa3-*.json`.

## Quanto cada variável pesa (Gravity, 16/09)

| variável | quanto muda o desvio |
|---|---|
| **a corda em que a nota é tocada** | **até 10,7 dB** |
| ter ou não pedal de ganho | 1,1 dB |
| o gabinete (entre os 14 melhores) | 0,7 dB |
| o nível de entrada do amp (0 a +30 dB) | 0,6 dB |
| o amp (Dumble ODS John Mayer × Two-Rock) | 0,3 dB |

A biblioteca de notas de cada guitarra, com todas as cordas, pesa mais que trocar de amp.

## Retenção

Toda escolha (bloco, ajuste, EQ) é ranqueada na metade das notas e decidida na outra. Aceita só
se a melhora média nas notas de teste passa de 2 × erro-padrão das diferenças por nota.

EQ ajustado em *Gravity*, 4 notas de ajuste × 4 de teste:

| iteração | ajuste | teste |
|---|---|---|
| sem EQ | 8,3 | **8,1** |
| 1 | 6,7 | 8,3 |
| 3 | 7,6 | 9,6 |
| 5 | 11,2 | 13,5 |

Sem retenção a iteração 1 teria saído como "6,7 dB".

## Bateria de blocos

Classes: drive único, drives empilhados, boost, compressor, amp, gabinete, EQ, efeitos de tempo.
Uma classe sem candidato precisa de motivo (normalmente o `not_found` da pesquisa).

- **Compressor** só conta com redução de ganho medida ≥ 3 dB (RMS do DI − RMS do compressor
  sozinho, ganho de saída 0). Limiares de −40/−30/−20 dB tiravam 1,2/0,1/0,0 dB.
- **Com fonte × sem fonte** ranqueados separados. O melhor sem fonte (ZVEX Fuzz Factory, 6,7 dB)
  aparece no relatório, mas só o com fonte (Tube Screamer, 8,2 dB) pode ser escolhido.

## Nunca fazer

| Não faça | Porque |
|---|---|
| Usar stem/pista separada como alvo de espectro | apaga os agudos: −104 dB onde o disco mostra +21 |
| Usar a mix inteira como referência | em *Gravity* a guitarra nunca domina (mediana −5,4 dB) |
| Comparar por banda de 1/3 de oitava numa nota | os vales entre harmônicos ficam 74–84 dB abaixo |
| "Corrigir" a oitava do pitch com heurística | as três variantes pioraram (17/21 contra 21/21) |
| Cortar agudo acima de onde se mede | foi a causa de "está abafado", quatro vezes |
| Escolher corda pela regra "casa mais perto da 7" | errou 7 de 8 notas, ~7 dB |
| Aceitar EQ ou escolha sem retenção | ajuste melhora, teste piora |
| Declarar pronto testando uma classe só | a rodada 7 de *Gravity* testou só drive único |
| Começar a medir sem pesquisar o rig da gravação | falta bloco; o pedal só apareceu quando o usuário perguntou |
| Usar o rig de turnê como se fosse o do disco | o pedalboard muda a cada turnê |
| Afirmar equipamento de memória ou por resumo de busca | resumo juntou duas páginas e inventou um delay no disco |
| Confiar num número de validação medido com uma guitarra só | o 1,84 dB virou 1,5–3,7 dB com 4 guitarras |
| Ler áudio sem reamostrar para 48 kHz | Demucs escreve 44,1 kHz; tudo desloca +1,5 semitom |
