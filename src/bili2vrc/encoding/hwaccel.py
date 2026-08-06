"""
hwaccel.py — ffmpeg 硬體/軟體編碼器偵測與參數預設（AV1 / H.264 / H.265）
"""
from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from functools import lru_cache

from bili2vrc import config

logger = logging.getLogger("bili2vrchat.hwaccel")

# Even size + 8-bit so HW encoders accept most Bilibili sources (10-bit / odd res).
VIDEO_FORMAT_FILTER = "scale=trunc(iw/2)*2:trunc(ih/2)*2,format=yuv420p"
# QSV prefers NV12 system-memory frames (avoids fragile hwupload on Windows).
QSV_FORMAT_FILTER = "scale=trunc(iw/2)*2:trunc(ih/2)*2,format=nv12"
# HDR (PQ/HLG) → SDR BT.709 via libplacebo (supports Mobius / BT.2390 / Hable).
TONEMAP_ALGORITHMS = ("mobius", "bt.2390", "hable")
DEFAULT_TONEMAP_ALGORITHM = "mobius"
TONEMAP_ALGORITHM_LABELS = {
    "mobius": "Mobius",
    "bt.2390": "BT.2390",
    "hable": "Hable",
}


def hdr_tonemap_filter(algorithm: str | None = None) -> str:
    algo = normalize_tonemap_algorithm(algorithm)
    return (
        f"libplacebo=tonemapping={algo}:"
        "colorspace=bt709:color_primaries=bt709:color_trc=bt709"
    )


def normalize_tonemap_algorithm(algorithm: str | None = None) -> str:
    key = str(algorithm or DEFAULT_TONEMAP_ALGORITHM).strip().lower()
    aliases = {
        "bt2390": "bt.2390",
        "bt_2390": "bt.2390",
        "itu-r bt.2390": "bt.2390",
    }
    key = aliases.get(key, key)
    return key if key in TONEMAP_ALGORITHMS else DEFAULT_TONEMAP_ALGORITHM


# Safe constant rates for HW encoders + VRChat / Unity VideoPlayer.
SAFE_OUTPUT_FPS = (24, 25, 30, 50, 60)
QSV_SAFE_FPS = SAFE_OUTPUT_FPS

SOFTWARE_ENCODERS: dict[str, str] = {
    "av1": "libsvtav1",
    "h264": "libx264",
    "h265": "libx265",
}

ENCODER_PRESETS: dict[str, tuple[str, list[str], str | None]] = {
    "av1_nvenc": ("NVENC AV1 (NVIDIA)", [], None),
    "av1_qsv": ("Quick Sync AV1 (Intel)", [], None),
    "av1_amf": ("AMF AV1 (AMD)", [], None),
    "av1_vaapi": ("VAAPI AV1", [], "format=nv12,hwupload"),
    "av1_videotoolbox": ("VideoToolbox AV1 (Apple)", [], None),
    "libsvtav1": ("libsvtav1 (軟體)", [], None),
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
    "hevc_nvenc": ("NVENC HEVC (NVIDIA)", [], None),
    "hevc_qsv": ("Quick Sync HEVC (Intel)", [], None),
    "hevc_amf": ("AMF HEVC (AMD)", [], None),
    "hevc_vaapi": ("VAAPI HEVC", [], "format=nv12,hwupload"),
    "hevc_videotoolbox": ("VideoToolbox HEVC (Apple)", [], None),
    "libx265": ("libx265 (軟體)", [], None),
}

PLATFORM_CANDIDATES_BY_CODEC: dict[str, dict[str, list[str]]] = {
    "av1": {
        "darwin": ["av1_videotoolbox"],
        "win32": ["av1_nvenc", "av1_qsv", "av1_amf"],
        "linux": ["av1_nvenc", "av1_vaapi", "av1_qsv"],
    },
    "h264": {
        "darwin": ["h264_videotoolbox"],
        "win32": ["h264_nvenc", "h264_qsv", "h264_amf"],
        "linux": ["h264_nvenc", "h264_vaapi", "h264_qsv"],
    },
    "h265": {
        "darwin": ["hevc_videotoolbox"],
        "win32": ["hevc_nvenc", "hevc_qsv", "hevc_amf"],
        "linux": ["hevc_nvenc", "hevc_vaapi", "hevc_qsv"],
    },
}

