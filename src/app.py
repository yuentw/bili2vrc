"""
app.py  ─  B站→R2→VRChat 上傳工具後端
"""
import json
import logging
import os
import queue
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
from contextlib import contextmanager

import requests
from flask import Flask, Response, abort, jsonify, request, send_from_directory

import config
import hwaccel
import r2

app = Flask(__name__)
logger = logging.getLogger("bili2vrchat")

PLAYBACK_SPEED_MIN = 0.5
PLAYBACK_SPEED_MAX = 2.0
YTDLP_JS_ARGS = ["--js-runtimes", "node", "--remote-components", "ejs:github"]


class ProcessController:
    """追蹤進行中的下載/轉檔任務，支援取消並終止子進程"""

    def __init__(self):
        self._lock = threading.Lock()
        self._job_id: str | None = None
        self._cancel_event: threading.Event | None = None
        self._procs: list[subprocess.Popen] = []

    def begin(self, job_id: str) -> threading.Event:
        with self._lock:
            self._stop_procs()
            self._job_id = job_id
            self._cancel_event = threading.Event()
            self._procs = []
            return self._cancel_event

    def register_proc(self, proc: subprocess.Popen) -> None:
        with self._lock:
            self._procs.append(proc)

    def cancel(self, job_id: str | None = None) -> bool:
        with self._lock:
            if job_id and self._job_id != job_id:
                return False
            if not self._job_id:
                return False
            if self._cancel_event:
                self._cancel_event.set()
            self._stop_procs()
            return True

    def clear(self, job_id: str) -> None:
        with self._lock:
            if self._job_id == job_id:
                self._job_id = None
                self._cancel_event = None
                self._procs = []

    def _stop_procs(self) -> None:
        for proc in self._procs:
            self._kill_proc(proc)
        self._procs = []

    def _kill_proc(self, proc: subprocess.Popen) -> None:
        try:
            proc.terminate()
            proc.wait(timeout=3)
        except Exception:
            try:
                proc.kill()
                proc.wait(timeout=3)
            except Exception:
                pass


process_controller = ProcessController()


