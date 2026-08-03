#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
ROOT="$(pwd)"

echo "[bili2vrchat] 啟動中..."

# ── bun：優先 PATH，其次專案 .bun；皆無則安裝到 .bun ──
BUN_CMD=""
if command -v bun >/dev/null 2>&1; then
  BUN_CMD="$(command -v bun)"
elif [[ -x "$ROOT/.bun/bin/bun" ]]; then
  BUN_CMD="$ROOT/.bun/bin/bun"
else
  echo "[bili2vrchat] 未偵測到 bun，安裝至 .bun ..."
  export BUN_INSTALL="$ROOT/.bun"
  curl -fsSL https://bun.sh/install | bash
  if [[ ! -x "$ROOT/.bun/bin/bun" ]]; then
    echo "[bili2vrchat] bun 安裝後找不到 .bun/bin/bun" >&2
    exit 1
  fi
  BUN_CMD="$ROOT/.bun/bin/bun"
fi

export PATH="$ROOT/.bun/bin:$PATH"

# ── frontend：bun install + generate ──
echo "[bili2vrchat] 建置 frontend ..."
(
  cd frontend
  "$BUN_CMD" install
  "$BUN_CMD" run generate
)

if [[ -f .venv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

exec python3 app.py
