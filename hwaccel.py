"""
hwaccel.py — ffmpeg H.264 硬體編碼器偵測與參數預設
"""
from __future__ import annotations

import logging
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from functools import lru_cache

import config

logger = logging.getLogger("bili2vrchat.hwaccel")

# Even size + 8-bit so HW encoders accept most Bilibili sources (10-bit / odd res).
VIDEO_FORMAT_FILTER = "scale=trunc(iw/2)*2:trunc(ih/2)*2,format=yuv420p"
# QSV prefers NV12 system-memory frames (avoids fragile hwupload on Windows).
QSV_FORMAT_FILTER = "scale=trunc(iw/2)*2:trunc(ih/2)*2,format=nv12"
# QSV rejects many fractional / intermediate rates (e.g. 45fps after 1.5x on 30fps).
QSV_SAFE_FPS = (24, 25, 30, 50, 60)

ENCODER_PRESETS: dict[str, tuple[str, list[str], str | None]] = {
    # name -> (label, video_args after -c:v, optional extra vf after format normalize)
    "h264_nvenc": (
        "NVENC (NVIDIA)",
        ["-preset", "p4", "-rc", "vbr", "-cq", "23", "-profile:v", "main", "-b:v", "0"],
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
        ["-global_quality", "23", "-look_ahead", "0", "-profile:v", "main"],
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
    # Prefer NVIDIA when both exist; force Intel with HW_ENCODER=h264_qsv
    "win32": ["h264_nvenc", "h264_qsv", "h264_amf"],
    "linux": ["h264_nvenc", "h264_vaapi", "h264_qsv"],
}

PLATFORM_HWACCEL_DECODE: dict[str, list[str]] = {
    "darwin": ["-hwaccel", "videotoolbox"],
    "win32": ["-hwaccel", "d3d11va"],
    "linux": ["-hwaccel", "auto"],
}

# Windows QSV: bind oneVPL/MFX to D3D11 (required on recent Intel + ffmpeg).
QSV_INIT_CANDIDATES: list[list[str]] = [
    ["-init_hw_device", "qsv=hw,child_device_type=d3d11va", "-filter_hw_device", "hw"],
    ["-init_hw_device", "d3d11va=hw,vendor=0x8086", "-init_hw_device", "qsv=hw@hw", "-filter_hw_device", "hw"],
    ["-init_hw_device", "d3d11va=hw", "-init_hw_device", "qsv=hw@hw", "-filter_hw_device", "hw"],
    ["-init_hw_device", "qsv=hw", "-filter_hw_device", "hw"],
    [],  # last resort: encoder creates its own session
]


def _platform_candidates(gpus: list[str]) -> list[str]:
    """Order encoder probes by installed GPUs (Intel-only → QSV first)."""
    base = list(PLATFORM_CANDIDATES.get(_platform_key(), []))
    intel = has_intel_gpu(gpus)
    nvidia = has_nvidia_gpu(gpus)
    if _platform_key() == "win32":
        if intel and not nvidia:
            preferred = ["h264_qsv", "h264_nvenc", "h264_amf"]
            return [name for name in preferred if name in base] + [n for n in base if n not in preferred]
        if intel and nvidia:
            # Hybrid: NVENC default; set HW_ENCODER=h264_qsv to force Intel
            preferred = ["h264_nvenc", "h264_qsv", "h264_amf"]
            return [name for name in preferred if name in base] + [n for n in base if n not in preferred]
    if _platform_key() == "linux" and intel and not nvidia:
        preferred = ["h264_qsv", "h264_vaapi", "h264_nvenc"]
        return [name for name in preferred if name in base] + [n for n in base if n not in preferred]
    return base


@dataclass(frozen=True)
class VideoEncoder:
    name: str
    label: str
    video_args: list[str]
    hw_video_filter: str | None = None
    fallback: bool = False
    global_args: tuple[str, ...] = ()
    format_filter: str = VIDEO_FORMAT_FILTER


@dataclass
class ProbeResult:
    encoder: VideoEncoder
    available: list[str] = field(default_factory=list)
    smoke_failures: dict[str, str] = field(default_factory=dict)
    gpus: list[str] = field(default_factory=list)
    note: str = ""


def _platform_key() -> str:
    if sys.platform == "darwin":
        return "darwin"
    if sys.platform == "win32":
        return "win32"
    return "linux"


def decode_hwaccel_args(encoder: VideoEncoder | None = None) -> list[str]:
    """
    Args inserted before -i for GPU decode.
    Skip generic d3d11va when encoding with QSV — device init is handled by global_args.
    """
    if encoder and encoder.name == "h264_qsv":
        return []
    return list(PLATFORM_HWACCEL_DECODE.get(_platform_key(), ["-hwaccel", "auto"]))


def list_gpus() -> list[str]:
    """Return OK display adapters (best-effort)."""
    if sys.platform == "win32":
        try:
            result = subprocess.run(
                [
                    "powershell", "-NoProfile", "-Command",
                    "Get-CimInstance Win32_VideoController | "
                    "Where-Object { $_.Status -eq 'OK' } | "
                    "ForEach-Object { $_.Name }",
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=20,
            )
            names = [line.strip() for line in result.stdout.splitlines() if line.strip()]
            if names:
                return names
        except Exception as exc:
            logger.debug("list_gpus powershell failed: %s", exc)
    return []


def has_intel_gpu(gpus: list[str] | None = None) -> bool:
    names = gpus if gpus is not None else list_gpus()
    return any(re.search(r"intel|uhd|iris|arc", name, re.I) for name in names)


def has_nvidia_gpu(gpus: list[str] | None = None) -> bool:
    names = gpus if gpus is not None else list_gpus()
    return any(re.search(r"nvidia|geforce|rtx|quadro", name, re.I) for name in names)


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


def _run_smoke(cmd: list[str]) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=25,
        )
        if result.returncode == 0:
            return True, ""
        err = (result.stderr or result.stdout or "").strip()
        return False, err[-500:] if err else f"exit {result.returncode}"
    except FileNotFoundError:
        return False, "ffmpeg not found"
    except subprocess.TimeoutExpired:
        return False, "smoke test timeout"


def _smoke_test_encoder(encoder: VideoEncoder) -> tuple[bool, str]:
    base = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel", "error",
        *encoder.global_args,
        "-f", "lavfi",
        "-i", "testsrc2=duration=0.2:size=640x360:rate=30",
        "-vf", compose_video_filter(1.0, encoder),
        "-c:v", encoder.name,
        *encoder.video_args,
        "-frames:v", "3",
        "-f", "null",
        "-",
    ]
    return _run_smoke(base)


