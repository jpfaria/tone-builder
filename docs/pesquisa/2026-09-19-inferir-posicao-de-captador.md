# Dá para inferir uma posição de captador a partir das outras? (19/09/2026) — não passou

Pergunta do João: com ponte e braço gravados, a posição do meio (os dois humbuckers em paralelo) sai por conta?

**Teste.** PRS SE Paul's Guitar, 4ª corda, 16 notas gravadas nas três posições. Modelo: soma com sinal por
harmônico, `|s_b·A_ponte + g·s_n·A_braço|`, sinal = `sign(sin(n·π·x/L_casa))`, com a posição dos dois captadores e
o ganho relativo ajustados nas casas pares (52 mm, 153 mm, −4 dB) e o erro lido nas ímpares. Erro = RMS em dB da
forma do espectro, harmônicos 1–10, cada espectro centrado na própria média (cada tomada tem a sua força de palhetada).
Scripts em [2026-09-19-inferir-posicao/](2026-09-19-inferir-posicao/).

| comparação com o meio gravado | erro (dB) |
|---|---|
| modelo (soma com sinal) | 8,4 |
| soma de potências, sem fase | 10,5 |
| usar o braço no lugar | 10,5 |
| usar a ponte no lugar | 11,6 |
| *ponte contra braço (quanto duas posições reais diferem)* | *7,7* |
| *piso: mesma posição, mesmas notas, duas tomadas* | *4,3* |

**Conclusão.** O modelo melhora sobre "usar outra posição", mas erra 8,4 dB — tanto quanto a ponte difere do braço —
contra um piso de 4,3 dB. Não serve para substituir a gravação. Posição que se quer usar, grava-se.

**Achado lateral.** O piso de 4,3 dB (3,1–4,0 nos harmônicos 1–6) é a variação de palhetada entre duas tomadas da
mesma nota: nenhuma comparação de forma de espectro feita com uma única tomada por nota distingue menos que isso.
Medido nas cordas 3 e 2 da ponte com split, tocadas duas vezes por engano (`_takes/wrong-string/`).
