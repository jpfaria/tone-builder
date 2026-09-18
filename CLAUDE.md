# tone-builder — regras para o agente

## Onde o agente trabalha: `.solvers/<nome>/`, clone de verdade (igual no OpenRig)

O agente trabalha SOMENTE em `.solvers/<nome>/`, um `git clone` do remoto com `.git` próprio
(confira `[ -d .solvers/<nome>/.git ]`). Edita ali, commita ali, dá push dali. A pasta principal é do
João e de outras sessões dele: o agente não edita nem roda git nela.

`git worktree` é PROIBIDO, e pasta irmã (`../tone-builder-qualquer-coisa`) também. Um worktree
registra a branch no `.git` da pasta principal e o `git checkout` do João nela aborta.

**Why:** em 18/09/2026 o agente criou um worktree em `../tone-builder-metodo3` para não pisar em
outra sessão. Resposta do João: "não quero que vc faça isso, vc tem que usar o padrão de .solvers,
igual no openrig".

**How to apply:** `git clone git@github.com:jpfaria/tone-builder.git .solvers/<nome> && cd .solvers/<nome> && ./bootstrap.sh`.
Commit seguido de push direto na `main` (LEI Nº 2 do João). Builds longos rodam a partir do clone.
Apagar um `.solvers/<nome>/` só depois de conferir que não tem nada sem push.

## Outras regras do projeto

Método: [docs/metodo.md](docs/metodo.md). Aprendizados: [docs/learnings.md](docs/learnings.md).
Quem guarda o quê: áudio e análise de uma música são do tone-analyzer (`~/.tone-analyzer/tones/`);
`~/.tone-builder/<música>/` guarda só pesquisa, builds, resultado de aparelho e relatório.
