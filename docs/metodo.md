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
   Quem pesquisa é o agent `gear-researcher`, em contexto próprio; quem confere é o
   `research-auditor`, que abre cada URL citada e reprova bloco sem frase que o sustente. A
   conversa principal não pesquisa: recebe o veredito.
1. **Alvo = o disco, lido em cada frequência harmônica** — `tone_builder/target.py`.
   A pista separada só localiza onde a guitarra toca e qual é a nota.
   `--from M:SS --to M:SS` limita o alvo aos ataques dentro da janela; `--role rhythm|solo`
   escolhe a pista separada de cada guitarra (tone-analyzer).
1b. **Acorde** — `tone_builder/target.py`, `tone_builder/chords.py`. Ataque de 2+ notas na pista
   separada (`detect_chords`, detector padrão `salience`; `--chord-detector`, `--no-chords`
   desliga) vira entrada `kind: chord`, lida no disco em `k·f0` de cada nota (k = 1..16). Sai
   toda frequência a menos de 2,4 % de outra de nota diferente (dono ambíguo). Mesmos portões:
   destaque ≥ 13 dB, ≥ 5 frequências aceitas.
   - **Conjunto sem oitavas**: o detector não reporta dobra exata de oitava; "conjunto certo"
     compara `reduce(detectado)` com `reduce(verdade)` (sai toda nota com outra 12/24/36 abaixo).
     Porque o espectro da oitava é subconjunto do da nota de baixo: não há frequência que só ela
     tenha. As dobras são decididas pelo DI, não pelo detector.
   - **DI do acorde**: todo voicing tocável da biblioteca (uma nota por corda, casas dentro de 4,
     até 32 voicings, dobras de oitava enumeradas), somado nota a nota alinhado pelo ataque, e os
     acordes gravados com `library record-chord` que tenham o mesmo conjunto. Cada um é
     renderizado com o amp da pesquisa e medido; fica o de menor desvio, e o relatório diz de onde
     veio. Uma nota no ataque de um acorde é esse acorde (sai da lista de notas, contada).
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

10. **Conferência no aparelho** — `tone_builder/verify.py`. O preset salvo é renderizado 3 vezes;
    tolerância = 3σ da repetição (mínimo 0,1 dB). A MK-300 não repete a mesma nota igual: 0,2 dB
    entre re-amps idênticos sem modulação, até 0,5 dB com Univibe (*Alive*, 18/09/2026).

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

### Acordes (`tone-builder validate --chords`)

Acordes montados com notas da biblioteca (power chord de 2 e 3 notas, tríades maiores e menores
em forma de E e de A, raízes E2..E3), cordas espalhadas 0–30 ms, detecção na guitarra + resíduo
rosa 20 dB abaixo (a pista separada), nível lido na mistura com o fundo sintético. Critério a
−6 dB: conjunto certo ≥ 90 %, zero nota falsa, erro de nível ≤ 2 dB.

**Não passou** — PRS SE Silver Sky pos5, 18/09/2026:

| detector | dominância | acordes | conjunto certo | notas falsas | erro | falso positivo |
|---|---|---|---|---|---|---|
| salience | −6 dB | 78 | **61,5 %** | **31** | 1,59 dB | 0 |
| salience | −3 dB | 78 | 61,5 % | 31 | 1,40 dB | 0 |
| salience | 0 dB | 78 | 61,5 % | 31 | 1,09 dB | 0 |
| salience | +6 dB | 78 | 61,5 % | 31 | 0,77 dB | 0 |
| basic-pitch | — | — | não medido (não instalado) | — | — | — |

O nível passa (≤ 2 dB, zero falso positivo); a detecção não. Conjunto e notas falsas não mudam com
a dominância porque a detecção roda na pista separada, não na mistura. 26 das 31 notas falsas são
alturas de corda solta (D3 ×8, A2 ×6, B3 ×6, G3 ×4, E2 ×2) — provável ressonância simpática nas
amostras reais, ainda não medida. Por forma: power2 9/13, power3 9/13, maior-E 7/13, menor-E 6/13,
maior-A 9/13, menor-A 8/13. Somado × gravado: 0 pares (nenhum acorde gravado ainda). O padrão
continua `salience` por ser o único medido; o teste `test_chord_known_truth_on_the_shipped_library`
está `xfail(strict=True)` até passar.

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
| Mudar amp, compressor e EQ no mesmo passo num ajuste de ouvido | 17/09: estado "próximo" virou "completamente diferente" sem dar para saber o que piorou |
