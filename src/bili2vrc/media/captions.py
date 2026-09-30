"""YouTube CC → ASS (YouTube player look) for hardsub burn-in."""

import glob
import html
import logging
import os
import re
import subprocess

from bili2vrc import config

logger = logging.getLogger("bili2vrchat")

CAPTION_FONT_SIZE_RATIO = 0.04
CAPTION_MARGIN_RATIO = 0.08
CAPTION_BOX_PADDING_RATIO = 0.008
CAPTION_MIN_FONT_SIZE = 18
# ASS alpha: 00 opaque, FF transparent. 0x40 ≈ 75% opaque black box.
CAPTION_BOX_ALPHA = "40"

_LANG_CODE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,31}$")
_VTT_TIME = re.compile(
    r"(?:(\d+):)?(\d{1,2}):(\d{1,2})[.](\d{1,3})",
)
_TAG = re.compile(r"<[^>]+>")


def extract_caption_tracks(info: dict) -> list[dict]:
    """Manual tracks first; drop automatic tracks that duplicate a manual language."""
    tracks: list[dict] = []
    seen: set[str] = set()
    for automatic, key in ((False, "subtitles"), (True, "automatic_captions")):
        group = info.get(key) or {}
        if not isinstance(group, dict):
            continue
        for lang, entries in group.items():
            code = str(lang or "").strip()
            if not code or code in seen or code == "live_chat":
                continue
            seen.add(code)
            name = code
            if isinstance(entries, list):
                for entry in entries:
                    if isinstance(entry, dict):
                        label = str(entry.get("name") or "").strip()
                        if label:
                            name = label
                            break
            tracks.append({
                "lang": code,
                "name": name,
                "automatic": automatic,
            })
    return tracks


def is_caption_lang(lang: str) -> bool:
    return bool(_LANG_CODE.match(lang or ""))


