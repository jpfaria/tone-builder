# Timbre medido em acordes (issue #1)

## Problema

`build` só acha alvo onde a guitarra separada toca nota isolada que existe na biblioteca. Base em
acorde não gera alvo: *Even Flow* 0:00–2:50 sai com `exit 4`, e na faixa inteira as duas notas
achadas eram do solo do McCready. Também falta restringir o alvo a um trecho da música.

## Decisões (jpfaria, 18/09)

- DI do acorde vem de **duas fontes**: soma de notas da biblioteca que já existe, e biblioteca de
  acordes gravados em DI quando houver. O validador mede quanto a soma erra contra o gravado.
- Detecção de quais notas soam num ataque: **dois detectores** no tone-analyzer (saliência harmônica
  e basic-pitch); o validador mede os dois e o padrão é o que errar menos.
- Critério de aceite no `validate`: conjunto de notas certo em **≥ 90 %** dos acordes, **zero nota
  falsa**, erro de nível nos harmônicos aceitos **≤ 2 dB** a −6 dB de dominância.

## Fronteira

| tone-analyzer (informação de UM áudio) | tone-builder (compara ou decide) |
|---|---|
| `detect_chords`: ataque → conjunto de notas | alvo de acorde, DI do acorde, voicing, validador |
| `levels_at`: nível e destaque em frequências dadas | escolha do detector padrão |

## tone-analyzer

`tone_analyzer/chords.py`:

- `levels_at(signal, sr, start_s, freqs_hz, dur_s=0.6)` → `level_db`, `neighbour_db`,
  `prominence_db` por frequência. Mesma leitura do `harmonic_levels` (janela de Hann, pico ±1,2 %,
  vizinhança 0,90–0,96 / 1,04–1,10); `harmonic_levels` passa a chamar esta.
- `detect_chords(signal, sr, dur_s=0.6, detector="salience")` → `[{start_s, midis, names}]`, um por
  ataque de `note_onsets`, só ataques com 2+ notas (nota isolada continua com `detect_notes`).
  - `salience`: para cada MIDI 40–88, saliência = soma do destaque ≥ 13 dB nos harmônicos 1–8.
    Guloso: aceita a mais saliente, marca os harmônicos dela como explicados, recalcula, para em
    6 notas ou quando nenhuma candidata tem 3+ harmônicos não explicados acima do limiar.
  - `basic-pitch`: extra opcional `tone-analyzer[basic-pitch]` (onnxruntime); notas ativas em
    ≥ 75 % da janela de 0,6 s depois do ataque. Sem o extra instalado, erro claro.
- CLI `tone-analyzer chords AUDIO [--detector …]` → JSON. Versão 0.5.0.

## tone-builder

### Janela de tempo
`build` e `target` ganham `--from M:SS --to M:SS`: o alvo só aceita ataques dentro da janela. A
mistura das duas guitarras se resolve com `--role rhythm|solo` do tone-analyzer, que já existe;
a janela cobre música sem stem separado por papel.

### Alvo de acorde (`tone_builder/target.py`)
Localizado na pista separada com `detect_chords`, lido no disco com `levels_at`. Frequências =
`k·f0` de cada nota, k = 1..16; sai toda frequência a menos de 2,4 % de outra de nota diferente
(dono ambíguo). Mesmos portões: destaque ≥ 13 dB por frequência, ≥ 5 aceitas. Entrada do alvo:
`{kind: "chord", start_s, midis, name, freqs_hz, level_db, accepted}`. A nota isolada ganha
`kind: "note"` e `freqs_hz`; `compare.note_deviation` passa a ler em `freqs_hz` (uma só rotina
para os dois).

### DI do acorde (`tone_builder/chords.py`)
- **Soma**: todo voicing tocável — uma nota por corda, cordas distintas, casas dentro de 4 casas
  (cordas soltas não contam), no máximo 32 voicings por acorde. Cada nota da biblioteca é
  alinhada pelo ataque (`take_onset`), e a soma é normalizada para o pico de uma nota. Escrita em
  `<out>/work/chords/<voicing>.wav`.
- **Gravado**: `biblioteca/<guitarra>/<posição>/acordes/<c6-40_c5-47_c4-52>.wav` (corda-midi por
  nota); `library record-chord <guitarra> <posição> <c6-40_c5-47_…> --device … --channel …` grava
  3 palhetadas, e o `check` confere o conjunto de notas com `detect_chords`.
- Escolha como a da corda: todo DI candidato (voicings somados + gravados com o mesmo conjunto) é
  renderizado com o amp da pesquisa e medido; fica o de menor desvio. O relatório diz de onde veio.

### Build, relatório e verify
O alvo passa a ser notas + acordes em ordem de tempo; retenção, bateria, EQ e margem não mudam
(já trabalham sobre a lista de atribuições). `report.notes[].di` guarda o WAV do acorde somado, e o
`verify` o reusa. Sem alvo nenhum: `exit 4` diz quantos ataques foram vistos, quantos eram
acorde e por que caíram.

### Validador (`tone-builder validate --chords`)
Acordes montados com notas da biblioteca (power chord de 2 e 3 notas, tríades maiores e menores
em formas abertas e com pestana), ataques espalhados 0–30 ms entre cordas, no mesmo fundo
sintético de hoje, em −6/−3/0/+6 dB. Mede por detector: % de conjuntos certos, notas falsas, erro
de nível. Com acordes gravados: erro entre alvo lido no gravado e no somado do mesmo voicing
(informativo; vai para `docs/metodo.md`). Exit 1 se o detector padrão falhar o critério a −6 dB.

## Testes
- tone-analyzer: `levels_at` bate com `harmonic_levels` em nota única; `detect_chords` acha o
  conjunto em acordes sintéticos (soma de tons harmônicos) e não inventa nota em nota isolada.
- tone-builder: janela filtra ataques; alvo de acorde descarta frequência de dono ambíguo;
  voicings respeitam uma-nota-por-corda e abertura de 4 casas; build com alvo só de acorde
  (fake device) termina e o relatório traz a origem do DI; validador sintético com a biblioteca
  real (`test_real_library`).

## Aceite
`tone-builder validate --chords` passa o critério com a PRS SE Silver Sky pos5, e o build da base
de *Even Flow* (`--role rhythm` ou `--from 0:00 --to 2:50`) sai com alvo de acordes e número.