def setup_logging() -> None:
    if logging.getLogger().handlers:
        return
    level = getattr(logging, config.LOG_LEVEL.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


setup_logging()

# ──────────────────────────────────────────────
# 工具函式
# ──────────────────────────────────────────────

def simplify_codec(vcodec: str) -> str:
    """把 yt-dlp 原始 codec 字串縮短成好讀格式"""
    if not vcodec or vcodec == "none":
        return "-"
    v = vcodec.lower()
    if v.startswith("avc") or "h264" in v:
        return "H.264"
    if v.startswith("hev") or v.startswith("hvc") or "h265" in v or "hevc" in v:
        return "H.265"
    if v.startswith("av01") or v.startswith("av1"):
        return "AV1"
    if "vp9" in v:
        return "VP9"
    if "vp8" in v:
        return "VP8"
    # 原始字串截短，最多 16 字元
    return vcodec[:16]


def format_size(size_bytes) -> str:
    """把 bytes 轉成易讀字串"""
    if not size_bytes:
        return "-"
    size_bytes = int(size_bytes)
    if size_bytes >= 1024 ** 3:
        return f"{size_bytes / 1024 ** 3:.2f} GB"
    if size_bytes >= 1024 ** 2:
        return f"{size_bytes / 1024 ** 2:.1f} MB"
    if size_bytes >= 1024:
        return f"{size_bytes / 1024:.0f} KB"
    return f"{size_bytes} B"


def format_duration(seconds) -> str:
    """把秒數轉成 MM:SS 或 HH:MM:SS"""
    if not seconds:
        return "-"
    total = int(seconds)
    hours, rem = divmod(total, 3600)
    mins, secs = divmod(rem, 60)
    if hours:
        return f"{hours}:{mins:02d}:{secs:02d}"
    return f"{mins}:{secs:02d}"


def pick_thumbnail(info: dict) -> str:
    """從 yt-dlp 輸出挑最高解析度縮圖"""
    thumbnails = info.get("thumbnails") or []
    if thumbnails:
        best = max(
            thumbnails,
            key=lambda item: (item.get("width") or 0) * (item.get("height") or 0),
        )
        return best.get("url") or best.get("id") or ""
    return info.get("thumbnail") or ""


def detect_platform(url: str) -> str | None:
    """從影片 URL 判斷平台"""
    try:
        host = urllib.parse.urlparse(url).netloc.lower()
    except Exception:
        return None
    if "bilibili.com" in host or host.endswith("b23.tv"):
        return "bilibili"
    if "youtube.com" in host or host in ("youtu.be",) or host.endswith(".youtu.be"):
        return "youtube"
    return None


def _domain_matches_platform(domain: str, platform: str) -> bool:
    host = domain.lower().lstrip(".")
    if platform == "bilibili":
        return "bilibili.com" in host or host.endswith("b23.tv")
    if platform == "youtube":
        return "youtube.com" in host or host in ("youtu.be",) or host.endswith(".youtu.be")
    return False


def detect_platforms_from_cookie_content(content: str) -> set[str]:
    """從 Netscape cookies.txt 內容解析域名，判斷所屬平台"""
    found: set[str] = set()
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "\t" not in stripped:
            continue
        domain = stripped.split("\t", 1)[0]
        for platform in ("bilibili", "youtube"):
            if _domain_matches_platform(domain, platform):
                found.add(platform)
    return found


def validate_cookie_content(content: bytes) -> str | None:
    """驗證 cookies.txt 內容，成功回傳 None，失敗回傳錯誤訊息"""
    if len(content) > config.COOKIE_MAX_BYTES:
        return f"檔案過大（上限 {config.COOKIE_MAX_BYTES // 1024} KB）"
    if not content.strip():
        return "檔案為空"

    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        try:
            text = content.decode("latin-1")
        except UnicodeDecodeError:
            return "無法讀取為文字檔"

    has_cookie_line = False
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "\t" in stripped:
            has_cookie_line = True
            break
    if not has_cookie_line:
        return "不是有效的 Netscape cookies.txt 格式"
    return None


def validate_cookie_for_url(url: str, cookie_content: str | None) -> str | None:
    """驗證 cookie 內容與 URL 平台是否匹配"""
    if not cookie_content:
        return None

    format_error = validate_cookie_content(cookie_content.encode("utf-8"))
    if format_error:
        return format_error

    url_platform = detect_platform(url)
    if not url_platform:
        return None

    content_platforms = detect_platforms_from_cookie_content(cookie_content)
    if url_platform not in content_platforms:
        label = "Bilibili" if url_platform == "bilibili" else "YouTube"
        return f"Cookie 與網址平台不符（需要 {label} cookie）"
    return None


@contextmanager
def temp_cookie_file(cookie_content: str | None):
    """將 payload cookie 寫入暫存檔，用完自動刪除"""
    if not cookie_content:
        yield None
        return

    format_error = validate_cookie_content(cookie_content.encode("utf-8"))
    if format_error:
        raise ValueError(format_error)

    fd, path = tempfile.mkstemp(suffix=".txt", dir=config.TEMP_DIR)
    try:
        with os.fdopen(fd, "wb") as cookie_file:
            cookie_file.write(cookie_content.encode("utf-8"))
        yield path
    finally:
        if os.path.isfile(path):
            os.remove(path)


def write_cookie_temp_file(cookie_content: str) -> str:
    """寫入暫存 cookie 檔（由呼叫方負責刪除，用於 background thread）"""
    format_error = validate_cookie_content(cookie_content.encode("utf-8"))
    if format_error:
        raise ValueError(format_error)

    fd, path = tempfile.mkstemp(suffix=".txt", dir=config.TEMP_DIR)
    with os.fdopen(fd, "wb") as cookie_file:
        cookie_file.write(cookie_content.encode("utf-8"))
    return path


def get_cookie_args(cookie_path: str | None = None):
    """如果 cookie 檔案存在就帶參數，否則不帶"""
    if cookie_path and os.path.isfile(cookie_path):
        return ["--cookies", cookie_path]
    return []


def _local_aria2c_path() -> str | None:
    """專案根目錄內使用者自行放置的 aria2c（Windows: aria2c.exe，Unix: aria2c）"""
    name = "aria2c.exe" if sys.platform == "win32" else "aria2c"
    path = os.path.join(config.BASE_DIR, name)
    if not os.path.isfile(path):
        return None
    if sys.platform != "win32" and not os.access(path, os.X_OK):
        return None
    return path


def has_aria2c() -> bool:
    """偵測 aria2c：先查專案根目錄，再查 PATH（可由 DISABLE_ARIA2C 關閉）"""
    if config.DISABLE_ARIA2C:
        return False
    if _local_aria2c_path():
        return True
    return shutil.which("aria2c") is not None


def should_use_aria2c(url: str) -> bool:
    """YouTube 不使用 aria2c（與 yt-dlp 外部下載器相容性較差）"""
    if detect_platform(url) == "youtube":
        return False
    return has_aria2c()


def get_aria2c_cmd() -> str:
    """回傳 aria2c 可用的命令名稱（專案根目錄或 PATH）"""
    local = _local_aria2c_path()
    return local if local else "aria2c"


def verify_mp4(filepath: str):
    """
    用 ffprobe 驗證 MP4 完整性，回傳 (ok: bool, msg: str)。
    檢查項目：
      1. codec 可讀取
      2. 實際播放時長 > 0（時長為 0 = 檔案被截斷）
    """
    try:
        r = subprocess.run(
            [
                "ffprobe", "-v", "quiet",
                "-print_format", "json",
                "-show_streams",
                "-show_format",
                filepath,
            ],
            capture_output=True, text=True,
            encoding="utf-8", errors="replace",
            timeout=120,
        )
        if r.returncode != 0:
            return False, "⚠ ffprobe 讀取失敗，可能檔案損毀"

        info = json.loads(r.stdout)
        streams = info.get("streams", [])
        fmt    = info.get("format", {})

        if not streams:
            return False, "⚠ 成變流為空，檔案可能損毀"

        # 檢查播放時長
        duration = float(fmt.get("duration") or 0)
        if duration <= 0:
            return False, "⚠ 時長為 0，檔案可能被截斷（請重試或換格式）"

        mins, secs = divmod(int(duration), 60)
        hrs,  mins = divmod(mins, 60)
        dur_str = f"{hrs:02d}:{mins:02d}:{secs:02d}" if hrs else f"{mins:02d}:{secs:02d}"
        size_mb = os.path.getsize(filepath) / 1024 / 1024
        return True, f"驗證通過 ✓  時長 {dur_str}  |  {size_mb:.1f} MB"

    except json.JSONDecodeError:
        return False, "⚠ ffprobe 輸出解析失敗"
    except Exception as e:
        # ffprobe 不存在或超時，不阻擋上傳
        return True, f"(略過驗證: {e})"


def apply_faststart(src: str, dst: str) -> bool:
    """
    用 ffmpeg -c copy -movflags +faststart 把 MOOV atom 移到檔首。
    改善 VRChat/頁面播放器對造ȷ上水影片的讀取。
    回傳 True = 成功。
    """
    try:
        r = subprocess.run(
            ["ffmpeg", "-i", src,
             "-c", "copy",
             "-movflags", "+faststart",
             "-y", dst],
            capture_output=True, timeout=300
        )
        return r.returncode == 0 and os.path.isfile(dst)
    except Exception:
        return False


def clamp_playback_speed(speed: float) -> float:
    return max(PLAYBACK_SPEED_MIN, min(PLAYBACK_SPEED_MAX, speed))


def _probe_has_audio(filepath: str) -> bool:
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "quiet",
                "-select_streams", "a:0",
                "-show_entries", "stream=index",
                "-of", "csv=p=0",
                filepath,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )
        return result.returncode == 0 and bool(result.stdout.strip())
    except Exception:
        return False


