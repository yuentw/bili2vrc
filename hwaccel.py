"""
hwaccel.py — ffmpeg H.264 硬體編碼器偵測與參數預設
"""
from __future__ import annotations

import logging
import os
import subprocess
import sys
from dataclasses import dataclass
from functools import lru_cache

import config

logger = logging.getLogger("bili2vrchat.hwaccel")

ENCODER_PRESETS: dict[str, tuple[str, list[str], str | None]] = {
    # name -> (label, video_args after -c:v, optional hw video filter suffix)
    "h264_nvenc": (
        "NVENC (NVIDIA)",
        ["-preset", "p4", "-rc", "vbr", "-cq", "23", "-profile:v", "main"],
        None,
    ),
    "h264_videotoolbox": (
        "VideoToolbox (Apple)",
        ["-profile:v", "main", "-q:v", "65"],
        None,
    ),
    "h264_vaapi": (
        "VAAPI (Intel/AMD)",
        ["-profile:v", "main", "-qp", "23"],
        "format=nv12,hwupload",
    ),
    "h264_qsv": (
        "Quick Sync (Intel)",
        ["-preset", "fast", "-profile:v", "main"],
        None,
    ),
    "h264_amf": (
        "AMF (AMD)",
        ["-quality", "balanced", "-profile:v", "main"],
        None,
    ),
    "libx264": (
        "libx264 (軟體)",
        ["-preset", "fast", "-crf", "18", "-profile:v", "main", "-level:v", "4.1"],
        None,
    ),
}

PLATFORM_CANDIDATES: dict[str, list[str]] = {
    "darwin": ["h264_videotoolbox"],
    "win32": ["h264_nvenc", "h264_qsv", "h264_amf"],
    "linux": ["h264_nvenc", "h264_vaapi", "h264_qsv"],
}


@dataclass(frozen=True)
class VideoEncoder:
    name: str
    label: str
    video_args: list[str]
    hw_video_filter: str | None = None
    fallback: bool = False


def _platform_key() -> str:
    if sys.platform == "darwin":
        return "darwin"
    if sys.platform == "win32":
        return "win32"
    return "linux"


def _list_ffmpeg_encoders() -> set[str]:
    try:
        result = subprocess.run(
            ["ffmpeg", "-hide_banner", "-encoders"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return set()

    if result.returncode != 0:
        return set()

    encoders: set[str] = set()
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0].startswith("V"):
            encoders.add(parts[1])
    return encoders


def _encoder_available(name: str, available: set[str]) -> bool:
    if name not in available:
        return False
    if name == "h264_vaapi" and not os.path.exists("/dev/dri/renderD128"):
        return False
    return True


def _smoke_test_encoder(name: str, video_args: list[str], hw_video_filter: str | None) -> bool:
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel", "error",
        "-f", "lavfi",
        "-i", "testsrc2=duration=0.1:size=320x240:rate=1",
    ]
    if hw_video_filter:
        cmd += ["-vf", hw_video_filter]
    cmd += ["-c:v", name, *video_args, "-frames:v", "1", "-f", "null", "-"]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _make_encoder(name: str, *, fallback: bool = False) -> VideoEncoder:
    label, video_args, hw_video_filter = ENCODER_PRESETS[name]
    return VideoEncoder(
        name=name,
        label=label,
        video_args=list(video_args),
        hw_video_filter=hw_video_filter,
        fallback=fallback,
    )


def detect_video_encoder() -> VideoEncoder:
    forced = (config.HW_ENCODER or "auto").strip().lower()
    if forced and forced != "auto":
        if forced in ENCODER_PRESETS:
            logger.info("encoder forced: %s", forced)
            return _make_encoder(forced, fallback=(forced == "libx264"))
        logger.warning("unknown HW_ENCODER=%s, falling back to libx264", forced)
        return _make_encoder("libx264", fallback=True)

    available = _list_ffmpeg_encoders()
    candidates = PLATFORM_CANDIDATES.get(_platform_key(), [])
    logger.debug("probing encoders: platform=%s candidates=%s", _platform_key(), candidates)
    for name in candidates:
        if not _encoder_available(name, available):
            logger.debug("encoder skip (unavailable): %s", name)
            continue
        label, video_args, hw_video_filter = ENCODER_PRESETS[name]
        if _smoke_test_encoder(name, video_args, hw_video_filter):
            logger.info("encoder selected: %s (%s)", name, label)
            return _make_encoder(name)
        logger.debug("encoder smoke test failed: %s", name)

    logger.info("encoder fallback: libx264 (software)")
    return _make_encoder("libx264", fallback=True)


def software_encoder() -> VideoEncoder:
    return _make_encoder("libx264", fallback=True)


@lru_cache(maxsize=1)
def get_video_encoder() -> VideoEncoder:
    return detect_video_encoder()