PLATFORM_HWACCEL_DECODE: dict[str, list[str]] = {
    "darwin": ["-hwaccel", "videotoolbox"],
    "win32": ["-hwaccel", "d3d11va"],
    "linux": ["-hwaccel", "auto"],
}

QSV_INIT_CANDIDATES: list[list[str]] = [
    ["-init_hw_device", "qsv=hw,child_device_type=d3d11va", "-filter_hw_device", "hw"],
    ["-init_hw_device", "d3d11va=hw,vendor=0x8086", "-init_hw_device", "qsv=hw@hw", "-filter_hw_device", "hw"],
    ["-init_hw_device", "d3d11va=hw", "-init_hw_device", "qsv=hw@hw", "-filter_hw_device", "hw"],
    ["-init_hw_device", "qsv=hw", "-filter_hw_device", "hw"],
    [],
]


def _codec_for_encoder(name: str) -> str:
    if name in SOFTWARE_ENCODERS.values():
        for codec, sw in SOFTWARE_ENCODERS.items():
            if sw == name:
                return codec
    if name.startswith("av1_"):
        return "av1"
    if name.startswith("hevc_"):
        return "h265"
    return "h264"


def _is_qsv_encoder(name: str) -> bool:
    return name.endswith("_qsv")


def _is_vaapi_encoder(name: str) -> bool:
    return name.endswith("_vaapi")


def _nvenc_preset(quality_key: str) -> str:
    return {
        "high": "p6",
        "balanced": "p5",
        "medium": "p4",
        "small": "p3",
    }.get(quality_key, "p5")


def _x264_preset(quality_key: str) -> str:
    return {
        "high": "slow",
        "balanced": "medium",
        "medium": "fast",
        "small": "veryfast",
    }.get(quality_key, "medium")


def _x265_preset(quality_key: str) -> str:
    return {
        "high": "medium",
        "balanced": "medium",
        "medium": "fast",
        "small": "veryfast",
    }.get(quality_key, "medium")


def _svtav1_preset(quality_key: str) -> str:
    return {
        "high": "4",
        "balanced": "6",
        "medium": "8",
        "small": "10",
    }.get(quality_key, "6")


def _qsv_lookahead(quality_key: str) -> str:
    return "1" if quality_key in ("high", "balanced") else "0"


def _amf_quality(quality_key: str) -> str:
    return "quality" if quality_key == "high" else "balanced"


