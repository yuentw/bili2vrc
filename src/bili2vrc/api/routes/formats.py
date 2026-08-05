import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from bili2vrc.api.schemas import FetchFormatsRequest
from bili2vrc.services.format_service import FormatFetchError, fetch_formats

logger = logging.getLogger("bili2vrchat")

router = APIRouter()


@router.post("/fetch-formats")
def fetch_formats_route(body: FetchFormatsRequest):
    try:
        return fetch_formats(body.url, body.cookie_content)
    except FormatFetchError as exc:
        return JSONResponse({"error": exc.message}, status_code=exc.status_code)
