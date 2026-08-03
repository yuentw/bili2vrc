#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

echo "[bili2vrchat] 啟動中..."

if [[ -f .venv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

# python3 -m pip install -r requirements.txt -q
exec python3 app.py
