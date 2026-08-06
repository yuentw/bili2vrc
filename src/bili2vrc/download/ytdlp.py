import os
import shutil
import sys
from dataclasses import dataclass
from functools import lru_cache

from bili2vrc import config
from bili2vrc.utils.platform import detect_platform

JS_RUNTIME_ORDER = ("node", "bun", "deno")
YTDLP_REMOTE_COMPONENTS = ("--remote-components", "ejs:github")


@dataclass(frozen=True)
class JsRuntime:
    name: str
    path: str | None = None


def _local_bun_path() -> str | None:
    name = "bun.exe" if sys.platform == "win32" else "bun"
    path = os.path.join(config.BASE_DIR, ".bun", "bin", name)
    if not os.path.isfile(path):
        return None
    if sys.platform != "win32" and not os.access(path, os.X_OK):
        return None
    return path


def _resolve_runtime_path(name: str) -> str | None:
    if name == "bun":
        local = _local_bun_path()
        if local:
            return local
    return shutil.which(name)


def _detect_js_runtime() -> JsRuntime | None:
    for name in JS_RUNTIME_ORDER:
        path = _resolve_runtime_path(name)
        if path:
            return JsRuntime(name=name, path=path)
    return None


@lru_cache(maxsize=1)
def get_js_runtime() -> JsRuntime | None:
    """Return yt-dlp JS runtime (node → bun → deno), or forced via YTDLP_JS_RUNTIME."""
    forced = config.YTDLP_JS_RUNTIME
    if forced != "auto":
        path = _resolve_runtime_path(forced)
        return JsRuntime(name=forced, path=path)
    return _detect_js_runtime()


@lru_cache(maxsize=1)
def get_ytdlp_js_args() -> list[str]:
    runtime = get_js_runtime()
    args: list[str] = []
    if runtime:
        if runtime.path:
            args.extend(["--js-runtimes", f"{runtime.name}:{runtime.path}"])
        else:
            args.extend(["--js-runtimes", runtime.name])
    args.extend(YTDLP_REMOTE_COMPONENTS)
    return args


def _local_aria2c_path() -> str | None:
    """專案根目錄內使用者自行放置的 aria2c（Windows: aria2c.exe，Unix: aria2c）"""
    name = "aria2c.exe" if sys.platform == "win32" else "aria2c"
    path = os.path.join(config.BASE_DIR, name)
    if not os.path.isfile(path):
        return None
    if sys.platform != "win32" and not os.access(path, os.X_OK):
        return None
    return path


def has_aria2c() -> bool:
    """偵測 aria2c：先查專案根目錄，再查 PATH（可由 DISABLE_ARIA2C 關閉）"""
    if config.DISABLE_ARIA2C:
        return False
    if _local_aria2c_path():
        return True
    return shutil.which("aria2c") is not None


def should_use_aria2c(url: str) -> bool:
    """YouTube 不使用 aria2c（與 yt-dlp 外部下載器相容性較差）"""
    if detect_platform(url) == "youtube":
        return False
    return has_aria2c()


def get_aria2c_cmd() -> str:
    """回傳 aria2c 可用的命令名稱（專案根目錄或 PATH）"""
    local = _local_aria2c_path()
    return local if local else "aria2c"
