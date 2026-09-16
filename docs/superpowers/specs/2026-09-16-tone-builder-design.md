# tone-builder — design

Data: 16/09/2026 · Autor da decisão: jpfaria · Estado: aprovado em conversa, aguardando revisão desta spec.

## Por que existe

O método para recriar o timbre de uma gravação estava espalhado e, em parte, errado:

- `openrig:tone-builder` e `mvave:tone-builder` (MK-300) carregavam cada um a sua cópia das
  regras genéricas; a Ampero II não tinha tone-builder.
- O método que foi **validado contra verdade conhecida** em 16/09 existia só no repo pessoal
  `music-setup` (`docs/metodo-timbre.md`, `tools/openrig/timbre_medida.py`,
  `tools/openrig/valida_timbre_medida.py`, `tools/openrig/biblioteca_notas.py`).
- O `mvave:tone-builder` ainda usa `proximity_pct` e `eq-match` sem retenção — exatamente o que
  foi medido como inválido para comparar notas isoladas.

O `tone-builder` concentra o método num lugar e usa os aparelhos só para gravar e tocar.

## Números que justificam as decisões (medidos em *Gravity*, John Mayer, 16/09)

| fato | número | consequência no design |
|---|---|---|
| referência separada (Moises/Demucs) apaga harmônicos acima de ~H6 | disco +21 dB sobre a vizinhança onde a pista separada marca −104 dB | alvo = o disco lido nos harmônicos |
| a guitarra nunca domina a mix | mediana −5,4 dB | pista separada só localiza a nota |
| banda de 1/3 de oitava numa nota isolada | vales 74–84 dB abaixo dos picos | comparação nos harmônicos |
| alvo nos harmônicos, contra verdade conhecida | erro 1,84 dB a −6 dB de dominância, zero falso positivo | método aceito; vira teste automático |
| detector de pitch | autocorrelação pura 92/96 e 21/21; "correções de oitava" 84–93/96 e 17/21 | só autocorrelação pura |
| peso das variáveis | corda até 10,7 dB · pedal 1,1 · gabinete 0,7 · amp 0,3 | a biblioteca de notas é a peça central |
| EQ ajustado sem retenção | 5 iterações: ajuste melhora, teste piora (8,1 → 8,3 … 13,5) | nenhum EQ ou escolha sem retenção |
| compressor com limiar alto | −30/−20 dB tiravam 0,0 dB | compressor só conta com redução ≥ 3 dB medida |
| ranking cru de pedais | Fuzz Factory 6,7 dB, sem fonte; Tube Screamer 8,2, com fonte | candidatos com e sem fonte separados; escolha entre os com fonte |

## Peças e responsabilidades

### `tone-builder` (repo novo, plugin do Claude Code)

O método, sem conhecer protocolo nem catálogo de aparelho nenhum.

- **Comparação**: tudo que envolve dois áudios ou uma decisão — montar o alvo (pista separada
  localiza a nota, disco dá o nível), comparar render × alvo nos harmônicos, retenção, validador de
  verdade conhecida.
- **Passo 0 — pesquisa** do rig da gravação: busca na web na sessão, página aberta (resumo de
  busca não é fonte), rig do disco separado do rig de turnê, "não achei" é resultado.
- **Biblioteca de guitarras** (gravação, teste por nota, armazenamento).
- **Bateria de blocos** completa, **seleção por retenção**, **margem de pico**.
- **Conferência pós-gravação** e **relatório de entrega**.

### `tone-analyzer` (existe; fica só com análise de UM áudio)

