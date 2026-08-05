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
