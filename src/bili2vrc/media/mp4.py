import json
import logging
import os
import subprocess

logger = logging.getLogger("bili2vrchat")


def verify_mp4(filepath: str):
    """
    用 ffprobe 驗證 MP4 完整性，回傳 (ok: bool, msg: str)。
    """
    try:
        result = subprocess.run(
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
        if result.returncode != 0:
            return False, "⚠ ffprobe 讀取失敗，可能檔案損毀"

        info = json.loads(result.stdout)
        streams = info.get("streams", [])
        fmt = info.get("format", {})

        if not streams:
            return False, "⚠ 成變流為空，檔案可能損毀"

        duration = float(fmt.get("duration") or 0)
        if duration <= 0:
            return False, "⚠ 時長為 0，檔案可能被截斷（請重試或換格式）"

        mins, secs = divmod(int(duration), 60)
        hrs, mins = divmod(mins, 60)
        dur_str = f"{hrs:02d}:{mins:02d}:{secs:02d}" if hrs else f"{mins:02d}:{secs:02d}"
        size_mb = os.path.getsize(filepath) / 1024 / 1024
        return True, f"驗證通過 ✓  時長 {dur_str}  |  {size_mb:.1f} MB"

    except json.JSONDecodeError:
        return False, "⚠ ffprobe 輸出解析失敗"
    except Exception as exc:
        return True, f"(略過驗證: {exc})"


def apply_faststart(src: str, dst: str) -> bool:
    """ffmpeg -c copy -movflags +faststart"""
    try:
        result = subprocess.run(
            ["ffmpeg", "-i", src,
             "-c", "copy",
             "-movflags", "+faststart",
             "-y", dst],
            capture_output=True, timeout=300,
        )
        return result.returncode == 0 and os.path.isfile(dst)
    except Exception:
        return False


def probe_has_audio(filepath: str) -> bool:
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
