import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from bili2vrc import config
from bili2vrc.api.router import api_router
from bili2vrc.encoding import hwaccel
from bili2vrc.logging_setup import setup_logging
from bili2vrc.services.cleanup import start_r2_cleanup_thread
from bili2vrc.web.middleware import PermissionsPolicyMiddleware
from bili2vrc.web.static import resolve_frontend_file, warn_if_frontend_missing

logger = logging.getLogger("bili2vrchat")


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    encoder = hwaccel.get_video_encoder()
    logger.info("video encoder: %s (%s)", encoder.label, encoder.name)
    warn_if_frontend_missing()
    start_r2_cleanup_thread()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="bili2vrc", lifespan=lifespan)
    app.add_middleware(PermissionsPolicyMiddleware)
    app.include_router(api_router, prefix="/api")

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str = ""):
        response = resolve_frontend_file(full_path)
        if response is None:
            raise HTTPException(status_code=404)
        return response

    return app


app = create_app()


def run() -> None:
    setup_logging()
    logger.info("listening on http://%s:%s", config.HOST, config.PORT)
    uvicorn.run(
        "bili2vrc.main:app",
        host=config.HOST,
        port=config.PORT,
        log_level=config.LOG_LEVEL.lower(),
    )


if __name__ == "__main__":
    run()