Analisa **um** áudio de guitarra, sem efeito colateral (jpfaria, 16/09: *"o tone-analyzer deveria
somente analisar um áudio de guitarra"*).

- Entrega três coisas para um áudio (jpfaria, 16/09: *"gerar métrica, documentação e espectro"*):
  - **métrica** — JSON;
  - **documentação** — o relatório legível (hoje `analysis.pdf`);
  - **espectro** — os espectrogramas (hoje `spec_*.png`).
- Ganha nessas três saídas: detecção de pitch (autocorrelação pura); início de cada nota; nível de
  cada harmônico H1..H16 de uma nota num instante dado, com o destaque sobre a vizinhança.
- `compare` e `eq-match` comparam **dois** áudios, então não pertencem mais a ele: ficam marcados
  como **obsoletos** (e inválidos para nota isolada) na documentação e na saída.

### Aparelhos — `openrig`, `ampero2`, `mvave`

Viram gravadores com o mesmo contrato (seção "Contrato de aparelho"). Os `tone-builder` de dentro
de `openrig` e `mvave` encolhem para "use o tone-builder".

### `music-setup` (repo pessoal)

Continua documentando o rig do jpfaria. Fornece, como dado de configuração, o roteamento de re-amp
de cada aparelho. Mantém o histórico do *Gravity* como caso de estudo, apontando para este repo.
O plugin não depende do `music-setup`.

## Biblioteca de guitarras

```
biblioteca/
  <guitarra>/                       id igual ao do music-setup (ex.: silversky-se)
    guitarra.yaml                   captadores, afinação, cordas, posições do seletor, data
    <posicao>/
      c<corda>-<midi>-<nota>.wav    48 kHz, uma nota, começando no ataque
      medicao.yaml                  resultado do teste de cada nota
```

- **Git LFS** para os WAVs. Tomadas brutas não entram.
- `guitarra.yaml` só com o que o usuário disser ou os docs trouxerem. **Posições do seletor são
  declaradas por guitarra** — não se assume 5 (em `music-setup/docs/guitarras.md` há Les Paul com
  EMG ativos, HSS e SSS).
- **Nenhuma nota é salva sem passar no teste:** pitch medido = nota esperada (autocorrelação pura);
  duração ≥ 0,67 s; zero amostras saturadas; sinal acima do ruído de fundo da própria tomada.
  Reprovou → não salva e pede para regravar aquela nota.
- **Gravação** pergunta guitarra, posição, corda e **a entrada onde escutar** (nada de interface
  fixa no código); bipe no início; substituir nota vira commit, o histórico fica no git.
- **Música não entra no repo.** Disco e pistas separadas são trazidos por cada usuário.
- Conteúdo inicial: as 96 notas da PRS SE Silver Sky, posição 5 (17 MB).

## Fluxo de um timbre

```
0. pesquisa     rig da GRAVAÇÃO, página aberta, disco × turnê separados
1. alvo         disco + pista separada do usuário → notas inteiras (0,6 s do ataque),
                nível de cada harmônico lido no disco, aceito só com ≥ 10 dB sobre a vizinhança
2. corda        para cada nota do alvo, mede todas as cordas disponíveis na biblioteca
3. bateria      TODAS as classes, cada uma medida:
                drive único · drives empilhados (pares, 2 ordens) · boost ·
                compressor (conta só com redução ≥ 3 dB) · amp · gabinete · EQ
                candidatos com fonte e sem fonte em listas separadas
4. escolha      pelas notas de TESTE (retenção metade/metade), entre os com fonte
5. margem       DI +12 e +18 dB, zero amostra saturada
6. gravar       no aparelho, via contrato; reler do aparelho/disco
7. conferir     renderizar/tocar a preset GRAVADA e medir de novo; tem que bater com o passo 4
8. relatório    por classe: número, ou "não mensurável — motivo"
```

**Relatório e a palavra "pronto".** Só pode sair "pronto" se toda classe do passo 3 tiver número
ou motivo escrito. Faltou alguma → "parcial: faltam X, Y". A lista do que o método não mede sai
sempre, não só quando perguntada: reverb e ambiência, processamento de mixagem do disco, grave
abaixo de ~200 Hz, agudo sem harmônico destacado, imagem estéreo, percepção do ouvido.

**Time FX** (delay, modulação, reverb) não são medidos pela métrica: só entram com fonte da
gravação, e a ausência de fonte é registrada como "não achei", não como "não usa".

## Contrato de aparelho

Seis operações, cada aparelho implementa sobre o próprio plugin.

| operação | OpenRig | M-VAVE MK-300 | Ampero II Stage |
|---|---|---|---|
| catálogo por classe | manifestos dos plugins | catálogo do `mvave` | categorias/`params` do `ampero2` |
| achar modelo pelo nome pesquisado | `resolve_gear` | por nome no catálogo | por nome no catálogo |
| gravar preset | MCP: carregar blocos → salvar preset → salvar projeto | CLI `mvave`: blocos → `save` | CLI `ampero2`: `model`/`param` → `save` |
| ler de volta | reler YAML do disco | ler preset do aparelho | `show` após recarregar de outro patch |
| renderizar DI | `openrig-render` (software) | `mvave reamp di.wav wet.wav` (USB, põe o USB Audio em RESAMPLE e restaura) | tocar pela interface |
| armadilhas conhecidas | bloco inválido é ignorado em silêncio e sai com 0; prefixo `nam_`; entrada não é reamostrada | modo de USB audio | Global Settings: uma escrita, ler a página, só então a próxima; travou = só desligar/ligar |

### Escrita em duas camadas

- **Preset** (blocos, parâmetros, nome): livre, sempre em slot/preset **novo** ou no que o usuário
  nomear. Nunca sobrescreve outro timbre.
- **Configuração global** do aparelho (modo de USB audio, canal de entrada, E/S do OpenRig): só
  quando o render exige, **restaurada ao estado anterior** no fim, e listada no relatório.

### Render do M-VAVE MK-300: USB

O plugin `mvave` (0.2.0) já re-amplifica por USB: `mvave reamp di.wav wet.wav`, com o USB Audio
em RESAMPLE só durante a execução e restaurado depois. É o caminho padrão — não precisa de
roteamento na interface.

**Não medido:** se o re-amp por USB soa igual ao DI entrando pela entrada analógica do pedal
(o USB pula o estágio de entrada analógico). O caminho analógico fica documentado como
alternativa — `ADA #1 Out 5` → re-amp C → INPUT, escuta em `ADAT 6/7` (XLR L/R), `rack.yaml`,
confirmado 16/09 — e a primeira validação com aparelho compara os dois na mesma nota.

### Render por interface (Ampero II)

- O roteamento é **configuração do gravador**: saída que toca o DI e entrada onde escutar.
  Faltando, **pergunta** — nunca deduz, e antes de perguntar procura em `docs/patchbay.md`,
  `docs/cenas-universal-control.md`, `docs/roteamento-element.md`, `docs/equipamentos/` e
  `rack.yaml` do `music-setup`.
- Valores do rig do jpfaria: toca por `ADA #1 Out 2` (send `ADAT 1/2` **hard R**) → IN L; escuta em
  HD 8 `In 5/6` (OUT XLR L/R) — `docs/patchbay.md`, `docs/cenas-universal-control.md`. O
  `ADAT 1/2` hard L é o FX RETURN da Ampero: o DI não pode ir para lá.
- O plugin `ampero2` não documenta re-amp por USB; se existir, entra como na MK-300.
- **Antes de tocar:** teste de laço — se a entrada de escuta aparece no barramento que alimenta a
  saída, aborta.
- Alinhamento pela latência medida no bipe de início; gravação em silêncio reprova o candidato.

## Testes

### Automáticos (sem aparelho)

- **Pitch** contra as notas da biblioteca (MIDI no nome do arquivo). Falha se cair abaixo do valor
  medido na data da entrada da biblioteca.
- **Alvo nos harmônicos** contra verdade conhecida: nota da biblioteca + acompanhamento
  **sintético** (ruído rosa + linha de baixo sintetizada, porque música não pode ir para o repo).
  Critério: erro ≤ 2 dB a −6 dB de dominância e zero falso positivo.
- **Retenção:** caso com EQ superajustado de propósito tem que ser reprovado.
- **Relatório:** faltando uma classe, a palavra "pronto" não pode aparecer.
- **Compressor:** ajuste com redução < 3 dB tem que sair marcado como não testado.
- **Aparelhos com dublê:** ordem de escrita (Ampero uma global por vez, restauração no fim),
  preset sempre em slot novo, abortar em laço de roteamento. Nenhum teste automático toca hardware
  ou escreve fora de diretório temporário.

### Com aparelho (manuais, sob pedido do usuário)

- gravar → ler de volta → tocar DI → medir; tem que bater com o medido antes de gravar.
- Validador de verdade conhecida usando o acompanhamento real da música do usuário.

## Erros

| situação | comportamento |
|---|---|
| equipamento pesquisado sem modelo no catálogo | para e lista o que não achou |
| nota do alvo sem par na biblioteca | segue sem ela; o relatório mostra a cobertura |
| render com bloco ignorado ou DI gravado em silêncio | reprova o candidato |
| laço no roteamento | aborta antes de tocar |
| Ampero deixa de responder | para tudo; avisa que só desligar e ligar recupera e que escritas recentes podem não ter salvo |

## Ordem de implementação

Cada etapa só começa quando a anterior passa nos próprios testes.

1. **`tone-analyzer`**: pitch, início de nota e harmônicos de um áudio; `compare`/`eq-match`
   marcados como obsoletos.
2. **`tone-builder` esqueleto**: repo, plugin, Git LFS, biblioteca (gravador com teste por nota) e
   as 96 notas existentes. Pronto antes de mapear as outras guitarras.
3. **Método**: pesquisa, alvo, comparação nos harmônicos, validador de verdade conhecida, corda,
   bateria completa, retenção, margem, relatório. Migra a parte
   genérica de `music-setup/docs/metodo-timbre.md` e `music-setup/tools/openrig/`.
4. **Aparelho OpenRig**. Aceite: refazer *Gravity* pelo tone-builder e chegar no mesmo desvio de
   **8,2 dB** da rodada 7 (Tube Screamer → Dumble ODS John Mayer → IR Vox AC30, EQ plano).
5. **Aparelho M-VAVE MK-300** (render tocando pela interface).
6. **Aparelho Ampero II** (por último, pela regra de escrita global).
7. **Encolher** `openrig:tone-builder` e `mvave:tone-builder` para "use o tone-builder".

## Fora do escopo

- Medir reverb, ambiência e processamento de mixagem do disco.
- Redistribuir gravações de artistas.
- Aparelhos além dos três citados.
