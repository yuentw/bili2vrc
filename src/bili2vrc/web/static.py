import os

from fastapi.responses import FileResponse

from bili2vrc import config


def frontend_fallback_name() -> str:
    dist = config.FRONTEND_DIST
    if os.path.isfile(os.path.join(dist, "200.html")):
        return "200.html"
    return "index.html"


def resolve_frontend_file(path: str) -> FileResponse | None:
    if path.startswith("api/"):
        return None
    dist = config.FRONTEND_DIST
    if path and os.path.isfile(os.path.join(dist, path)):
        return FileResponse(os.path.join(dist, path))
    fallback = os.path.join(dist, frontend_fallback_name())
    if os.path.isfile(fallback):
        return FileResponse(fallback)
    return None


def warn_if_frontend_missing() -> None:
    dist = config.FRONTEND_DIST
    fallback = frontend_fallback_name()
    if not os.path.isfile(os.path.join(dist, fallback)):
        import logging
        logging.getLogger("bili2vrchat").warning(
            "frontend dist missing (%s); run: cd frontend && bun install && bun run generate",
            dist,
        )
