import json
import logging
import queue

from fastapi import APIRouter
from fastapi.responses import JSONResponse, StreamingResponse

from bili2vrc import config
from bili2vrc.api.schemas import ProcessCancelRequest, ProcessRequest
from bili2vrc.constants import clamp_playback_speed
from bili2vrc.download.cookies import write_cookie_temp_file
from bili2vrc.encoding import hwaccel
from bili2vrc.services.job_queue import job_queue
from bili2vrc.utils.platform import detect_platform, validate_cookie_for_url

logger = logging.getLogger("bili2vrchat")

router = APIRouter()


def _sse_events(event_queue: queue.Queue, job_id: str):
    started = {"type": "started", "job_id": job_id, **job_queue.queue_fields_for(job_id)}
    yield f"data: {json.dumps(started, ensure_ascii=False)}\n\n"
    while True:
        try:
            msg = event_queue.get(timeout=120)
        except queue.Empty:
            yield 'data: {"type":"error","message":"逾時，請重試"}\n\n'
            break
        if msg is None:
            break
        yield f"data: {json.dumps(msg, ensure_ascii=False)}\n\n"


@router.get("/queue-status")
def queue_status_route():
    return job_queue.queue_status()


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
    encode_crf = (
        config.clamp_encode_crf(body.encode_crf, output_codec)
        if body.encode_crf is not None
        else None
    )
    tonemap_hdr = bool(body.tonemap_hdr)
    tonemap_algorithm = hwaccel.normalize_tonemap_algorithm(body.tonemap_algorithm)

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
        "api/process: format_id=%s ttl=%s compat=%s speed=%sx codec=%s mode=%s quality=%s crf=%s bitrate=%skbps scale_speed=%s tonemap_hdr=%s tonemap_algo=%s platform=%s cookie_used=%s",
        format_id, ttl, compat_mode, playback_speed, output_codec, encode_mode, encode_quality, encode_crf, bitrate_kbps,
        scale_bitrate_with_speed, tonemap_hdr, tonemap_algorithm, url_platform, bool(cookie_content),
    )

    status = job_queue.queue_status()
    if status["available_slots"] <= 0:
        max_queue = status["max_queue"]
        total = status["total_count"]
        return JSONResponse(
            {
                "error": f"佇列已滿（{total}/{max_queue}），請稍後再試",
                "queue_count": total,
                "max_queue": max_queue,
            },
            status_code=429,
        )

    event_queue: queue.Queue = queue.Queue()
    job_id = job_queue.enqueue(
        event_queue=event_queue,
        url=url,
        format_id=format_id,
        key_phrase=key_phrase,
        ttl=ttl,
        compat_mode=compat_mode,
        playback_speed=playback_speed,
        bitrate_kbps=bitrate_kbps,
        encode_quality=encode_quality,
        encode_mode=encode_mode,
        scale_bitrate_with_speed=scale_bitrate_with_speed,
        output_codec=output_codec,
        encode_crf=encode_crf,
        tonemap_hdr=tonemap_hdr,
        tonemap_algorithm=tonemap_algorithm,
        cookie_path=cookie_path,
    )
    if not job_id:
        status = job_queue.queue_status()
        return JSONResponse(
            {
                "error": f"佇列已滿（{status['total_count']}/{status['max_queue']}），請稍後再試",
                "queue_count": status["total_count"],
                "max_queue": status["max_queue"],
            },
            status_code=429,
        )

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
    if job_queue.cancel(job_id):
        logger.info("process cancelled: job_id=%s", job_id)
        return {"ok": True}
    return JSONResponse({"ok": False, "error": "找不到進行中的任務"}, status_code=404)