def ffmpeg_has_subtitles_filter() -> bool:
    try:
        result = subprocess.run(
            ["ffmpeg", "-hide_banner", "-filters"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return " subtitles " in (result.stdout or "")


def probe_video_size(filepath: str) -> tuple[int, int]:
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "quiet",
                "-select_streams", "v:0",
                "-show_entries", "stream=width,height",
                "-of", "csv=p=0",
                filepath,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
        width_text, height_text = (result.stdout or "").strip().split(",")[:2]
        width = int(width_text)
        height = int(height_text)
        if width > 0 and height > 0:
            return width, height
    except (OSError, subprocess.TimeoutExpired, ValueError):
        pass
    return 1920, 1080


def resolve_caption_font() -> tuple[str, str | None]:
    """Return (ASS font name, fonts directory or None)."""
    bundled = os.path.join(config.BASE_DIR, "assets", "fonts")
    if os.path.isdir(bundled):
        for name in sorted(os.listdir(bundled)):
            if name.lower().endswith((".ttf", ".otf", ".ttc")):
                return os.path.splitext(name)[0], bundled

    windows_fonts = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
    jhenghei = os.path.join(windows_fonts, "msjh.ttc")
    if os.path.isfile(jhenghei):
        return "Microsoft JhengHei", windows_fonts

    noto_dirs = (
        "/usr/share/fonts/opentype/noto",
        "/usr/share/fonts/noto-cjk",
        "/usr/share/fonts/truetype/noto",
    )
    for directory in noto_dirs:
        if os.path.isdir(directory):
            return "Noto Sans CJK TC", directory
    return "Arial", None


def download_caption_vtt(
    url: str,
    lang: str,
    dest_dir: str,
    *,
    cookie_args: list[str],
    ytdlp_js_args: list[str],
) -> str | None:
    os.makedirs(dest_dir, exist_ok=True)
    outtmpl = os.path.join(dest_dir, "caption.%(ext)s")
    cmd = [
        "yt-dlp",
        "--skip-download",
        "--write-subs",
        "--write-auto-subs",
        "--sub-langs", lang,
        "--convert-subs", "vtt",
        "--no-playlist",
        *ytdlp_js_args,
        *cookie_args,
        "-o", outtmpl,
        url,
    ]
    try:
        subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=90,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.warning("caption download failed: %s", exc)
        return None

    matches = sorted(glob.glob(os.path.join(dest_dir, "caption*.vtt")))
    if not matches:
        return None
    wanted = lang.lower()
    for path in matches:
        if wanted in os.path.basename(path).lower():
            return path
    return matches[0]


def write_youtube_style_ass(
    vtt_path: str,
    ass_path: str,
    *,
    play_width: int,
    play_height: int,
) -> bool:
    cues = _collapse_rollups(_parse_vtt(vtt_path))
    if not cues:
        return False
    font_name, _fonts_dir = resolve_caption_font()
    font_size = max(CAPTION_MIN_FONT_SIZE, int(play_height * CAPTION_FONT_SIZE_RATIO))
    margin_v = max(16, int(play_height * CAPTION_MARGIN_RATIO))
    box_pad = max(6, int(play_height * CAPTION_BOX_PADDING_RATIO))
    back = f"&H{CAPTION_BOX_ALPHA}000000"
    header = (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        "WrapStyle: 0\n"
        f"PlayResX: {play_width}\n"
        f"PlayResY: {play_height}\n"
        "ScaledBorderAndShadow: yes\n"
        "\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
        "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: YT,{font_name},{font_size},&H00FFFFFF,&H000000FF,&H00000000,"
        f"{back},0,0,0,0,100,100,0,0,3,{box_pad},0,2,40,40,{margin_v},1\n"
        "\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )
    lines = [header]
    for start, end, text in cues:
        if end <= start:
            continue
        lines.append(
            f"Dialogue: 0,{_ass_time(start)},{_ass_time(end)},YT,,0,0,0,,{_ass_text(text)}\n"
        )
    with open(ass_path, "w", encoding="utf-8-sig", newline="\n") as handle:
        handle.writelines(lines)
    return True


def ffmpeg_subtitles_filter(ass_path: str) -> str:
    _font_name, fonts_dir = resolve_caption_font()
    filt = f"subtitles={_escape_filter_path(ass_path)}"
    if fonts_dir:
        filt += f":fontsdir={_escape_filter_path(fonts_dir)}"
    return filt


def _escape_filter_path(path: str) -> str:
    normalized = os.path.abspath(path).replace("\\", "/")
    return (
        normalized
        .replace("\\", r"\\")
        .replace(":", r"\:")
        .replace("'", r"\'")
        .replace(",", r"\,")
        .replace("[", r"\[")
        .replace("]", r"\]")
    )


def _parse_vtt(path: str) -> list[tuple[float, float, str]]:
    try:
        with open(path, encoding="utf-8-sig", errors="replace") as handle:
            raw = handle.read()
    except OSError:
        return []
    raw = raw.replace("\r\n", "\n").replace("\r", "\n")
    cues: list[tuple[float, float, str]] = []
    for block in re.split(r"\n\s*\n", raw):
        lines = [line.strip() for line in block.split("\n") if line.strip()]
        arrow = next((index for index, line in enumerate(lines) if "-->" in line), None)
        if arrow is None:
            continue
        timing = lines[arrow]
        start_raw, end_raw = timing.split("-->", 1)
        start = _vtt_seconds(start_raw)
        end = _vtt_seconds(end_raw.split()[0] if end_raw.split() else "")
        if start is None or end is None:
            continue
        text = _clean_cue_text("\n".join(lines[arrow + 1 :]))
        if text:
            cues.append((start, end, text))
    return cues


def _collapse_rollups(cues: list[tuple[float, float, str]]) -> list[tuple[float, float, str]]:
    """YouTube auto-captions emit growing overlapping lines; keep the longer one."""
    if not cues:
        return []
    ordered = sorted(cues, key=lambda cue: cue[0])
    merged: list[list] = [[ordered[0][0], ordered[0][1], ordered[0][2]]]
    for start, end, text in ordered[1:]:
        prev = merged[-1]
        prev_flat = prev[2].replace("\n", " ")
        flat = text.replace("\n", " ")
        overlaps = start < prev[1] - 0.05
        if overlaps and (prev_flat in flat or flat in prev_flat):
            if len(flat) >= len(prev_flat):
                prev[2] = text
            prev[1] = max(prev[1], end)
            continue
        merged.append([start, end, text])
    return [(item[0], item[1], item[2]) for item in merged]


def _clean_cue_text(text: str) -> str:
    cleaned = _TAG.sub("", text)
    cleaned = html.unescape(cleaned)
    lines = [" ".join(line.split()) for line in cleaned.split("\n")]
    lines = [line for line in lines if line]
    return "\n".join(lines).strip()


def _vtt_seconds(raw: str) -> float | None:
    match = _VTT_TIME.search(raw.strip())
    if not match:
        return None
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2))
    seconds = int(match.group(3))
    millis = int((match.group(4) + "000")[:3])
    return hours * 3600 + minutes * 60 + seconds + millis / 1000


def _ass_time(seconds: float) -> str:
    if seconds < 0:
        seconds = 0
    total_cs = int(round(seconds * 100))
    cs = total_cs % 100
    total_s = total_cs // 100
    secs = total_s % 60
    minutes = (total_s // 60) % 60
    hours = total_s // 3600
    return f"{hours}:{minutes:02d}:{secs:02d}.{cs:02d}"


def _ass_text(text: str) -> str:
    escaped = (
        text.replace("\\", r"\\")
        .replace("{", r"\{")
        .replace("}", r"\}")
    )
    return escaped.replace("\n", r"\N")
