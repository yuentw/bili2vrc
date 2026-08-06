#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

IMAGE_NAME="${IMAGE_NAME:-mio9/bili2vrc}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
IMAGE_REF="${IMAGE_NAME}:${IMAGE_TAG}"

PUSH=false
for arg in "$@"; do
  case "${arg}" in
    --push) PUSH=true ;;
    *) echo "[bili2vrchat] Unknown argument: ${arg}" >&2; exit 1 ;;
  esac
done

BUILD_ARGS=(--platform linux/amd64,linux/arm64 --pull -t "${IMAGE_REF}" .)
if [[ "${PUSH}" == true ]]; then
  BUILD_ARGS+=(--push)
  echo "[bili2vrchat] Building and pushing Docker image: ${IMAGE_REF}"
else
  echo "[bili2vrchat] Building Docker image: ${IMAGE_REF}"
fi

docker buildx build "${BUILD_ARGS[@]}"

echo "[bili2vrchat] Done: ${IMAGE_REF}"


echo "Run: docker run --rm -p 5000:5000 -v \"\$(pwd)/temp:/app/temp\" ${IMAGE_REF}"
