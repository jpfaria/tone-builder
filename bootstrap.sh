#!/usr/bin/env bash
# Idempotent venv setup. Subsequent runs are <1 s if pyproject.toml is unchanged.
set -euo pipefail
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STAMP=".venv/.pyproject.sha"
SHA="$(shasum -a 256 pyproject.toml | awk '{print $1}')"
if [ -f "$STAMP" ] && [ "$(cat "$STAMP")" = "$SHA" ]; then exit 0; fi
# tone-analyzer keeps 2.3 GB of song audio in Git LFS: an install needs the code, never the audio.
export GIT_LFS_SKIP_SMUDGE=1
# scipy ships no wheels for Python 3.14+ yet, so the venv must be built on 3.11-3.13.
supported() { "$1" -c 'import sys; sys.exit(not (3, 11) <= sys.version_info[:2] <= (3, 13))' 2>/dev/null; }
pick_python() {
  for c in python3 python3.13 python3.12 python3.11; do
    command -v "$c" >/dev/null 2>&1 && supported "$c" && { command -v "$c"; return; }
  done
  if command -v uv >/dev/null 2>&1; then uv python install 3.12 >&2 && uv python find 3.12; return; fi
  echo "bootstrap: Python 3.11-3.13 not found; install one or install uv (https://docs.astral.sh/uv/)" >&2
  exit 1
}
if [ -x .venv/bin/python ] && ! supported .venv/bin/python; then rm -rf .venv; fi
[ -d .venv ] || "$(pick_python)" -m venv .venv
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet -e ".[dev]"
echo "$SHA" > "$STAMP"