def video_encode_args(
    encoder_name: str,
    bitrate_kbps: int,
    encode_quality: str | None = None,
    encode_mode: str | None = None,
    encode_crf: int | None = None,
    output_codec: str | None = None,
) -> list[str]:
    """
    Encode args for AV1 / H.264 / H.265 encoders.

    encode_mode=cbr: fixed bitrate (+ quality affects encoder preset / look-ahead).
    encode_mode=vbr: quality (CRF/CQ) with bitrate_kbps as hard maxrate ceiling.
    """
    mode = config.normalize_encode_mode(encode_mode)
    quality_key = config.normalize_encode_quality(encode_quality)
    codec = output_codec or _codec_for_encoder(encoder_name)
    quality = config.encode_quality_params_for_request(quality_key, encode_crf, codec)
    kbps = max(1, int(bitrate_kbps))
    bitrate = f"{kbps}k"
    maxrate = bitrate
    bufsize = f"{kbps * 2}k"
    crf = str(quality["crf"])
    cq = str(quality["cq"])
    vt_q = str(quality["vt_q"])
    nvenc_preset = _nvenc_preset(quality_key)
    x264_preset = _x264_preset(quality_key)
    x265_preset = _x265_preset(quality_key)
    svtav1_preset = _svtav1_preset(quality_key)
    qsv_lookahead = _qsv_lookahead(quality_key)
    amf_quality = _amf_quality(quality_key)
    h264_profile = ["-profile:v", "main"]
    hevc_profile = ["-tag:v", "hvc1"]

    if mode == "cbr":
        if encoder_name == "libx264":
            return [
                "-preset", x264_preset, *h264_profile, "-level:v", "4.1",
                "-b:v", bitrate, "-minrate", bitrate, "-maxrate", maxrate,
                "-bufsize", bufsize, "-x264-params", "nal-hrd=cbr",
            ]
        if encoder_name == "libx265":
            return [
                "-preset", x265_preset, *hevc_profile,
                "-b:v", bitrate, "-minrate", bitrate, "-maxrate", maxrate,
                "-bufsize", bufsize,
            ]
        if encoder_name == "libsvtav1":
            return [
                "-preset", svtav1_preset, "-rc", "1",
                "-b:v", bitrate, "-maxrate", maxrate, "-bufsize", bufsize,
            ]
        if encoder_name in ("h264_nvenc", "hevc_nvenc", "av1_nvenc"):
            # av1_nvenc has no H.264-style -profile:v main
            if encoder_name == "hevc_nvenc":
                profile = hevc_profile
            elif encoder_name == "h264_nvenc":
                profile = h264_profile
            else:
                profile = []
            return [
                "-preset", nvenc_preset, "-rc", "cbr", *profile,
                "-b:v", bitrate, "-minrate", bitrate, "-maxrate", maxrate,
                "-bufsize", bufsize,
            ]
        if encoder_name.endswith("_videotoolbox"):
            profile = h264_profile if encoder_name.startswith("h264_") else []
            return [*profile, "-b:v", bitrate, "-maxrate", maxrate, "-q:v", vt_q]
        if _is_vaapi_encoder(encoder_name):
            profile = h264_profile if encoder_name.startswith("h264_") else []
            return [*profile, "-b:v", bitrate, "-maxrate", maxrate]
        if _is_qsv_encoder(encoder_name):
            profile = h264_profile if encoder_name.startswith("h264_") else []
            return [
                *profile, "-look_ahead", qsv_lookahead,
                "-b:v", bitrate, "-maxrate", maxrate, "-minrate", bitrate,
                "-bufsize", bufsize,
            ]
        if encoder_name.endswith("_amf"):
            profile = h264_profile if encoder_name.startswith("h264_") else []
            # av1_amf uses hqcbr/qvbr, not cbr/vbr
            amf_rc = "hqcbr" if encoder_name == "av1_amf" else "cbr"
            return [
                "-quality", amf_quality, *profile, "-rc", amf_rc,
                "-b:v", bitrate, "-maxrate", maxrate,
            ]
        sw = SOFTWARE_ENCODERS.get(_codec_for_encoder(encoder_name), "libx264")
        return video_encode_args(
            sw, bitrate_kbps, encode_quality, encode_mode, encode_crf, codec,
        )

    target_kbps = config.vbr_target_kbps(kbps, quality_key)
    target = f"{target_kbps}k"

    if encoder_name == "libx264":
        return [
            "-preset", x264_preset, *h264_profile, "-level:v", "4.1",
            "-crf", crf, "-maxrate", maxrate, "-bufsize", bufsize,
        ]
    if encoder_name == "libx265":
        return [
            "-preset", x265_preset, *hevc_profile,
            "-crf", crf, "-maxrate", maxrate, "-bufsize", bufsize,
        ]
    if encoder_name == "libsvtav1":
        return [
            "-preset", svtav1_preset, "-crf", crf,
            "-maxrate", maxrate, "-bufsize", bufsize,
        ]
    if encoder_name in ("h264_nvenc", "hevc_nvenc", "av1_nvenc"):
        # av1_nvenc has no H.264-style -profile:v main
        if encoder_name == "hevc_nvenc":
            profile = hevc_profile
        elif encoder_name == "h264_nvenc":
            profile = h264_profile
        else:
            profile = []
        return [
            "-preset", nvenc_preset, "-rc", "vbr", "-cq", cq, *profile,
            "-b:v", target, "-maxrate", maxrate, "-bufsize", bufsize,
        ]
    if encoder_name.endswith("_videotoolbox"):
        profile = h264_profile if encoder_name.startswith("h264_") else []
        return [*profile, "-b:v", target, "-maxrate", maxrate, "-q:v", vt_q]
    if _is_vaapi_encoder(encoder_name):
        profile = h264_profile if encoder_name.startswith("h264_") else []
        return [*profile, "-b:v", target, "-maxrate", maxrate, "-qp", cq]
    if _is_qsv_encoder(encoder_name):
        profile = h264_profile if encoder_name.startswith("h264_") else []
        return [
            *profile, "-look_ahead", qsv_lookahead,
            "-b:v", target, "-maxrate", maxrate, "-bufsize", bufsize,
        ]
    if encoder_name.endswith("_amf"):
        profile = h264_profile if encoder_name.startswith("h264_") else []
        # av1_amf uses hqcbr/qvbr, not cbr/vbr
        amf_rc = "qvbr" if encoder_name == "av1_amf" else "vbr"
        return [
            "-quality", amf_quality, *profile, "-rc", amf_rc,
            "-b:v", target, "-maxrate", maxrate, "-bufsize", bufsize,
        ]

    sw = SOFTWARE_ENCODERS.get(_codec_for_encoder(encoder_name), "libx264")
    return video_encode_args(
        sw, bitrate_kbps, encode_quality, encode_mode, encode_crf, codec,
    )


