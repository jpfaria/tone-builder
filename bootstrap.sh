#!/usr/bin/env bash
# Idempotent venv setup. Subsequent runs are <1 s if pyproject.toml is unchanged.
set -euo pipefail
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STAMP=".venv/.pyproject.sha"
SHA="$(shasum -a 256 pyproject.toml | awk '{print $1}')"
if [ -f "$STAMP" ] && [ "$(cat "$STAMP")" = "$SHA" ]; then exit 0; fi
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet -e ".[dev]"
echo "$SHA" > "$STAMP"
