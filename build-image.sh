#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

IMAGE_NAME="${IMAGE_NAME:-mio9/bili2vrc}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
IMAGE_REF="${IMAGE_NAME}:${IMAGE_TAG}"

echo "[bili2vrchat] Building Docker image: ${IMAGE_REF}"

docker buildx build --platform linux/amd64,linux/arm64 --pull -t "${IMAGE_REF}" .

echo "[bili2vrchat] Done: ${IMAGE_REF}"
echo "Run: docker run --rm -p 5000:5000 -v \"\$(pwd)/temp:/app/temp\" ${IMAGE_REF}"