def _platform_candidates(gpus: list[str], output_codec: str) -> list[str]:
    """Order encoder probes by installed GPUs (Intel-only → QSV first)."""
    codec = config.normalize_output_codec(output_codec)
    base = list(PLATFORM_CANDIDATES_BY_CODEC.get(codec, {}).get(_platform_key(), []))
    if codec != "h264":
        return base

    intel = has_intel_gpu(gpus)
    nvidia = has_nvidia_gpu(gpus)
    if _platform_key() == "win32":
        if intel and not nvidia:
            preferred = ["h264_qsv", "h264_nvenc", "h264_amf"]
            return [name for name in preferred if name in base] + [n for n in base if n not in preferred]
        if intel and nvidia:
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
    output_codec: str = "h264"


@dataclass
class ProbeResult:
    encoder: VideoEncoder
    output_codec: str = "h264"
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
    """Args inserted before -i for GPU decode."""
    if config.DISABLE_HW_ACCEL:
        return []
    if encoder and _is_qsv_encoder(encoder.name):
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
    if _is_vaapi_encoder(name) and not os.path.exists("/dev/dri/renderD128"):
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
        *video_encode_args(
            encoder.name,
            config.DEFAULT_BITRATE_KBPS,
            config.DEFAULT_ENCODE_QUALITY,
            config.DEFAULT_ENCODE_MODE,
        ),
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
    output_codec: str | None = None,
) -> VideoEncoder:
    label, video_args, hw_video_filter = ENCODER_PRESETS[name]
    format_filter = QSV_FORMAT_FILTER if _is_qsv_encoder(name) else VIDEO_FORMAT_FILTER
    codec = output_codec or _codec_for_encoder(name)
    return VideoEncoder(
        name=name,
        label=label,
        video_args=list(video_args),
        hw_video_filter=hw_video_filter,
        fallback=fallback,
        global_args=tuple(global_args or ()),
        format_filter=format_filter,
        output_codec=codec,
    )


def _probe_qsv_encoder(encoder_name: str) -> tuple[VideoEncoder | None, str]:
    """Try several Windows QSV device-init recipes; return first that works."""
    last_err = ""
    for init_args in QSV_INIT_CANDIDATES:
        encoder = _make_encoder(encoder_name, global_args=list(init_args))
        ok, err = _smoke_test_encoder(encoder)
        if ok:
            logger.info("QSV ok (%s) with init=%s", encoder_name, init_args or "(default session)")
            return encoder, ""
        last_err = err
        logger.warning(
            "QSV smoke failed (%s) init=%s: %s",
            encoder_name, init_args or "(default)", err[:200],
        )
    return None, last_err or "QSV smoke test failed"