def _make_encoder(
    name: str,
    *,
    fallback: bool = False,
    global_args: list[str] | None = None,
) -> VideoEncoder:
    label, video_args, hw_video_filter = ENCODER_PRESETS[name]
    format_filter = QSV_FORMAT_FILTER if name == "h264_qsv" else VIDEO_FORMAT_FILTER
    return VideoEncoder(
        name=name,
        label=label,
        video_args=list(video_args),
        hw_video_filter=hw_video_filter,
        fallback=fallback,
        global_args=tuple(global_args or ()),
        format_filter=format_filter,
    )


def _probe_qsv_encoder() -> tuple[VideoEncoder | None, str]:
    """Try several Windows QSV device-init recipes; return first that works."""
    last_err = ""
    for init_args in QSV_INIT_CANDIDATES:
        encoder = _make_encoder("h264_qsv", global_args=list(init_args))
        ok, err = _smoke_test_encoder(encoder)
        if ok:
            logger.info("QSV ok with init=%s", init_args or "(default session)")
            return encoder, ""
        last_err = err
        logger.warning("QSV smoke failed init=%s: %s", init_args or "(default)", err[:200])
    return None, last_err or "QSV smoke test failed"


def detect_video_encoder() -> VideoEncoder:
    return probe_video_encoder().encoder


