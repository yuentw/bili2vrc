#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

IMAGE_NAME="${IMAGE_NAME:-mio9/bili2vrc}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
IMAGE_REF="${IMAGE_NAME}:${IMAGE_TAG}"
BUILD_NUMBER="$(date +%Y%m%d-%H%M%S)"
BUILD_REF="${IMAGE_NAME}:${BUILD_NUMBER}"

PUSH=false
for arg in "$@"; do
  case "${arg}" in
    --push) PUSH=true ;;
    *) echo "[bili2vrchat] Unknown argument: ${arg}" >&2; exit 1 ;;
  esac
done

BUILD_ARGS=(--platform linux/amd64,linux/arm64 --pull -t "${IMAGE_REF}" -t "${BUILD_REF}" .)

echo "[bili2vrchat] Building Docker images: ${IMAGE_REF}, ${BUILD_REF}"
docker buildx build "${BUILD_ARGS[@]}"


if [[ "${PUSH}" == true ]]; then
  echo "[bili2vrchat] Pushing Docker images: ${IMAGE_REF}, ${BUILD_REF}"
  docker push "${IMAGE_REF}"
  docker push "${BUILD_REF}"
else
  echo "[bili2vrchat] Done: ${IMAGE_REF}, ${BUILD_REF}"
fi

echo "Run: docker run --rm -p 5000:5000 -v \"\$(pwd)/temp:/app/temp\" ${IMAGE_REF}"
