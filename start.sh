#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
ROOT="$(pwd)"

echo "[bili2vrchat] 啟動中..."

confirm_install() {
  local prompt="$1"
  printf '%s [y/N] ' "$prompt"
  read -r reply
  case "${reply}" in
    [yY]|[yY][eE][sS]) return 0 ;;
    *)
      echo "[bili2vrchat] 已取消。" >&2
      exit 1
      ;;
  esac
}

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

  confirm_install "[bili2vrchat] 未找到 uv。是否安裝到 .uv？"
  echo "[bili2vrchat] 正在安裝 uv 到 .uv ..."
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

ffmpeg_available() {
  command -v ffmpeg >/dev/null 2>&1 && command -v ffprobe >/dev/null 2>&1
}

ensure_ffmpeg() {
  if ffmpeg_available; then
    return 0
  fi

  if [[ -x "$ROOT/.ffmpeg/bin/ffmpeg" && -x "$ROOT/.ffmpeg/bin/ffprobe" ]]; then
    export PATH="$ROOT/.ffmpeg/bin:$PATH"
    return 0
  fi

  local os arch url
  os="$(uname -s)"
  arch="$(uname -m)"

  if [[ "$os" == "Darwin" ]]; then
    if command -v brew >/dev/null 2>&1; then
      confirm_install "[bili2vrchat] 未找到 ffmpeg。是否用 Homebrew 安裝？"
      echo "[bili2vrchat] 正在用 Homebrew 安裝 ffmpeg ..."
      brew install ffmpeg
      if ffmpeg_available; then
        echo "[bili2vrchat] ffmpeg 已安裝。"
        return 0
      fi
    fi
    echo "[bili2vrchat] 無法自動安裝 ffmpeg。請執行：brew install ffmpeg" >&2
    echo "  手動安裝：https://ffmpeg.org/download.html" >&2
    exit 1
  fi

  case "$arch" in
    x86_64|amd64)
      url="https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linux64-gpl.tar.xz"
      ;;
    aarch64|arm64)
      url="https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linuxarm64-gpl.tar.xz"
      ;;
    *)
      echo "[bili2vrchat] 不支援的架構：${arch}。請手動安裝 ffmpeg。" >&2
      echo "  手動安裝：https://ffmpeg.org/download.html" >&2
      exit 1
      ;;
  esac

  confirm_install "[bili2vrchat] 未找到 ffmpeg。是否下載安裝到 .ffmpeg？"
  echo "[bili2vrchat] 正在安裝 ffmpeg 到 .ffmpeg ..."

  local archive="$ROOT/.ffmpeg-download.tar.xz"
  local extract="$ROOT/.ffmpeg-extract"
  rm -f "$archive"
  rm -rf "$extract"
  mkdir -p "$extract"

  if command -v curl >/dev/null 2>&1; then
    curl -fL --retry 3 -o "$archive" "$url"
  elif command -v wget >/dev/null 2>&1; then
    wget -O "$archive" "$url"
  else
    echo "[bili2vrchat] 無法安裝 ffmpeg：需要 curl 或 wget。" >&2
    echo "  手動安裝：https://ffmpeg.org/download.html" >&2
    exit 1
  fi

  tar -xf "$archive" -C "$extract"

  local ffmpeg_bin
  ffmpeg_bin="$(find "$extract" -type f -name ffmpeg -print -quit)"
  if [[ -z "$ffmpeg_bin" ]]; then
    echo "[bili2vrchat] 下載的壓縮檔中找不到 ffmpeg。" >&2
    exit 1
  fi

  rm -rf "$ROOT/.ffmpeg"
  mkdir -p "$ROOT/.ffmpeg/bin"
  cp -a "$(dirname "$ffmpeg_bin")/." "$ROOT/.ffmpeg/bin/"
  chmod +x "$ROOT/.ffmpeg/bin/ffmpeg" "$ROOT/.ffmpeg/bin/ffprobe"
  export PATH="$ROOT/.ffmpeg/bin:$PATH"

  rm -f "$archive"
  rm -rf "$extract"

  if ! ffmpeg_available; then
    echo "[bili2vrchat] 安裝後仍找不到 ffmpeg。" >&2
    echo "  手動安裝：https://ffmpeg.org/download.html" >&2
    exit 1
  fi
  echo "[bili2vrchat] ffmpeg 已安裝。"
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

  confirm_install "[bili2vrchat] 未找到 bun。是否安裝到 .bun？"
  echo "[bili2vrchat] 正在安裝 bun 到 .bun ..."
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

  confirm_install "[bili2vrchat] 前端尚未建置。是否執行 bun install 與 bun run generate？"
  echo "[bili2vrchat] 正在建置前端 ..."
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
ensure_ffmpeg
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
