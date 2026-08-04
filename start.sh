#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
ROOT="$(pwd)"

echo "[bili2vrchat] 啟動中..."

if ! command -v uv >/dev/null 2>&1; then
  echo "[bili2vrchat] 未找到 uv。請先安裝：https://docs.astral.sh/uv/getting-started/installation/" >&2
  exit 1
fi

FRONTEND_DIST="$ROOT/frontend/.output/public"
if [[ ! -f "$FRONTEND_DIST/index.html" && ! -f "$FRONTEND_DIST/200.html" ]]; then
  echo "[bili2vrchat] 警告：前端尚未建置（缺少 frontend/.output/public）" >&2
  echo "  請先執行：cd frontend && bun install && bun run generate" >&2
  echo "  （需安裝 bun：https://bun.sh）" >&2
fi

exec uv run app.py
