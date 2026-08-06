FROM oven/bun:1.3.14-slim AS frontend-build
WORKDIR /frontend
COPY frontend/package.json frontend/bun.lock ./
RUN bun install --frozen-lockfile
COPY frontend/ ./
RUN bun run generate

FROM python:3.14-slim-trixie

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
COPY --from=node:26-bookworm-slim /usr/local/bin/node /usr/local/bin/node
COPY --from=mwader/static-ffmpeg:9.0 /ffmpeg /usr/local/bin/ffmpeg
COPY --from=mwader/static-ffmpeg:9.0 /ffprobe /usr/local/bin/ffprobe

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        aria2 \
        libatomic1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

ENV UV_NO_DEV=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

COPY pyproject.toml uv.lock .python-version ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project

COPY app.py README.md ./
COPY src/bili2vrc/ ./src/bili2vrc/
COPY --from=frontend-build /frontend/.output/public ./frontend/.output/public
COPY cookies/README.md cookies/

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen

RUN mkdir -p temp

ENV HOST=0.0.0.0 \
    PORT=5000 \
    FRONTEND_DIST=/app/frontend/.output/public

EXPOSE 5000

VOLUME ["/app/temp"]

CMD ["uv", "run", "app.py"]
