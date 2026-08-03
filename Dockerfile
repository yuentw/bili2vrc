FROM oven/bun:1-bookworm-slim AS frontend-build
WORKDIR /frontend
COPY frontend/package.json frontend/bun.lock ./
RUN bun install --frozen-lockfile
COPY frontend/ ./
RUN bun run generate

FROM python:3.14-slim-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ffmpeg \
        aria2 \
        nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py config.py hwaccel.py r2.py ./
COPY --from=frontend-build /frontend/.output/public ./frontend/.output/public
COPY cookies/README.md cookies/

RUN mkdir -p temp

ENV HOST=0.0.0.0 \
    PORT=5000 \
    FRONTEND_DIST=/app/frontend/.output/public

EXPOSE 5000

VOLUME ["/app/temp"]

CMD ["python", "app.py"]