def _build_atempo_filter(speed: float) -> str:
    """atempo only accepts 0.5–2.0; chain filters for safety."""
    speed = clamp_playback_speed(speed)
    parts: list[str] = []
    remaining = speed
    while remaining > 2.0 + 1e-9:
        parts.append("atempo=2.0")
        remaining /= 2.0
    while remaining < 0.5 - 1e-9:
        parts.append("atempo=0.5")
        remaining /= 0.5
    parts.append(f"atempo={remaining:.6g}")
    return ",".join(parts)


def _run_ffmpeg_transcode(
    cmd: list[str],
    *,
    step: str,
    emit_msg: str,
    emit_fn,
    cancel_event: threading.Event | None,
    register_proc,
) -> tuple[bool, str]:
    """Run ffmpeg; return (ok, error_tail)."""
    logger.info("ffmpeg command: %s", " ".join(cmd))
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if register_proc:
            register_proc(proc)
        time_pat = re.compile(r"time=(\d+:\d+:\d+\.\d+)")
        tail: list[str] = []
        for line in proc.stdout:
            if cancel_event and cancel_event.is_set():
                proc.terminate()
                return False, "cancelled"
            line = line.rstrip()
            if line:
                tail.append(line)
                if len(tail) > 40:
                    tail = tail[-40:]
            match = time_pat.search(line)
            if match:
                emit_fn(step, f"{emit_msg}  已處理 {match.group(1)}")
        proc.wait()
        if cancel_event and cancel_event.is_set():
            return False, "cancelled"
        if proc.returncode != 0:
            return False, "\n".join(tail[-15:])
        return True, ""
    except Exception as exc:
        logger.exception("transcode error: %s", exc)
        return False, str(exc)


def transcode_h264(
    src: str,
    dst: str,
    emit_fn,
    *,
    playback_speed: float = 1.0,
    cancel_event: threading.Event | None = None,
    register_proc=None,
) -> bool:
    """
    重新編碼為 H.264，可選時間拉伸（setpts + atempo 保留音高）。
    硬體編碼失敗時自動回退 libx264。
    """
    speed = clamp_playback_speed(float(playback_speed))
    has_audio = _probe_has_audio(src)
    source_fps = hwaccel.probe_video_fps(src)
    step = "stretch" if abs(speed - 1.0) > 1e-6 else "reencode"

    encoders_to_try = [hwaccel.get_video_encoder()]
    if encoders_to_try[0].name != "libx264":
        encoders_to_try.append(hwaccel.software_encoder())

    return _transcode_h264_try(
        src,
        dst,
        emit_fn,
        speed=speed,
        has_audio=has_audio,
        source_fps=source_fps,
        step=step,
        encoders=encoders_to_try,
        cancel_event=cancel_event,
        register_proc=register_proc,
    )


