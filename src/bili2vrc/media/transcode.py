"""ffmpeg video transcode with optional speed stretch (AV1 / H.264 / H.265)."""

import logging
import os
import re
import subprocess
import threading
import time

from bili2vrc import config
from bili2vrc.constants import clamp_playback_speed
from bili2vrc.encoding import hwaccel
from bili2vrc.media.mp4 import probe_has_audio

logger = logging.getLogger("bili2vrchat")


def _build_atempo_filter(speed: float) -> str:
    """atempo only accepts 0.5–2.0; chain filters + keep A/V sync after stretch."""
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
    parts.append("aresample=async=1:first_pts=0")
    parts.append("asetpts=PTS-STARTPTS")
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


def transcode_video(
    src: str,
    dst: str,
    emit_fn,
    *,
    output_codec: str | None = None,
    playback_speed: float = 1.0,
    bitrate_kbps: int | None = None,
    encode_quality: str | None = None,
    encode_mode: str | None = None,
    encode_crf: int | None = None,
    scale_bitrate_with_speed: bool = True,
    cancel_event: threading.Event | None = None,
    register_proc=None,
) -> bool:
    codec = config.normalize_output_codec(output_codec)
    codec_label = config.OUTPUT_CODEC_LABELS.get(codec, codec.upper())
    speed = clamp_playback_speed(float(playback_speed))
    quality = config.normalize_encode_quality(encode_quality)
    mode = config.normalize_encode_mode(encode_mode)
    base_bitrate = config.clamp_bitrate_kbps(
        bitrate_kbps if bitrate_kbps is not None else config.DEFAULT_BITRATE_KBPS,
    )
    if scale_bitrate_with_speed:
        video_bitrate = config.effective_bitrate_kbps(base_bitrate, speed)
    else:
        video_bitrate = base_bitrate
    if video_bitrate != base_bitrate:
        logger.info(
            "bitrate for speed: base=%skbps × %sx → %skbps (codec=%s mode=%s quality=%s)",
            base_bitrate, speed, video_bitrate, codec, mode, quality,
        )
    elif abs(speed - 1.0) > 1e-6 and not scale_bitrate_with_speed:
        logger.info(
            "bitrate speed scale skipped: %skbps (codec=%s mode=%s quality=%s)",
            base_bitrate, codec, mode, quality,
        )
    has_audio = probe_has_audio(src)
    source_fps = hwaccel.probe_video_fps(src)
    step = "stretch" if abs(speed - 1.0) > 1e-6 else "reencode"
    encoders_to_try = hwaccel.get_encoders_to_try(codec)

    return _transcode_video_try(
        src,
        dst,
        emit_fn,
        output_codec=codec,
        codec_label=codec_label,
        speed=speed,
        has_audio=has_audio,
        source_fps=source_fps,
        step=step,
        encoders=encoders_to_try,
        bitrate_kbps=video_bitrate,
        encode_quality=quality,
        encode_mode=mode,
        encode_crf=encode_crf,
        cancel_event=cancel_event,
        register_proc=register_proc,
    )


def transcode_h264(
    src: str,
    dst: str,
    emit_fn,
    **kwargs,
) -> bool:
    """Backward-compatible wrapper."""
    return transcode_video(src, dst, emit_fn, output_codec="h264", **kwargs)


def _transcode_video_try(
    src: str,
    dst: str,
    emit_fn,
    *,
    output_codec: str,
    codec_label: str,
    speed: float,
    has_audio: bool,
    source_fps: float,
    step: str,
    encoders: list,
    bitrate_kbps: int,
    encode_quality: str,
    encode_mode: str,
    encode_crf: int | None,
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
            emit_msg = f"時間拉伸 {speed}x + {codec_label} ({encoder.label})..."
        else:
            emit_msg = f"重新編碼 {codec_label} ({encoder.label})..."
        emit_fn(step, emit_msg)

        video_filter = hwaccel.compose_video_filter(
            speed, encoder, source_fps=source_fps,
        )
        out_fps = hwaccel.resolve_output_fps(source_fps)
        decode_args = hwaccel.decode_hwaccel_args(encoder)
        cmd = [
            "ffmpeg", "-hide_banner", "-y",
            *encoder.global_args,
            *decode_args,
            "-i", src,
        ]

        speed_changed = abs(speed - 1.0) > 1e-6
        if has_audio and speed_changed:
            filter_graph = (
                f"[0:v]{video_filter}[v];"
                f"[0:a:0]{_build_atempo_filter(speed)}[a]"
            )
            cmd += ["-filter_complex", filter_graph, "-map", "[v]", "-map", "[a]"]
        elif has_audio:
            cmd += ["-vf", video_filter, "-map", "0:v:0", "-map", "0:a:0?"]
        else:
            cmd += ["-vf", video_filter, "-an"]

        video_args = list(
            hwaccel.video_encode_args(
                encoder.name,
                bitrate_kbps,
                encode_quality,
                encode_mode,
                encode_crf,
                output_codec,
            ),
        )
        if speed_changed:
            video_args += ["-bf", "0"]

        cmd += ["-c:v", encoder.name, *video_args]
        if speed_changed or encoder.name.endswith("_qsv"):
            cmd += ["-r", str(out_fps), "-fps_mode", "cfr"]
        if has_audio:
            cmd += ["-c:a", "aac", "-b:a", "192k"]
            if speed_changed:
                cmd += ["-shortest"]
        cmd += ["-avoid_negative_ts", "make_zero", "-movflags", "+faststart", dst]

        logger.info(
            "transcode start: encoder=%s speed=%sx mode=%s quality=%s bitrate=%skbps fps_in=%.3f fps_out=%s audio=%s src=%s",
            encoder.name, speed, encode_mode, encode_quality, bitrate_kbps,
            source_fps or 0, out_fps, has_audio, os.path.basename(src),
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
