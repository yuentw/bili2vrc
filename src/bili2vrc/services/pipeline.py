"""Download → transcode → R2 upload pipeline (runs in background thread)."""

import logging
import os
import queue
import re
import subprocess
import threading
import urllib.parse

from bili2vrc import config
from bili2vrc.constants import YTDLP_JS_ARGS, clamp_playback_speed
from bili2vrc.download.cookies import get_cookie_args
from bili2vrc.download.ytdlp import get_aria2c_cmd, should_use_aria2c
from bili2vrc.media.mp4 import apply_faststart, verify_mp4
from bili2vrc.media.transcode import transcode_video
from bili2vrc.services.process_controller import process_controller
from bili2vrc.storage import r2
from bili2vrc.utils.formatting import format_size
from bili2vrc.utils.platform import detect_platform

logger = logging.getLogger("bili2vrchat")


def run_process(
    url: str,
    format_id: str,
    key_phrase: str,
    ttl: int,
    compat_mode: bool,
    playback_speed: float,
    bitrate_kbps: int,
    encode_quality: str,
    encode_mode: str,
    scale_bitrate_with_speed: bool,
    output_codec: str,
    encode_crf: int | None,
    cookie_path: str | None,
    job_id: str,
    cancel_event: threading.Event,
    event_queue: queue.Queue,
) -> None:
    """在子執行緒中執行；用 event_queue 回傳進度事件"""

    output_path = None
    register_proc = process_controller.register_proc

    def emit(step: str, message: str, **extra):
        logger.info("[%s] %s", step, message)
        event_queue.put({"type": "status", "step": step, "message": message, **extra})

    def emit_error(msg: str):
        logger.error("%s", msg)
        event_queue.put({"type": "error", "message": msg})

    def emit_result(url_str: str):
        logger.info("result url=%s", url_str)
        event_queue.put({"type": "result", "url": url_str})

    def cancelled() -> bool:
        return cancel_event.is_set()

    def abort_if_cancelled() -> bool:
        if cancelled():
            emit_error("已取消")
            return True
        return False

    try:
        logger.info(
            "process start: job=%s url=%s format_id=%s ttl=%s compat=%s speed=%sx mode=%s quality=%s bitrate=%skbps scale_speed=%s",
            job_id, url, format_id, ttl, compat_mode, clamp_playback_speed(playback_speed),
            encode_mode, encode_quality, bitrate_kbps, scale_bitrate_with_speed,
        )
        if abort_if_cancelled():
            return

        emit("info", "取得影片資訊...")
        cookie_args = get_cookie_args(cookie_path)

        id_cmd = ["yt-dlp", "--get-id", "--no-playlist", *YTDLP_JS_ARGS, *cookie_args, url]
        id_result = subprocess.run(
            id_cmd, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=30,
        )
        if abort_if_cancelled():
            return
        video_id = id_result.stdout.strip() or "video"
        video_id = re.sub(r'[\\/:*?"<>|]', "_", video_id)

        output_path = os.path.join(config.TEMP_DIR, f"{video_id}.mp4")
        logger.info("video_id=%s output=%s", video_id, output_path)

        if os.path.isfile(output_path):
            os.remove(output_path)

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
            "--retries", "15",
            "--fragment-retries", "15",
            "--retry-sleep", "3",
            "--fixup", "force",
            *cookie_args,
            "-o", output_path,
            url,
        ]

        if use_aria2:
            aria2c_exe = get_aria2c_cmd()
            dl_cmd += [
                "--external-downloader", aria2c_exe,
                "--external-downloader-args",
                "aria2c:-x 16 -s 16 -k 1M --min-split-size=1M"
                " --max-connection-per-server=16"
                " --retry-wait=3 --max-tries=15",
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

            if "[download]" in line and "%" in line:
                match = re.search(r"([\d.]+)%\s+of\s+([\d.]+\w+)\s+at\s+([\d.]+\w+/s)", line)
                if match:
                    pct, total, speed = match.group(1), match.group(2), match.group(3)
                    emit("download", f"下載中  {pct}%  |  {total}  @  {speed}")
                else:
                    match2 = re.search(r"([\d.]+)%", line)
                    if match2:
                        emit("download", f"下載中  {match2.group(1)}%")
            elif "[Merger]" in line or "Merging formats" in line:
                emit("merge", "合併音訊與影像...")
            elif "has already been downloaded" in line:
                emit("download", "找到暫存檔，略過下載")
            elif "[ffmpeg]" in line:
                emit("merge", "後製處理 (ffmpeg)...")

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

        emit("verify", "驗證影片完整性...")
        verify_ok, verify_msg = verify_mp4(output_path)
        emit("verify", verify_msg)
        if not verify_ok:
            logger.warning("verify failed: %s", verify_msg)

        if abort_if_cancelled():
            return

        speed = clamp_playback_speed(playback_speed)
        needs_transcode = compat_mode or abs(speed - 1.0) > 1e-6
        effective_codec = config.normalize_output_codec(output_codec, compat_mode=compat_mode)

        if needs_transcode:
            if compat_mode and abs(speed - 1.0) > 1e-6:
                emit("reencode", f"VRChat 相容模式 + 時間拉伸 {speed}x...")
            elif compat_mode:
                emit("reencode", "重新編碼為 H.264 VRChat相容模式...")
            else:
                emit("stretch", f"時間拉伸 {speed}x（保留音高）...")

            suffix = "_compat.mp4" if compat_mode else "_stretch.mp4"
            out_path = output_path.replace(".mp4", suffix)
            ok = transcode_video(
                output_path,
                out_path,
                emit,
                output_codec=effective_codec,
                playback_speed=speed,
                bitrate_kbps=bitrate_kbps,
                encode_quality=encode_quality,
                encode_mode=encode_mode,
                encode_crf=encode_crf,
                scale_bitrate_with_speed=scale_bitrate_with_speed,
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

    except Exception as exc:
        logger.exception("process error: %s", exc)
        emit_error(f"意外錯誤：{exc}")

    finally:
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
        event_queue.put(None)
