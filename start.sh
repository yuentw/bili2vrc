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

ensure_bun() {
  if command -v bun >/dev/null 2>&1; then
    export PATH="$ROOT/.bun/bin:$PATH"
    return 0
  fi

  if [[ -x "$ROOT/.bun/bin/bun" ]]; then
    export PATH="$ROOT/.bun/bin:$PATH"
    return 0
  fi

  echo "[bili2vrchat] 未找到 bun，正在安裝到 .bun ..."
  export BUN_INSTALL="$ROOT/.bun"

  if command -v curl >/dev/null 2>&1; then
    curl -fsSL https://bun.sh/install | bash
  else
    echo "[bili2vrchat] 無法安裝 bun：需要 curl。" >&2
    echo "  手動安裝：https://bun.sh" >&2
    exit 1
  fi

  export PATH="$ROOT/.bun/bin:$PATH"
  if ! command -v bun >/dev/null 2>&1; then
    echo "[bili2vrchat] 安裝後仍找不到 bun。" >&2
    echo "  手動安裝：https://bun.sh" >&2
    exit 1
  fi
  echo "[bili2vrchat] bun 已安裝。"
}

ensure_frontend() {
  local dist="$ROOT/frontend/.output/public"
  if [[ -f "$dist/index.html" || -f "$dist/200.html" ]]; then
    return 0
  fi

  echo "[bili2vrchat] 前端尚未建置，正在建置 ..."
  (
    cd "$ROOT/frontend"
    bun install
    bun run generate
  )

  if [[ ! -f "$dist/index.html" && ! -f "$dist/200.html" ]]; then
    echo "[bili2vrchat] 建置完成但仍缺少 frontend/.output/public。" >&2
    exit 1
  fi
}

ensure_uv
update_ytdlp() {
  echo "[bili2vrchat] 正在檢查 yt-dlp ..."
  if uv lock --upgrade-package yt-dlp && uv sync; then
    local version
    version="$(uv run --no-sync yt-dlp --version 2>/dev/null || true)"
    if [[ -n "$version" ]]; then
      echo "[bili2vrchat] yt-dlp ${version}"
    fi
  else
    echo "[bili2vrchat] yt-dlp 更新失敗，沿用現有版本。"
  fi
}
update_ytdlp
ensure_bun
ensure_frontend

echo "[bili2vrchat] 啟動伺服器 ..."
exec uv run app.py
