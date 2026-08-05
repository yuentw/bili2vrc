import json
import logging
import queue
import secrets
import threading

from fastapi import APIRouter
from fastapi.responses import JSONResponse, StreamingResponse

from bili2vrc import config
from bili2vrc.api.schemas import ProcessCancelRequest, ProcessRequest
from bili2vrc.constants import clamp_playback_speed
from bili2vrc.download.cookies import write_cookie_temp_file
from bili2vrc.services.pipeline import run_process
from bili2vrc.services.process_controller import process_controller
from bili2vrc.utils.platform import detect_platform, validate_cookie_for_url

logger = logging.getLogger("bili2vrchat")

router = APIRouter()


def _sse_events(event_queue: queue.Queue, job_id: str):
    yield f"data: {json.dumps({'type': 'started', 'job_id': job_id}, ensure_ascii=False)}\n\n"
    while True:
        try:
            msg = event_queue.get(timeout=120)
        except queue.Empty:
            yield 'data: {"type":"error","message":"逾時，請重試"}\n\n'
            break
        if msg is None:
            break
        yield f"data: {json.dumps(msg, ensure_ascii=False)}\n\n"


@router.post("/process")
def process_route(body: ProcessRequest):
    url = (body.url or "").strip()
    format_id = (body.format_id or "").strip()
    key_phrase = body.key_phrase or ""

    requested_ttl = int(body.ttl if body.ttl is not None else config.DEFAULT_TTL)
    ttl = config.effective_ttl(requested_ttl)
    if ttl != requested_ttl:
        logger.info(
            "ttl clamped: requested=%s effective=%s max=%s",
            requested_ttl, ttl, config.MAX_TTL,
        )

    compat_mode = bool(body.compat_mode)
    playback_speed = clamp_playback_speed(float(body.playback_speed or 1))
    bitrate_kbps = config.clamp_bitrate_kbps(
        body.bitrate_kbps if body.bitrate_kbps is not None else config.DEFAULT_BITRATE_KBPS,
    )
    encode_quality = config.normalize_encode_quality(body.encode_quality)
    encode_mode = config.normalize_encode_mode(body.encode_mode)
    if body.scale_bitrate_with_speed is not None:
        scale_bitrate_with_speed = bool(body.scale_bitrate_with_speed)
    else:
        scale_bitrate_with_speed = True
    output_codec = config.normalize_output_codec(body.output_codec, compat_mode=compat_mode)

    cookie_content = (body.cookie_content or "").strip() or None

    if not url or not format_id:
        return JSONResponse({"error": "缺少必要參數"}, status_code=400)

    cookie_error = validate_cookie_for_url(url, cookie_content)
    if cookie_error:
        return JSONResponse({"error": cookie_error}, status_code=400)

    url_platform = detect_platform(url)
    cookie_path = None
    if cookie_content:
        try:
            cookie_path = write_cookie_temp_file(cookie_content)
        except ValueError as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)

    logger.info(
        "api/process: format_id=%s ttl=%s compat=%s speed=%sx codec=%s mode=%s quality=%s bitrate=%skbps scale_speed=%s platform=%s cookie_used=%s",
        format_id, ttl, compat_mode, playback_speed, output_codec, encode_mode, encode_quality, bitrate_kbps,
        scale_bitrate_with_speed, url_platform, bool(cookie_content),
    )

    event_queue: queue.Queue = queue.Queue()
    job_id = secrets.token_hex(8)
    cancel_event = process_controller.begin(job_id)

    thread = threading.Thread(
        target=run_process,
        args=(
            url, format_id, key_phrase, ttl, compat_mode, playback_speed, bitrate_kbps,
            encode_quality, encode_mode, scale_bitrate_with_speed, output_codec, cookie_path, job_id,
            cancel_event, event_queue,
        ),
        daemon=True,
    )
    thread.start()

    return StreamingResponse(
        _sse_events(event_queue, job_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.post("/process/cancel")
def process_cancel_route(body: ProcessCancelRequest):
    job_id = (body.job_id or "").strip() or None
    if process_controller.cancel(job_id):
        logger.info("process cancelled: job_id=%s", job_id)
        return {"ok": True}
    return JSONResponse({"ok": False, "error": "找不到進行中的任務"}, status_code=404)
