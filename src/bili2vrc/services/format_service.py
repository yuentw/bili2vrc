import json
import logging
import subprocess

from bili2vrc.download.cookies import get_cookie_args, temp_cookie_file
from bili2vrc.download.ytdlp import get_ytdlp_js_args
from bili2vrc.utils.formatting import (
    format_duration,
    format_size,
    pick_thumbnail,
    simplify_codec,
)
from bili2vrc.utils.platform import detect_platform, validate_cookie_for_url

logger = logging.getLogger("bili2vrchat")


class FormatFetchError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def fetch_formats(url: str, cookie_content: str | None) -> dict:
    url = (url or "").strip()
    if not url:
        raise FormatFetchError("請輸入影片網址", 400)

    cookie_content = (cookie_content or "").strip() or None
    url_platform = detect_platform(url)
    cookie_error = validate_cookie_for_url(url, cookie_content)
    if cookie_error:
        raise FormatFetchError(cookie_error, 400)

    logger.info(
        "fetch-formats: url=%s platform=%s cookie_used=%s",
        url, url_platform, bool(cookie_content),
    )

    try:
        with temp_cookie_file(cookie_content) as cookie_path:
            cookie_args = get_cookie_args(cookie_path)
            cmd = [
                "yt-dlp", "-J", "--no-playlist",
                *get_ytdlp_js_args(),
                *cookie_args,
                url,
            ]
            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=60,
                )
            except FileNotFoundError:
                logger.error("fetch-formats: yt-dlp not found")
                raise FormatFetchError("找不到 yt-dlp，請先安裝並加入 PATH", 500) from None
            except subprocess.TimeoutExpired:
                logger.error("fetch-formats: timeout url=%s", url)
                raise FormatFetchError("取得格式逾時（60 秒）", 500) from None

            if result.returncode != 0:
                err = result.stderr.strip().splitlines()
                msg = "\n".join(err[-5:]) if err else "yt-dlp 執行失敗"
                logger.warning("fetch-formats failed: %s", msg)
                raise FormatFetchError(msg, 400)

            try:
                info = json.loads(result.stdout)
            except json.JSONDecodeError:
                raise FormatFetchError("無法解析 yt-dlp 輸出", 500) from None
    except ValueError as exc:
        raise FormatFetchError(str(exc), 400) from exc

    raw_formats = info.get("formats", [])
    title = info.get("title", "")
    duration = info.get("duration")
    thumbnail = pick_thumbnail(info)
    uploader = info.get("uploader") or info.get("channel") or ""

    video_formats = []
    for fmt in raw_formats:
        if fmt.get("vcodec", "none") == "none":
            continue
        width = fmt.get("width") or 0
        height = fmt.get("height") or 0
        if not height:
            continue

        size = fmt.get("filesize") or fmt.get("filesize_approx")
        approx = fmt.get("filesize") is None

        raw_bitrate = fmt.get("vbr") or fmt.get("tbr") or 0
        try:
            bitrate_kbps = int(round(float(raw_bitrate)))
        except (TypeError, ValueError):
            bitrate_kbps = 0
        if bitrate_kbps < 1:
            bitrate_kbps = None

        video_formats.append({
            "format_id": fmt.get("format_id", ""),
            "resolution": f"{width}x{height}" if width else f"{height}p",
            "height": height,
            "fps": fmt.get("fps") or 0,
            "dynamic_range": (fmt.get("dynamic_range") or "SDR").upper(),
            "vcodec_raw": fmt.get("vcodec", ""),
            "codec": simplify_codec(fmt.get("vcodec", "")),
            "size": format_size(size),
            "size_bytes": size or 0,
            "size_approx": approx,
            "bitrate_kbps": bitrate_kbps,
            "acodec": fmt.get("acodec", "none"),
            "ext": fmt.get("ext", "mp4"),
        })

    video_formats.sort(key=lambda item: (item["height"], item["size_bytes"]), reverse=True)

    logger.info(
        "fetch-formats ok: title=%r formats=%d duration=%s",
        title, len(video_formats), duration,
    )

    return {
        "title": title,
        "duration": duration,
        "duration_formatted": format_duration(duration),
        "thumbnail": thumbnail,
        "uploader": uploader,
        "formats": video_formats,
        "platform": url_platform,
        "cookie_used": bool(cookie_content),
    }