def _transcode_h264_try(
    src: str,
    dst: str,
    emit_fn,
    *,
    speed: float,
    has_audio: bool,
    source_fps: float,
    step: str,
    encoders: list,
    cancel_event: threading.Event | None,
    register_proc,
) -> bool:
    for index, encoder in enumerate(encoders):
        if os.path.isfile(dst):
            try:
                os.remove(dst)
            except OSError:
                pass

        if index > 0:
            emit_fn(step, f"{encoders[index - 1].label} 失敗，改用 {encoder.label}…")

        if abs(speed - 1.0) > 1e-6:
            emit_msg = f"時間拉伸 {speed}x + H.264 ({encoder.label})..."
        else:
            emit_msg = f"重新編碼 H.264 ({encoder.label})..."
        emit_fn(step, emit_msg)

        video_filter = hwaccel.compose_video_filter(
            speed, encoder, source_fps=source_fps,
        )
        decode_args = hwaccel.decode_hwaccel_args(encoder)
        cmd = [
            "ffmpeg", "-hide_banner", "-y",
            *encoder.global_args,
            *decode_args,
            "-i", src,
        ]

        if has_audio and abs(speed - 1.0) > 1e-6:
            filter_graph = (
                f"[0:v]{video_filter}[v];"
                f"[0:a:0]{_build_atempo_filter(speed)}[a]"
            )
            cmd += ["-filter_complex", filter_graph, "-map", "[v]", "-map", "[a]"]
        elif has_audio:
            cmd += ["-vf", video_filter, "-map", "0:v:0", "-map", "0:a:0?"]
        else:
            cmd += ["-vf", video_filter, "-an"]

        cmd += ["-c:v", encoder.name, *encoder.video_args]
        # QSV only: pin safe constant fps (avoids "frame rate unsupported" after setpts)
        if encoder.name == "h264_qsv":
            out_fps = hwaccel.snap_fps_for_encoder(encoder, source_fps or 30)
            cmd += ["-r", str(out_fps)]
        if has_audio:
            cmd += ["-c:a", "aac", "-b:a", "192k"]
        cmd += ["-movflags", "+faststart", dst]

        logger.info(
            "transcode start: encoder=%s speed=%sx fps_in=%.3f audio=%s src=%s",
            encoder.name, speed, source_fps or 0, has_audio, os.path.basename(src),
        )
        ok, err_tail = _run_ffmpeg_transcode(
            cmd,
            step=step,
            emit_msg=emit_msg,
            emit_fn=emit_fn,
            cancel_event=cancel_event,
            register_proc=register_proc,
        )
        if cancel_event and cancel_event.is_set():
            return False
        if ok and os.path.isfile(dst) and os.path.getsize(dst) > 0:
            logger.info("transcode done: %s (%s)", os.path.basename(dst), encoder.name)
            return True

        if decode_args:
            logger.warning(
                "transcode failed with decode accel (%s); retry without: %s",
                encoder.name, err_tail or "(no output)",
            )
            cmd_no_hw = [
                "ffmpeg", "-hide_banner", "-y",
                *encoder.global_args,
                "-i", src,
            ]
            try:
                input_idx = cmd.index("-i")
                cmd_no_hw += cmd[input_idx + 2 :]
            except ValueError:
                cmd_no_hw = None
            if cmd_no_hw:
                if os.path.isfile(dst):
                    try:
                        os.remove(dst)
                    except OSError:
                        pass
                ok2, err_tail2 = _run_ffmpeg_transcode(
                    cmd_no_hw,
                    step=step,
                    emit_msg=emit_msg + " (軟體解碼)",
                    emit_fn=emit_fn,
                    cancel_event=cancel_event,
                    register_proc=register_proc,
                )
                if cancel_event and cancel_event.is_set():
                    return False
                if ok2 and os.path.isfile(dst) and os.path.getsize(dst) > 0:
                    logger.info(
                        "transcode done without decode accel: %s (%s)",
                        os.path.basename(dst), encoder.name,
                    )
                    return True
                err_tail = err_tail2 or err_tail

        logger.error(
            "transcode failed with %s (speed=%s): %s",
            encoder.name, speed, err_tail or "(no output)",
        )

    return False



# ──────────────────────────────────────────────
# 路由：取得格式列表
# ──────────────────────────────────────────────

