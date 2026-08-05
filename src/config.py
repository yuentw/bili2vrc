import os

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def is_set(value: str) -> bool:
    """True when configured / 已設定（非空且非 Fill in 占位提示）."""
    return bool(value) and not value.startswith("Fill in ")


def _with_https(url: str) -> str:
    """Add https:// when scheme is missing (so <video src> is absolute)."""
    cleaned = (url or "").strip().rstrip("/")
    if not cleaned or cleaned.startswith("Fill in "):
        return cleaned
    if cleaned.startswith("//"):
        return "https:" + cleaned
    if not cleaned.lower().startswith(("http://", "https://")):
        return "https://" + cleaned
    return cleaned


# ── Cloudflare R2（S3-compatible API / S3 相容 API）──
# Replace quoted defaults below, or use env vars / 請改下方引號內的值，或改用環境變數
CF_ACCOUNT_ID        = os.environ.get("CF_ACCOUNT_ID", "Fill in CF Account ID here")
R2_ACCESS_KEY_ID     = os.environ.get("R2_ACCESS_KEY_ID", "Fill in R2 Access Key ID here")
R2_SECRET_ACCESS_KEY = os.environ.get("R2_SECRET_ACCESS_KEY", "Fill in R2 Secret Access Key here")
R2_BUCKET_NAME       = os.environ.get("R2_BUCKET_NAME", "Fill in R2 bucket name here")

# Optional public URL (R2.dev or custom domain) / 選填：公開網址（R2.dev 或自訂網域）
# 可只填網域；載入時若無 http(s):// 會自動加上 https://
R2_PUBLIC_BASE_URL = _with_https(
    os.environ.get("R2_PUBLIC_BASE_URL", "Fill in R2 public URL here (optional)")
)

# Expired-object cleanup via metadata expires / 過期檔案清理（依 metadata expires 刪除）
R2_CLEANUP_ENABLED   = os.environ.get("R2_CLEANUP_ENABLED", "1").lower() in ("1", "true", "yes", "on")
R2_CLEANUP_INTERVAL  = int(os.environ.get("R2_CLEANUP_INTERVAL", "3600"))  # seconds / 秒

# ── Local paths / 本地路徑 ──
TEMP_DIR     = os.path.join(BASE_DIR, "temp")
FRONTEND_DIST = os.environ.get(
    "FRONTEND_DIST",
    os.path.join(BASE_DIR, "frontend", ".output", "public"),
)

# ── Defaults / 預設值 ──
MAX_TTL = int(os.environ.get("MAX_TTL", "2592000"))  # max retention (30 days); 0 = no cap / 最長保存；0 = 不限制


def effective_ttl(ttl_seconds: int) -> int:
    """Clamp TTL to MAX_TTL; forever (0) is capped when MAX_TTL > 0."""
    ttl = max(0, int(ttl_seconds))
    if MAX_TTL > 0 and (ttl == 0 or ttl > MAX_TTL):
        return MAX_TTL
    return ttl


DEFAULT_TTL = effective_ttl(int(os.environ.get("DEFAULT_TTL", "604800")))  # 7 days (seconds) / 7 天（秒）
DEFAULT_BITRATE_KBPS = int(os.environ.get("DEFAULT_BITRATE_KBPS", "3000"))
MIN_BITRATE_KBPS = int(os.environ.get("MIN_BITRATE_KBPS", "500"))
MAX_BITRATE_KBPS = int(os.environ.get("MAX_BITRATE_KBPS", "50000"))  # 0 = no cap
# Mild ceiling bump when speeding (bitrate is only a maxrate cap; quality is CRF/CQ).
SPEED_BITRATE_FACTOR = float(os.environ.get("SPEED_BITRATE_FACTOR", "1.0"))

# Lower CRF/CQ/global_quality = higher visual quality (ffmpeg convention).
ENCODE_QUALITY_PRESETS: dict[str, dict[str, int]] = {
    "high": {"crf": 17, "cq": 17, "qsv": 18, "vt_q": 72},
    "balanced": {"crf": 19, "cq": 19, "qsv": 20, "vt_q": 65},
    "medium": {"crf": 22, "cq": 22, "qsv": 23, "vt_q": 55},
    "small": {"crf": 24, "cq": 24, "qsv": 25, "vt_q": 45},
}
DEFAULT_ENCODE_QUALITY = os.environ.get("DEFAULT_ENCODE_QUALITY", "balanced").strip().lower()
if DEFAULT_ENCODE_QUALITY not in ENCODE_QUALITY_PRESETS:
    DEFAULT_ENCODE_QUALITY = "balanced"


def normalize_encode_quality(quality) -> str:
    key = str(quality or DEFAULT_ENCODE_QUALITY).strip().lower()
    return key if key in ENCODE_QUALITY_PRESETS else DEFAULT_ENCODE_QUALITY


def encode_quality_params(quality) -> dict[str, int]:
    return dict(ENCODE_QUALITY_PRESETS[normalize_encode_quality(quality)])


def clamp_bitrate_kbps(bitrate_kbps) -> int:
    """Clamp H.264 video bitrate (kbps) for transcode requests."""
    try:
        bitrate = int(bitrate_kbps)
    except (TypeError, ValueError):
        bitrate = DEFAULT_BITRATE_KBPS
    if bitrate < MIN_BITRATE_KBPS:
        return MIN_BITRATE_KBPS
    if MAX_BITRATE_KBPS > 0 and bitrate > MAX_BITRATE_KBPS:
        return MAX_BITRATE_KBPS
    return bitrate


def effective_bitrate_kbps(bitrate_kbps, playback_speed: float) -> int:
    """
    Bitrate ceiling when speeding: base × speed × SPEED_BITRATE_FACTOR.
    Visual quality is controlled separately via encode_quality (CRF/CQ).
    """
    base = clamp_bitrate_kbps(bitrate_kbps)
    try:
        speed = float(playback_speed)
    except (TypeError, ValueError):
        speed = 1.0
    if abs(speed - 1.0) <= 1e-6:
        return base
    factor = SPEED_BITRATE_FACTOR if SPEED_BITRATE_FACTOR > 0 else 1.0
    return clamp_bitrate_kbps(int(round(base * speed * factor)))
HOST         = os.environ.get("HOST", "0.0.0.0")             # bind address / 綁定位址
PORT         = int(os.environ.get("PORT", "5000"))             # HTTP port / HTTP 連接埠
HW_ENCODER   = os.environ.get("HW_ENCODER", "auto")           # auto | libx264 | h264_videotoolbox, etc.
LOG_LEVEL    = os.environ.get("LOG_LEVEL", "INFO")           # Python log level / 日誌級別
COOKIE_MAX_BYTES = int(os.environ.get("COOKIE_MAX_BYTES", "65536"))  # max cookie payload per request / 單次 Cookie 上限
DISABLE_ARIA2C   = os.environ.get("DISABLE_ARIA2C", "").lower() in ("1", "true", "yes", "on")  # disable aria2c / 停用 aria2c

os.makedirs(TEMP_DIR, exist_ok=True)
