#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

IMAGE_NAME="${IMAGE_NAME:-mio9/bili2vrc}"
IMAGE_TAG="${IMAGE_TAG:-latest}"

show_help() {
  cat <<EOF
Usage: $(basename "$0") [OPTIONS]

Build multi-arch Docker images (linux/amd64, linux/arm64).

Options:
  --push    Push all tags after build
  -h, --help
            Show this help

Environment:
  IMAGE_NAME   Image repository (default: mio9/bili2vrc)
  IMAGE_TAG    Primary tag (default: latest)

Tags applied:
  \${IMAGE_NAME}:\${IMAGE_TAG}
  \${IMAGE_NAME}:YYYYMMDD-HHMMSS
  \${IMAGE_NAME}:\${COMMIT_SHA}   only when git work tree is clean

Examples:
  $(basename "$0")
  $(basename "$0") --push
  IMAGE_NAME=myregistry/bili2vrc IMAGE_TAG=dev $(basename "$0") --push
EOF
}

IMAGE_REF="${IMAGE_NAME}:${IMAGE_TAG}"
BUILD_NUMBER="$(date +%Y%m%d-%H%M%S)"
BUILD_REF="${IMAGE_NAME}:${BUILD_NUMBER}"

IMAGE_TAGS=("${IMAGE_REF}" "${BUILD_REF}")

if git rev-parse --git-dir >/dev/null 2>&1 && [[ -z "$(git status --porcelain)" ]]; then
  COMMIT_SHA="$(git rev-parse HEAD)"
  COMMIT_REF="${IMAGE_NAME}:${COMMIT_SHA}"
  IMAGE_TAGS+=("${COMMIT_REF}")
fi

PUSH=false
for arg in "$@"; do
  case "${arg}" in
    --push) PUSH=true ;;
    -h|--help) show_help; exit 0 ;;
    *) echo "[bili2vrchat] Unknown argument: ${arg}" >&2; echo "Try '$(basename "$0") --help'." >&2; exit 1 ;;
  esac
done

BUILD_ARGS=(--platform linux/amd64,linux/arm64 --pull)
for tag in "${IMAGE_TAGS[@]}"; do
  BUILD_ARGS+=(-t "${tag}")
done
BUILD_ARGS+=(.)

echo "[bili2vrchat] Building Docker images: ${IMAGE_TAGS[*]}"
docker buildx build "${BUILD_ARGS[@]}"


if [[ "${PUSH}" == true ]]; then
  echo "[bili2vrchat] Pushing Docker images: ${IMAGE_TAGS[*]}"
  for tag in "${IMAGE_TAGS[@]}"; do
    docker push "${tag}"
  done
else
  echo "[bili2vrchat] Done: ${IMAGE_TAGS[*]}"
fi

echo "Run: docker run --rm -p 5000:5000 -v \"\$(pwd)/temp:/app/temp\" ${IMAGE_REF}"
