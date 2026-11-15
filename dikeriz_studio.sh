#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
PY="${PYTHON:-python3}"
command -v "$PY" >/dev/null || { echo "python3 bulunamadi (3.9+ gerekli)"; exit 1; }
"$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' || { echo "Python 3.9+ gerekli"; exit 1; }
[ -x .venv/bin/python ] || "$PY" -m venv .venv
if ! cmp -s requirements.txt .venv/.requirements.txt; then
  echo "Paketler kuruluyor..."
  .venv/bin/python -m pip install --disable-pip-version-check -q -r requirements.txt
  cp requirements.txt .venv/.requirements.txt
fi
exec .venv/bin/python dikeriz_studio.py "$@"
