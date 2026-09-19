# tone-builder

Recreates the tone of a recording by measurement, and configures OpenRig, M-VAVE and Ampero II.

Design: [docs/superpowers/specs/2026-09-16-tone-builder-design.md](docs/superpowers/specs/2026-09-16-tone-builder-design.md)
Method: [docs/metodo.md](docs/metodo.md)

## Commands

```bash
./bootstrap.sh
.venv/bin/tone-builder library list
.venv/bin/tone-builder library check prs-silver-sky-se pos5
.venv/bin/tone-builder library record <guitar> <position> <string|all> --device "<interface>" --channel <n>   # listens: names each note as it lands, ends when the string is complete; a wrong note is played again. `all` = the six strings in a row, 6 first, skipping the complete ones. `--seconds N` = a fixed-length take
.venv/bin/tone-builder target record.wav separated-guitar.wav --guitar prs-silver-sky-se --position pos5 --out target.json
.venv/bin/tone-builder validate
```

Songs and stems never go into this repo: each user brings their own.