def probe_video_encoder() -> ProbeResult:
    gpus = list_gpus()
    forced = (config.HW_ENCODER or "auto").strip().lower()
    if forced and forced != "auto":
        if forced not in ENCODER_PRESETS:
            logger.warning("unknown HW_ENCODER=%s, falling back to libx264", forced)
            return ProbeResult(
                encoder=_make_encoder("libx264", fallback=True),
                smoke_failures={forced: "unknown encoder name"},
                gpus=gpus,
                note=f"未知 HW_ENCODER={forced}，已改用軟體編碼",
            )
        if forced == "h264_qsv":
            if sys.platform == "win32" and not has_intel_gpu(gpus):
                note = (
                    "已指定 h264_qsv，但系統未偵測到 Intel GPU。"
                    f"目前顯示卡：{', '.join(gpus) or '（無）'}。"
                    "請在裝置管理員／BIOS 啟用 Intel 內顯，或改 HW_ENCODER=auto。"
                )
                logger.warning(note)
                return ProbeResult(
                    encoder=_make_encoder("libx264", fallback=True),
                    smoke_failures={"h264_qsv": "no Intel GPU adapter"},
                    gpus=gpus,
                    note=note,
                )
            qsv, err = _probe_qsv_encoder()
            if qsv:
                return ProbeResult(encoder=qsv, available=["h264_qsv"], gpus=gpus)
            note = f"已指定 h264_qsv 但初始化失敗：{err}"
            logger.warning(note)
            return ProbeResult(
                encoder=_make_encoder("libx264", fallback=True),
                smoke_failures={"h264_qsv": err},
                gpus=gpus,
                note=note,
            )
        logger.info("encoder forced: %s", forced)
        return ProbeResult(
            encoder=_make_encoder(forced, fallback=(forced == "libx264")),
            available=[forced],
            gpus=gpus,
        )

    available = _list_ffmpeg_encoders()
    candidates = _platform_candidates(gpus)
    listed = [name for name in candidates if _encoder_available(name, available)]
    smoke_failures: dict[str, str] = {}
    note = ""
    if has_intel_gpu(gpus) and has_nvidia_gpu(gpus):
        note = "雙顯卡：預設 NVENC。若要用 Intel 內顯請設 HW_ENCODER=h264_qsv"
    logger.info(
        "probing encoders: platform=%s gpus=%s order=%s",
        _platform_key(), gpus or "(unknown)", candidates,
    )

    for name in candidates:
        if not _encoder_available(name, available):
            continue

        # Only skip when GPU list is non-empty and clearly lacks that vendor.
        # Empty list = detection failed → still probe (important on Intel PCs).
        if name == "h264_qsv" and sys.platform == "win32" and gpus and not has_intel_gpu(gpus):
            smoke_failures[name] = "no Intel GPU adapter in system"
            logger.warning("skip QSV: no Intel adapter in %s", gpus)
            continue

        if name == "h264_nvenc" and sys.platform == "win32" and gpus and not has_nvidia_gpu(gpus):
            smoke_failures[name] = "no NVIDIA GPU adapter in system"
            continue

        if name == "h264_qsv":
            qsv, err = _probe_qsv_encoder()
            if qsv:
                logger.info("encoder selected: h264_qsv (%s)", qsv.label)
                return ProbeResult(
                    encoder=qsv,
                    available=listed,
                    smoke_failures=smoke_failures,
                    gpus=gpus,
                    note=note,
                )
            smoke_failures[name] = err or "QSV init failed"
            logger.warning("encoder smoke test failed: %s — %s", name, smoke_failures[name])
            if not note:
                note = (
                    "Intel Quick Sync 初始化失敗。"
                    "請更新 Intel 顯示驅動，確認 ffmpeg 支援 QSV，"
                    "或設定 HW_ENCODER=h264_qsv 查看詳細錯誤。"
                )
            continue

        encoder = _make_encoder(name)
        ok, err = _smoke_test_encoder(encoder)
        if ok:
            logger.info("encoder selected: %s (%s)", name, encoder.label)
            return ProbeResult(
                encoder=encoder,
                available=listed,
                smoke_failures=smoke_failures,
                gpus=gpus,
                note=note,
            )
        smoke_failures[name] = err or "smoke test failed"
        logger.warning("encoder smoke test failed: %s — %s", name, smoke_failures[name])

    logger.info("encoder fallback: libx264 (software)")
    if not note and smoke_failures:
        note = "硬體編碼皆不可用，已回退軟體 libx264"
    return ProbeResult(
        encoder=_make_encoder("libx264", fallback=True),
        available=listed,
        smoke_failures=smoke_failures,
        gpus=gpus,
        note=note,
    )


def software_encoder() -> VideoEncoder:
    return _make_encoder("libx264", fallback=True)


def probe_video_fps(filepath: str) -> float:
    """Return average frame rate of first video stream, or 0 if unknown."""
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "quiet",
                "-select_streams", "v:0",
                "-show_entries", "stream=avg_frame_rate,r_frame_rate",
                "-of", "json",
                filepath,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )
        if result.returncode != 0:
            return 0.0
        streams = json.loads(result.stdout or "{}").get("streams") or []
        if not streams:
            return 0.0
        for key in ("avg_frame_rate", "r_frame_rate"):
            raw = streams[0].get(key) or "0/0"
            if "/" in raw:
                num_s, den_s = raw.split("/", 1)
                num, den = float(num_s), float(den_s)
                if den > 0 and num > 0:
                    return num / den
            else:
                value = float(raw)
                if value > 0:
                    return value
    except Exception as exc:
        logger.debug("probe_video_fps failed: %s", exc)
    return 0.0


def snap_fps_for_encoder(encoder: VideoEncoder, source_fps: float) -> int:
    """Pick an output fps the encoder accepts (especially QSV after setpts)."""
    base = source_fps if source_fps > 1 else 30.0
    if encoder.name != "h264_qsv":
        # Keep near source; clamp to common integer for filter stability
        return max(1, int(round(base)))
    return min(QSV_SAFE_FPS, key=lambda candidate: abs(candidate - base))


def compose_video_filter(
    speed: float,
    encoder: VideoEncoder,
    *,
    source_fps: float | None = None,
) -> str:
    """
    Build video filter chain: optional speed + format + optional hw upload.

    QSV only: after setpts, force a safe fps (24/25/30/50/60). Otherwise NVENC etc.
    keep the effective rate (e.g. 30fps @ 1.5x → ~45fps).
    """
    parts: list[str] = []
    if abs(float(speed) - 1.0) > 1e-6:
        parts.append(f"setpts=PTS/{speed}")
    if encoder.name == "h264_qsv":
        out_fps = snap_fps_for_encoder(encoder, float(source_fps or 30))
        parts.append(f"fps={out_fps}")
    parts.append(encoder.format_filter)
    if encoder.hw_video_filter:
        parts.append(encoder.hw_video_filter)
    return ",".join(parts)


@lru_cache(maxsize=1)
def get_probe_result() -> ProbeResult:
    return probe_video_encoder()


@lru_cache(maxsize=1)
def get_video_encoder() -> VideoEncoder:
    return get_probe_result().encoder
