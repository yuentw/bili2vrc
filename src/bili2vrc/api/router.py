from fastapi import APIRouter

from bili2vrc.api.routes import formats, hwaccel, process

api_router = APIRouter()
api_router.include_router(formats.router)
api_router.include_router(process.router)
api_router.include_router(hwaccel.router)