def _software_fallback_result(
    output_codec: str,
    *,
    available: list[str] | None = None,
    smoke_failures: dict[str, str] | None = None,
    gpus: list[str] | None = None,
    note: str = "",
) -> ProbeResult:
    sw_name = SOFTWARE_ENCODERS[output_codec]
    return ProbeResult(
        encoder=_make_encoder(sw_name, fallback=True, output_codec=output_codec),
        output_codec=output_codec,
        available=available or [],
        smoke_failures=smoke_failures or {},
        gpus=gpus or [],
        note=note or f"硬體編碼皆不可用，已回退 {sw_name}",
    )


def detect_video_encoder(output_codec: str | None = None) -> VideoEncoder:
    return probe_video_encoder(output_codec).encoder


def probe_video_encoder(output_codec: str | None = None) -> ProbeResult:
    codec = config.normalize_output_codec(output_codec)
    gpus = list_gpus()
    sw_name = SOFTWARE_ENCODERS[codec]

    if config.DISABLE_HW_ACCEL:
        forced = (config.HW_ENCODER or "auto").strip().lower()
        note = "已設定 DISABLE_HW_ACCEL，使用軟體編碼"
        if forced and forced != "auto" and forced != sw_name:
            note = f"{note}（忽略 HW_ENCODER={forced}）"
        logger.info("hw accel disabled: using %s for codec=%s", sw_name, codec)
        return _software_fallback_result(codec, gpus=gpus, note=note)

    forced = (config.HW_ENCODER or "auto").strip().lower()

    if forced and forced != "auto":
        if forced not in ENCODER_PRESETS:
            logger.warning("unknown HW_ENCODER=%s, falling back to %s", forced, sw_name)
            return _software_fallback_result(
                codec,
                smoke_failures={forced: "unknown encoder name"},
                gpus=gpus,
                note=f"未知 HW_ENCODER={forced}，已改用 {sw_name}",
            )
        if _codec_for_encoder(forced) != codec:
            logger.info(
                "HW_ENCODER=%s ignored for output_codec=%s",
                forced, codec,
            )
        elif _is_qsv_encoder(forced):
            if sys.platform == "win32" and not has_intel_gpu(gpus):
                note = (
                    f"已指定 {forced}，但系統未偵測到 Intel GPU。"
                    f"目前顯示卡：{', '.join(gpus) or '（無）'}。"
                )
                logger.warning(note)
                return _software_fallback_result(
                    codec,
                    smoke_failures={forced: "no Intel GPU adapter"},
                    gpus=gpus,
                    note=note,
                )
            qsv, err = _probe_qsv_encoder(forced)
            if qsv:
                return ProbeResult(
                    encoder=qsv,
                    output_codec=codec,
                    available=[forced],
                    gpus=gpus,
                )
            note = f"已指定 {forced} 但初始化失敗：{err}"
            logger.warning(note)
            return _software_fallback_result(
                codec,
                smoke_failures={forced: err},
                gpus=gpus,
                note=note,
            )
        elif _codec_for_encoder(forced) == codec:
            logger.info("encoder forced: %s", forced)
            return ProbeResult(
                encoder=_make_encoder(forced, fallback=(forced == sw_name), output_codec=codec),
                output_codec=codec,
                available=[forced],
                gpus=gpus,
            )

    available = _list_ffmpeg_encoders()
    candidates = _platform_candidates(gpus, codec)
    listed = [name for name in candidates if _encoder_available(name, available)]
    smoke_failures: dict[str, str] = {}
    note = ""
    if codec == "h264" and has_intel_gpu(gpus) and has_nvidia_gpu(gpus):
        note = "雙顯卡：預設 NVENC。若要用 Intel 內顯請設 HW_ENCODER=h264_qsv"
    logger.info(
        "probing encoders: codec=%s platform=%s gpus=%s order=%s",
        codec, _platform_key(), gpus or "(unknown)", candidates,
    )

    for name in candidates:
        if not _encoder_available(name, available):
            continue

        if _is_qsv_encoder(name) and sys.platform == "win32" and gpus and not has_intel_gpu(gpus):
            smoke_failures[name] = "no Intel GPU adapter in system"
            logger.warning("skip QSV: no Intel adapter in %s", gpus)
            continue

        if name.endswith("_nvenc") and sys.platform == "win32" and gpus and not has_nvidia_gpu(gpus):
            smoke_failures[name] = "no NVIDIA GPU adapter in system"
            continue

        if _is_qsv_encoder(name):
            qsv, err = _probe_qsv_encoder(name)
            if qsv:
                logger.info("encoder selected: %s (%s)", name, qsv.label)
                return ProbeResult(
                    encoder=qsv,
                    output_codec=codec,
                    available=listed,
                    smoke_failures=smoke_failures,
                    gpus=gpus,
                    note=note,
                )
            smoke_failures[name] = err or "QSV init failed"
            logger.warning("encoder smoke test failed: %s — %s", name, smoke_failures[name])
            if codec == "h264" and not note:
                note = (
                    "Intel Quick Sync 初始化失敗。"
                    "請更新 Intel 顯示驅動，或設定 HW_ENCODER=h264_qsv 查看詳細錯誤。"
                )
            continue

        encoder = _make_encoder(name, output_codec=codec)
        ok, err = _smoke_test_encoder(encoder)
        if ok:
            logger.info("encoder selected: %s (%s)", name, encoder.label)
            return ProbeResult(
                encoder=encoder,
                output_codec=codec,
                available=listed,
                smoke_failures=smoke_failures,
                gpus=gpus,
                note=note,
            )
        smoke_failures[name] = err or "smoke test failed"
        logger.warning("encoder smoke test failed: %s — %s", name, smoke_failures[name])

    logger.info("encoder fallback: %s (software)", sw_name)
    return _software_fallback_result(
        codec,
        available=listed,
        smoke_failures=smoke_failures,
        gpus=gpus,
        note=note,
    )


