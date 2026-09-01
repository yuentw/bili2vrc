"""Resolve ffmpeg/ffprobe binaries for yt-dlp (bundled) vs transcode (optional NVENC override)."""
from __future__ import annotations

import os
import shutil

_BUNDLED_FFMPEG = "/usr/local/bin/ffmpeg-bundled"
_BUNDLED_FFPROBE = "/usr/local/bin/ffprobe-bundled"


def _first_executable(*candidates: str) -> str | None:
    for candidate in candidates:
        if candidate and os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return None


def bundled_ffmpeg_bin() -> str:
    """Static ffmpeg for yt-dlp merge/remux (always runnable in the container)."""
    found = _first_executable(
        os.environ.get("FFMPEG_BUNDLED_BIN", "").strip(),
        _BUNDLED_FFMPEG,
        shutil.which("ffmpeg") or "",
    )
    return found or "ffmpeg"


def bundled_ffprobe_bin() -> str:
    found = _first_executable(
        os.environ.get("FFPROBE_BUNDLED_BIN", "").strip(),
        _BUNDLED_FFPROBE,
        shutil.which("ffprobe") or "",
    )
    return found or "ffprobe"


def transcode_ffmpeg_bin() -> str:
    """ffmpeg for encode/probe; FFMPEG_BIN overrides PATH (e.g. host NVENC mount)."""
    forced = os.environ.get("FFMPEG_BIN", "").strip()
    if forced:
        return forced
    return bundled_ffmpeg_bin()


def transcode_ffprobe_bin() -> str:
    forced = os.environ.get("FFPROBE_BIN", "").strip()
    if forced:
        return forced
    paired = os.environ.get("FFMPEG_BIN", "").strip()
    if paired.endswith("-nvenc"):
        sibling = f"{paired[:-6]}ffprobe-nvenc"
        found = _first_executable(sibling)
        if found:
            return found
    return bundled_ffprobe_bin()


def ytdlp_ffmpeg_location() -> str:
    """Path passed to yt-dlp --ffmpeg-location (bundled static ffmpeg)."""
    return bundled_ffmpeg_bin()


_HOST_LIB_DIR = "/usr/local/lib/ffmpeg-host"


def transcode_subprocess_env() -> dict[str, str]:
    """Env for host-mounted dynamic ffmpeg (prepend LD_LIBRARY_PATH)."""
    env = os.environ.copy()
    extra_paths: list[str] = []
    for chunk in os.environ.get("FFMPEG_LD_LIBRARY_PATH", "").split(":"):
        chunk = chunk.strip()
        if chunk:
            extra_paths.append(chunk)
    if os.environ.get("FFMPEG_BIN", "").strip() and os.path.isdir(_HOST_LIB_DIR):
        if _HOST_LIB_DIR not in extra_paths:
            extra_paths.insert(0, _HOST_LIB_DIR)
    if not extra_paths:
        return env
    existing = env.get("LD_LIBRARY_PATH", "").strip()
    env["LD_LIBRARY_PATH"] = ":".join(extra_paths + ([existing] if existing else []))
    return env
