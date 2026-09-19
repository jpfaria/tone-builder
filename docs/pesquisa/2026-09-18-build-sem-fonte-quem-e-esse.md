# Build por medição de uma música sem rig documentado — "Quem é esse?" (Samuel Lima), 18/09/2026

Primeiro build com fonte de primeira mão (o guitarrista respondeu: "AC30 + Fender. compressor.
Reverb e delay") e classes abertas. 397 capturas de amp, 101 notas-alvo, OpenRig. Medições e
scripts: `~/.tone-builder/quem-e-esse-samuel-lima/medicoes/`.

## Resultado do build, e por que NÃO foi para o rig

`report.md` saiu **pronto** e escolheu `nam_fender_bassman_1971_a2[voicing=ts9_ds1_boost…]`: um
Bassman com TS9 e DS1 na frente. Isso contradiz o ouvido do jpfaria ("o som é clean", "tem uma
distorção que não existe na original") e a declaração do guitarrista, que não cita drive.
Não foi por margem pequena: capturas distorcidas leem 6,5 dB, as limpas 10 a 12 dB.

## Quatro hipóteses medidas

| hipótese | teste | resultado |
|---|---|---|
| a mix enviesa a leitura dos harmônicos | guitarra limpa conhecida, notas de altura aleatória, 5 dB abaixo do acompanhamento real | **refutada**: a cadeia verdadeira lê 1,9 dB, as distorcidas 7 a 8 |
| a captura distorcida ganha só por compensar brilho, coisa de EQ | reordenar as 397 descontando um EQ de 4 bandas ajustado nas notas de ajuste | **refutada**: distorcidas 6,2 a 6,4; limpas 10 a 11 |
| o alvo mistura trechos limpos e sujos da música | reordenar por trecho (o ouvido validou 0:49–2:00) | **refutada**: em todos os trechos as distorcidas ganham por ~4 dB |
| a banda toca as mesmas notas e infla os harmônicos do alvo | guitarra limpa conhecida NAS NOTAS E INSTANTES REAIS, 5 dB abaixo do acompanhamento real | **confirmada em parte**: o desvio da cadeia verdadeira salta de 0,3 para 6,4 dB e a margem limpo × sujo encolhe de 9 para 1,5 dB — mas a verdadeira ainda ganha |

O piso de 6,4 dB do teste é o mesmo desvio final do build real (6,4 a 6,7 dB). Nesta música a
leitura do alvo carrega ~6 dB de contaminação dos instrumentos que tocam as mesmas notas.
A validação de 16/09 (erro ≤ 2 dB com dominância de −6 dB) usou fundo sem relação harmônica com
a guitarra; com a banda tocando as mesmas notas ela não vale.

Restringir às notas em que a guitarra domina (dominância medida contra `mix − stem`, ≥ 9 dB,
57 notas) não muda a ordem. A dominância vem do stem do Demucs, que pode estar atribuindo à
guitarra a energia afinada dos outros instrumentos: a medida é circular.

## O que sobra como explicação, sem dado para decidir

1. A guitarra dele (tipo Telecaster, captador desconhecido) é muito mais rica em harmônicos que a
   PRS no captador do braço; nenhum amp limpo leva a DI do braço até lá, e a captura distorcida
   imita isso. **Teste que decide:** gravar a posição 1 (ponte) da PRS na biblioteca e repetir.
2. Ele toca com mais ganho do que o ouvido percebe (compressor + amp na beira da saturação).

## Decisões

- O preset do build NÃO foi gravado no OpenRig. A chain validada de ouvido continua valendo.
- `pronto` no relatório não bastou: faltava ao método desconfiar de um resultado que contradiz a
  fonte (a pesquisa diz "sem drive" e o amp escolhido é uma captura com dois drives).

## Pendências de método que este caso abriu

1. Relatório deve marcar conflito entre a captura escolhida e a pesquisa (captura com pedal de
   drive embutido quando `single_drive` está em `not_found`).
2. A prova de verdade conhecida precisa de um caso com fundo harmonicamente relacionado.
3. `linearity` de cada captura escolhida deveria ir para o relatório.

## Quinta hipótese: captador da ponte (19/09/2026) — refutada

Gravada a posição 1 (ponte) da PRS, 96 notas. Mesmo alvo (101 notas da gravação), mesmas seis cadeias,
desvio em dB (`~/.tone-builder/quem-e-esse-samuel-lima/medicoes/ponte-vs-braco/`):

| cadeia | braço (pos5) | ponte (pos1) |
|---|---|---|
| AC30 limpo n vol3 (aprovado de ouvido) | 12,20 | 13,09 |
| Twin limpo | 13,06 | 14,31 |
| Deluxe 65 limpo | 10,38 | 12,55 |
| Bassman 71 ts9_ds1_boost (escolha do build) | 7,52 | 8,71 |
| Bassman ts9_ds1 | 7,55 | 8,64 |
| AC30 n vol8 cut10 | 7,74 | 8,54 |

A ponte piora todas as cadeias em cerca de 1 dB e não muda a ordem: amp limpo com ponte (12,6 no melhor caso)
continua longe de amp com drive com braço (7,5). O captador não explica a preferência por drive.
