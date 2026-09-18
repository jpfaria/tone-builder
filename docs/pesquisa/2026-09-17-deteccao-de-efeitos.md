# Detecção de efeitos por medição — achados da prova de 17/09/2026

Prova descartável (spike), não é código de produção. Pergunta: dá para identificar delay, reverb e
distorção de uma gravação sem fonte de rig, só com matemática? Caso real: a guitarra do Samuel Lima
em "Quem é esse?" (https://www.youtube.com/watch?v=wwiejEM0aV4), validada de ouvido pelo jpfaria
numa chain do OpenRig. Código da prova: `~/.tone-builder/quem-e-esse-samuel-lima/spike-deteccao-efeitos/`.

## O que ficou provado

| tema | resultado |
|---|---|
| Detectores atuais do tone-analyzer (`detect_delay`, `estimate_rt60_s`, `classify_gain_character`) | **reprovados** em verdade conhecida: clean sai "distortion", caso seco sai RT60 3,15 s com confiança 0,8 (mede o sustain da corda), delay sai aleatório (o ritmo engana a correlação de envelope) |
| Delay por cepstrum do arquivo inteiro (ondulação de período 1/D em log\|X(f)\|²) | acha o tempo com erro < 1 ms; aguenta mix de 4 %, reverb por cima, guitarra 5 dB abaixo do acompanhamento real, AAC 128k e stem do Demucs |
| Delay modulado (wow de fita) | a força do pico cai ~100× dentro da mix (de ~700× para 7–9× o fundo; sem delay dá 2–4×). A altura do pico NÃO serve de critério |
| Critério certo | **persistência**: o mesmo atraso (±4 ms) votado em janelas independentes de 20 s. Sem delay: no máximo 2 janelas em 8. Com delay conhecido: 4 em 4 |
| Caso real | 728,2 ms em 15 de 44 janelas do stem da guitarra (colcheia pontuada a ~62 bpm). 483,8 e 967,8 ms caem de 17 para 9 e 8 janelas ao passar da mix para o stem: parecem ser do acompanhamento programado, não da guitarra |
| Ouvido × matemática | a chain aprovada de ouvido usava 726 ms; a medição deu 728 ms |

## O que NÃO funcionou

- Reverb por queda livre depois de corte de nota: acerta 1,0 s e 2,5 s quando acha cortes, mas confunde as repetições do delay com cauda e não acha cortes em execução real.
- Distorção por frequências de diferença (intermodulação em díades): não separou clean/edge/drive.
- Distorção por sustain da nota: ordena clean < edge < drive, mas o reverb desloca o clean para perto do edge.
- Detector de reataque por faixa de frequência: perde para o ritmo de uma frase periódica.

## Armadilhas

- Frase sintética não pode reusar a mesma amostra: nota repetida vira cópia exata e o cepstrum acusa "eco" no ritmo.
- Suavizar o cepstrum por média apaga o pico (1 amostra de largura). Somar energia em várias larguras (0 a 6 ms) preserva.
- Cepstrum de sinal só com reverb, sem mix, dá falso pico alto: mais um motivo para decidir por persistência.
- Wow de 8 ms a 0,8 Hz equivale a ±70 cents: irreal. Teto plausível de fita: ~3 ms (±26 cents).

## Verdade de ouvido deste caso (gabarito para os próximos detectores)

Som limpo (AC30 canal normal, volume 3; o top boost volume 3 já soava sujo), captador do braço,
agudo e médio abaixo do neutro, delay ~728 ms com mix ~24 % e feedback ~28 %, reverb hall ~3,2 s
com cauda a 30 % e modulação na cauda. A primeira tentativa, sem medição, errou para mais em todos
os efeitos (mix 35 %, cauda 45 %, queda 4,5 s) e no ganho.

## Fronteira

Presença, tempo e quantidade de um efeito são informação de UM áudio: tone-analyzer. Abrir
candidatos do catálogo nas classes detectadas e escolher por medição: tone-builder.

## Próximos passos

1. Levar `delay_cepstrum3` + `delay_persistent` para o tone-analyzer, com a prova de verdade conhecida como teste.
2. Quantidade do delay (mix, feedback) e reverb: medir por comparação render × disco na cauda das notas, porque o tone-builder tem a DI da mesma nota.
3. Ganho e captador: idem, por harmônicos da nota contra a biblioteca.
