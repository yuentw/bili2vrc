#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
ROOT="$(pwd)"

echo "[bili2vrchat] 啟動中..."

ensure_uv() {
  if command -v uv >/dev/null 2>&1; then
    return 0
  fi

  if [[ -x "$ROOT/.uv/uv" ]]; then
    export PATH="$ROOT/.uv:$PATH"
    return 0
  fi

  if [[ -x "$HOME/.local/bin/uv" ]]; then
    export PATH="$HOME/.local/bin:$PATH"
    return 0
  fi

  echo "[bili2vrchat] 未找到 uv，正在安裝到 .uv ..."
  export UV_INSTALL_DIR="$ROOT/.uv"
  export UV_NO_MODIFY_PATH=1

  if command -v curl >/dev/null 2>&1; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
  elif command -v wget >/dev/null 2>&1; then
    wget -qO- https://astral.sh/uv/install.sh | sh
  else
    echo "[bili2vrchat] 無法安裝 uv：需要 curl 或 wget。" >&2
    echo "  手動安裝：https://docs.astral.sh/uv/getting-started/installation/" >&2
    exit 1
  fi

  export PATH="$ROOT/.uv:$PATH"
  if ! command -v uv >/dev/null 2>&1; then
    echo "[bili2vrchat] 安裝後仍找不到 uv。" >&2
    echo "  手動安裝：https://docs.astral.sh/uv/getting-started/installation/" >&2
    exit 1
  fi
  echo "[bili2vrchat] uv 已安裝。"
}

ensure_uv

FRONTEND_DIST="$ROOT/frontend/.output/public"
if [[ ! -f "$FRONTEND_DIST/index.html" && ! -f "$FRONTEND_DIST/200.html" ]]; then
  echo "[bili2vrchat] 警告：前端尚未建置（缺少 frontend/.output/public）" >&2
  echo "  請先執行：cd frontend && bun install && bun run generate" >&2
  echo "  （需安裝 bun：https://bun.sh）" >&2
fi

exec uv run app.py