@app.route("/api/fetch-formats", methods=["POST"])
def fetch_formats():
    data = request.get_json(force=True)
    url = (data.get("url") or "").strip()
    if not url:
        return jsonify({"error": "請輸入影片網址"}), 400

    cookie_content = (data.get("cookie_content") or "").strip() or None
    url_platform = detect_platform(url)
    cookie_error = validate_cookie_for_url(url, cookie_content)
    if cookie_error:
        return jsonify({"error": cookie_error}), 400

    logger.info(
        "fetch-formats: url=%s platform=%s cookie_used=%s",
        url, url_platform, bool(cookie_content),
    )

    try:
        with temp_cookie_file(cookie_content) as cookie_path:
            cookie_args = get_cookie_args(cookie_path)

            cmd = [
                "yt-dlp", "-J", "--no-playlist",
                *YTDLP_JS_ARGS,
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
                return jsonify({"error": "找不到 yt-dlp，請先安裝並加入 PATH"}), 500
            except subprocess.TimeoutExpired:
                logger.error("fetch-formats: timeout url=%s", url)
                return jsonify({"error": "取得格式逾時（60 秒）"}), 500

            if result.returncode != 0:
                err = result.stderr.strip().splitlines()
                msg = "\n".join(err[-5:]) if err else "yt-dlp 執行失敗"
                logger.warning("fetch-formats failed: %s", msg)
                return jsonify({"error": msg}), 400

            try:
                info = json.loads(result.stdout)
            except json.JSONDecodeError:
                return jsonify({"error": "無法解析 yt-dlp 輸出"}), 500
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    raw_formats = info.get("formats", [])
    title = info.get("title", "")
    duration = info.get("duration")
    thumbnail = pick_thumbnail(info)
    uploader = info.get("uploader") or info.get("channel") or ""

    # 只保留有影像的格式
    video_formats = []
    for f in raw_formats:
        if f.get("vcodec", "none") == "none":
            continue
        width = f.get("width") or 0
        height = f.get("height") or 0
        if not height:
            continue

        size = f.get("filesize") or f.get("filesize_approx")
        approx = f.get("filesize") is None  # 如果只有 approx 就加 ~

        video_formats.append({
            "format_id":  f.get("format_id", ""),
            "resolution": f"{width}x{height}" if width else f"{height}p",
            "height":     height,
            "fps":        f.get("fps") or 0,
            "dynamic_range": (f.get("dynamic_range") or "SDR").upper(),
            "vcodec_raw": f.get("vcodec", ""),
            "codec":      simplify_codec(f.get("vcodec", "")),
            "size":       format_size(size),
            "size_bytes": size or 0,
            "size_approx": approx,
            "acodec":     f.get("acodec", "none"),
            "ext":        f.get("ext", "mp4"),
        })

    # 排序：解析度高→低，同解析度按大小高→低
    video_formats.sort(key=lambda x: (x["height"], x["size_bytes"]), reverse=True)

    logger.info(
        "fetch-formats ok: title=%r formats=%d duration=%s",
        title, len(video_formats), duration,
    )

    return jsonify({
        "title":    title,
        "duration": duration,
        "duration_formatted": format_duration(duration),
        "thumbnail": thumbnail,
        "uploader": uploader,
        "formats":  video_formats,
        "platform": url_platform,
        "cookie_used": bool(cookie_content),
    })


# ──────────────────────────────────────────────
# 後台任務：下載 + 上傳
# ──────────────────────────────────────────────

def do_process(url: str, format_id: str, key_phrase: str, ttl: int,
               compat_mode: bool, playback_speed: float, cookie_path: str | None,
               job_id: str, cancel_event: threading.Event, q: queue.Queue):
    """在子執行緒中執行；用 q 回傳進度事件"""

    output_path = None
    register_proc = process_controller.register_proc

    def emit(step: str, message: str, **extra):
        logger.info("[%s] %s", step, message)
        q.put({"type": "status", "step": step, "message": message, **extra})

    def emit_error(msg: str):
        logger.error("%s", msg)
        q.put({"type": "error", "message": msg})

    def emit_result(url_str: str):
        logger.info("result url=%s", url_str)
        q.put({"type": "result", "url": url_str})

    def cancelled() -> bool:
        return cancel_event.is_set()

    def abort_if_cancelled() -> bool:
        if cancelled():
            emit_error("已取消")
            return True
        return False

    try:
        logger.info(
            "process start: job=%s url=%s format_id=%s ttl=%s compat=%s speed=%sx",
            job_id, url, format_id, ttl, compat_mode, clamp_playback_speed(playback_speed),
        )
        if abort_if_cancelled():
            return
        # ── Step 1: 取影片 ID 決定輸出檔名 ──
        emit("info", "取得影片資訊...")
        cookie_args = get_cookie_args(cookie_path)

        id_cmd = ["yt-dlp", "--get-id", "--no-playlist", *YTDLP_JS_ARGS, *cookie_args, url]
        id_result = subprocess.run(
            id_cmd, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=30
        )
        if abort_if_cancelled():
            return
        video_id = id_result.stdout.strip() or "video"
        # 移除危險字元
        video_id = re.sub(r'[\\/:*?"<>|]', "_", video_id)

        output_path = os.path.join(config.TEMP_DIR, f"{video_id}.mp4")
        logger.info("video_id=%s output=%s", video_id, output_path)

        # 如果已有暫存檔先刪除
        if os.path.isfile(output_path):
            os.remove(output_path)

        # ── Step 2: yt-dlp 下載 ──
        use_aria2 = should_use_aria2c(url)
        logger.info("download: aria2c=%s platform=%s format_id=%s", use_aria2, detect_platform(url), format_id)
        if use_aria2:
            emit("download", "偵測到 aria2c，啟用 16 執行緒加速下載...")
        else:
            emit("download", "開始下載...")

        dl_cmd = [
            "yt-dlp",
            "-f", f"{format_id}+bestaudio[ext=m4a]/bestaudio",
            "--merge-output-format", "mp4",
            "--no-playlist",
            "--newline",
            *YTDLP_JS_ARGS,
            # ── 穩定性：重試與修復 ──
            "--retries",          "15",   # 整體重試次數
            "--fragment-retries", "15",   # 單一 DASH 片段重試
            "--retry-sleep",      "3",    # 每次重試等待秒數
            "--fixup",            "force", # 強制修復容器問題（防止撕裂）
            *cookie_args,
            "-o", output_path,
            url,
        ]

        # ── aria2c 多連線 / 內建並發 ──
        if use_aria2:
            aria2c_exe = get_aria2c_cmd()
            dl_cmd += [
                "--external-downloader",      aria2c_exe,
                "--external-downloader-args",
                f"aria2c:-x 16 -s 16 -k 1M --min-split-size=1M"
                f" --max-connection-per-server=16"
                f" --retry-wait=3 --max-tries=15",
            ]
        else:
            dl_cmd += ["--concurrent-fragments", "4"]

        proc = subprocess.Popen(
            dl_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        register_proc(proc)

        for line in proc.stdout:
            if cancelled():
                proc.terminate()
                emit_error("已取消")
                return
            line = line.strip()
            if not line:
                continue

            # 下載進度行
            if "[download]" in line and "%" in line:
                m = re.search(r"([\d.]+)%\s+of\s+([\d.]+\w+)\s+at\s+([\d.]+\w+/s)", line)
                if m:
                    pct, total, speed = m.group(1), m.group(2), m.group(3)
                    emit("download", f"下載中  {pct}%  |  {total}  @  {speed}")
                else:
                    m2 = re.search(r"([\d.]+)%", line)
                    if m2:
                        emit("download", f"下載中  {m2.group(1)}%")

            elif "[Merger]" in line or "Merging formats" in line:
                emit("merge", "合併音訊與影像...")

            elif "has already been downloaded" in line:
                emit("download", "找到暫存檔，略過下載")

            elif "[ffmpeg]" in line:
                emit("merge", "後製處理 (ffmpeg)...")

            # 忽略其他雜訊

        proc.wait()
        if cancelled():
            emit_error("已取消")
            return
        if proc.returncode != 0:
            logger.error("download failed: exit=%s video_id=%s", proc.returncode, video_id)
            emit_error("yt-dlp 下載失敗，請檢查網址或 cookie")
            return

        if not os.path.isfile(output_path):
            emit_error("下載完成但找不到輸出檔案")
            return

        file_size = os.path.getsize(output_path)
        emit("download", f"下載完成  ({format_size(file_size)})")

        if abort_if_cancelled():
            return

        # ── 驗證 MP4 完整性 ──
        emit("verify", "驗證影片完整性...")
        v_ok, v_msg = verify_mp4(output_path)
        emit("verify", v_msg)
        if not v_ok:
            logger.warning("verify failed: %s", v_msg)

        if abort_if_cancelled():
            return

        # ── Step 2.5: faststart / 重新編碼 / 時間拉伸 ──
        speed = clamp_playback_speed(playback_speed)
        needs_transcode = compat_mode or abs(speed - 1.0) > 1e-6

        if needs_transcode:
            if compat_mode and abs(speed - 1.0) > 1e-6:
                emit("reencode", f"VRChat 相容模式 + 時間拉伸 {speed}x...")
            elif compat_mode:
                emit("reencode", "重新編碼為 H.264 VRChat相容模式...")
            else:
                emit("stretch", f"時間拉伸 {speed}x（保留音高）...")

            suffix = "_compat.mp4" if compat_mode else "_stretch.mp4"
            out_path = output_path.replace(".mp4", suffix)
            ok = transcode_h264(
                output_path,
                out_path,
                emit,
                playback_speed=speed,
                cancel_event=cancel_event,
                register_proc=register_proc,
            )
            if cancelled():
                emit_error("已取消")
                return
            if ok:
                os.remove(output_path)
                output_path = out_path
                file_size = os.path.getsize(output_path)
                done_step = "stretch" if abs(speed - 1.0) > 1e-6 and not compat_mode else "reencode"
                emit(done_step, f"處理完成  ({format_size(file_size)})")
            else:
                if abs(speed - 1.0) > 1e-6:
                    logger.error("speed stretch failed; abort upload")
                    emit_error("時間拉伸失敗（未套用倍速）。請重試，或先開 VRChat 相容模式再試")
                    return
                fail_msg = "⚠ 處理失敗，使用原始檔案上傳"
                logger.warning("transcode fallback to original: %s", output_path)
                emit("reencode" if compat_mode else "stretch", fail_msg)
        else:
            # 僅加 faststart（速度快，不重編碼）
            logger.info("faststart: %s", os.path.basename(output_path))
            emit("faststart", "準備頁面播放 (faststart)...")
            fs_path = output_path.replace(".mp4", "_fs.mp4")
            if apply_faststart(output_path, fs_path):
                os.remove(output_path)
                output_path = fs_path
                file_size = os.path.getsize(output_path)
                emit("faststart", f"faststart 完成  ({format_size(file_size)})")
            else:
                emit("faststart", "(faststart 略過，使用原始檔案)")

        if abort_if_cancelled():
            return

        # ── Step 3: 直接上傳至 R2 ──
        emit("presign", "準備 R2 上傳...")

        safe_key = key_phrase.strip() if key_phrase else ""
        filename_encoded = urllib.parse.quote(os.path.basename(output_path))

        try:
            r2_key, key_err = r2.resolve_object_key(safe_key)
            if key_err:
                emit_error(key_err)
                return
            expires_val = r2.expires_value_for_ttl(ttl)
        except RuntimeError as exc:
            emit_error(str(exc))
            return
        except Exception as exc:
            logger.exception("r2 prepare failed")
            emit_error(f"R2 設定錯誤：{exc}")
            return

        logger.info("r2 upload prepare: key=%s size=%s", r2_key, format_size(file_size))

        emit("upload", "上傳至 Cloudflare R2...")

        def on_upload_progress(uploaded: int, total: int) -> None:
            pct = int(uploaded / total * 100) if total > 0 else 0
            emit(
                "upload",
                f"上傳至 R2  {pct}%  ({format_size(uploaded)} / {format_size(total)})",
            )

        try:
            r2.upload_file(
                output_path,
                r2_key,
                filename_encoded,
                expires_val,
                on_progress=on_upload_progress,
                cancel_event=cancel_event,
            )
        except InterruptedError:
            emit_error("已取消")
            return
        except Exception as exc:
            logger.exception("r2 upload failed")
            emit_error(f"上傳失敗：{exc}")
            return

        final_url = r2.build_object_url(r2_key)
        logger.info("process complete: %s", final_url)
        emit("done", f"上傳完成！{r2.ttl_notice(ttl)}")
        emit_result(final_url)

    except Exception as e:
        logger.exception("process error: %s", e)
        emit_error(f"意外錯誤：{e}")

    finally:
        # 清理暫存檔
        if output_path and os.path.isfile(output_path):
            try:
                os.remove(output_path)
                logger.debug("temp removed: %s", output_path)
            except Exception as exc:
                logger.warning("temp cleanup failed: %s (%s)", output_path, exc)
        if cookie_path and os.path.isfile(cookie_path):
            try:
                os.remove(cookie_path)
                logger.debug("cookie temp removed: %s", cookie_path)
            except Exception as exc:
                logger.warning("cookie temp cleanup failed: %s (%s)", cookie_path, exc)
        process_controller.clear(job_id)
        q.put(None)  # sentinel：結束串流


# ──────────────────────────────────────────────
# 路由：SSE 處理串流
# ──────────────────────────────────────────────

@app.route("/api/process", methods=["POST"])
def process():
    data = request.get_json(force=True)
    url        = (data.get("url") or "").strip()
    format_id  = (data.get("format_id") or "").strip()
    key_phrase = data.get("key_phrase", "")
    ttl        = int(data.get("ttl", config.DEFAULT_TTL))
    compat_mode = bool(data.get("compat_mode", False))
    playback_speed = clamp_playback_speed(float(data.get("playback_speed", 1) or 1))
    cookie_content = (data.get("cookie_content") or "").strip() or None

    if not url or not format_id:
        return jsonify({"error": "缺少必要參數"}), 400

    cookie_error = validate_cookie_for_url(url, cookie_content)
    if cookie_error:
        return jsonify({"error": cookie_error}), 400

    url_platform = detect_platform(url)
    cookie_path = None
    if cookie_content:
        try:
            cookie_path = write_cookie_temp_file(cookie_content)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

    logger.info(
        "api/process: format_id=%s ttl=%s compat=%s speed=%sx platform=%s cookie_used=%s",
        format_id, ttl, compat_mode, playback_speed, url_platform, bool(cookie_content),
    )

    q = queue.Queue()
    job_id = secrets.token_hex(8)
    cancel_event = process_controller.begin(job_id)

    t = threading.Thread(
        target=do_process,
        args=(url, format_id, key_phrase, ttl, compat_mode, playback_speed,
              cookie_path, job_id, cancel_event, q),
        daemon=True,
    )
    t.start()

    def generate():
        yield f"data: {json.dumps({'type': 'started', 'job_id': job_id}, ensure_ascii=False)}\n\n"
        while True:
            try:
                msg = q.get(timeout=120)
            except queue.Empty:
                yield "data: {\"type\":\"error\",\"message\":\"逾時，請重試\"}\n\n"
                break
            if msg is None:
                break
            yield f"data: {json.dumps(msg, ensure_ascii=False)}\n\n"

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@app.route("/api/process/cancel", methods=["POST"])
def process_cancel_route():
    data = request.get_json(silent=True) or {}
    job_id = (data.get("job_id") or "").strip() or None
    if process_controller.cancel(job_id):
        logger.info("process cancelled: job_id=%s", job_id)
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": "找不到進行中的任務"}), 404


# ──────────────────────────────────────────────
# 路由：硬體編碼器狀態
# ──────────────────────────────────────────────

@app.route("/api/hwaccel-status")
def hwaccel_status():
    probe = hwaccel.get_probe_result()
    encoder = probe.encoder
    return jsonify({
        "encoder": encoder.name,
        "label": encoder.label,
        "fallback": encoder.fallback,
        "available": probe.available,
        "smoke_failures": probe.smoke_failures,
        "decode_hwaccel": hwaccel.decode_hwaccel_args(encoder),
        "gpus": probe.gpus,
        "note": probe.note,
    })


# ──────────────────────────────────────────────
# R2 過期檔案清理（背景執行）
# ──────────────────────────────────────────────

def _r2_credentials_configured() -> bool:
    return all(
        config.is_set(value)
        for value in (
            config.CF_ACCOUNT_ID,
            config.R2_ACCESS_KEY_ID,
            config.R2_SECRET_ACCESS_KEY,
            config.R2_BUCKET_NAME,
        )
    )


def _run_r2_cleanup() -> None:
    if not _r2_credentials_configured():
        return
    scanned, deleted = r2.purge_expired_objects()
    if deleted:
        logger.info("r2 cleanup: scanned=%s deleted=%s", scanned, deleted)
    else:
        logger.debug("r2 cleanup: scanned=%s deleted=0", scanned)


def start_r2_cleanup_thread() -> None:
    if not config.R2_CLEANUP_ENABLED:
        logger.info("r2 cleanup disabled")
        return
    if not _r2_credentials_configured():
        logger.warning("r2 cleanup skipped: R2 credentials not configured")
        return

    def cleanup_loop() -> None:
        while True:
            try:
                _run_r2_cleanup()
            except Exception:
                logger.exception("r2 cleanup failed")
            time.sleep(config.R2_CLEANUP_INTERVAL)

    thread = threading.Thread(target=cleanup_loop, name="r2-cleanup", daemon=True)
    thread.start()
    logger.info("r2 cleanup thread started (interval=%ss)", config.R2_CLEANUP_INTERVAL)


# ──────────────────────────────────────────────
# 路由：Nuxt 前端靜態檔
# ──────────────────────────────────────────────

def _frontend_fallback_name() -> str:
    dist = config.FRONTEND_DIST
    if os.path.isfile(os.path.join(dist, "200.html")):
        return "200.html"
    return "index.html"


@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_frontend(path: str):
    if path.startswith("api/"):
        abort(404)
    dist = config.FRONTEND_DIST
    if path and os.path.isfile(os.path.join(dist, path)):
        return send_from_directory(dist, path)
    return send_from_directory(dist, _frontend_fallback_name())


def _warn_if_frontend_missing() -> None:
    dist = config.FRONTEND_DIST
    fallback = _frontend_fallback_name()
    if not os.path.isfile(os.path.join(dist, fallback)):
        logger.warning(
            "frontend dist missing (%s); run: cd frontend && bun install && bun run generate",
            dist,
        )


# ──────────────────────────────────────────────
# 入口
# ──────────────────────────────────────────────

if __name__ == "__main__":
    encoder = hwaccel.get_video_encoder()
    logger.info("listening on http://%s:%s", config.HOST, config.PORT)
    logger.info("video encoder: %s (%s)", encoder.label, encoder.name)
    _warn_if_frontend_missing()
    start_r2_cleanup_thread()
    app.run(host=config.HOST, port=config.PORT, threaded=True, debug=False)