def software_encoder(output_codec: str | None = None) -> VideoEncoder:
    codec = config.normalize_output_codec(output_codec)
    return _make_encoder(SOFTWARE_ENCODERS[codec], fallback=True, output_codec=codec)


def get_encoders_to_try(output_codec: str | None = None) -> list[VideoEncoder]:
    codec = config.normalize_output_codec(output_codec)
    primary = get_probe_result(codec).encoder
    encoders = [primary]
    sw = software_encoder(codec)
    if primary.name != sw.name:
        encoders.append(sw)
    return encoders


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


def resolve_output_fps(source_fps: float | None) -> int:
    """Snap source fps to a player-safe constant rate (24/25/30/50/60)."""
    base = float(source_fps) if source_fps and float(source_fps) > 1 else 30.0
    return min(SAFE_OUTPUT_FPS, key=lambda candidate: abs(candidate - base))


def snap_fps_for_encoder(encoder: VideoEncoder, source_fps: float) -> int:
    del encoder
    return resolve_output_fps(source_fps)


def compose_video_filter(
    speed: float,
    encoder: VideoEncoder,
    *,
    source_fps: float | None = None,
    tonemap_hdr: bool = False,
    tonemap_algorithm: str | None = None,
) -> str:
    """Build video filter chain: optional speed + CFR + tonemap + format + optional hw upload."""
    parts: list[str] = []
    out_fps = resolve_output_fps(source_fps)
    if abs(float(speed) - 1.0) > 1e-6:
        parts.append(f"setpts=PTS/{speed}")
        parts.append(f"fps={out_fps}")
        parts.append("setpts=PTS-STARTPTS")
    elif _is_qsv_encoder(encoder.name):
        parts.append(f"fps={out_fps}")
    if tonemap_hdr:
        parts.append(hdr_tonemap_filter(tonemap_algorithm))
    parts.append(encoder.format_filter)
    if encoder.hw_video_filter:
        parts.append(encoder.hw_video_filter)
    return ",".join(parts)


@lru_cache(maxsize=8)
def get_probe_result(output_codec: str = config.DEFAULT_OUTPUT_CODEC) -> ProbeResult:
    return probe_video_encoder(output_codec)


@lru_cache(maxsize=8)
def get_video_encoder(output_codec: str = config.DEFAULT_OUTPUT_CODEC) -> VideoEncoder:
    return get_probe_result(output_codec).encoder
