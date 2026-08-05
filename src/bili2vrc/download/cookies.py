import os
import tempfile
from contextlib import contextmanager

from bili2vrc import config


def validate_cookie_content(content: bytes) -> str | None:
    """驗證 cookies.txt 內容，成功回傳 None，失敗回傳錯誤訊息"""
    if len(content) > config.COOKIE_MAX_BYTES:
        return f"檔案過大（上限 {config.COOKIE_MAX_BYTES // 1024} KB）"
    if not content.strip():
        return "檔案為空"

    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        try:
            text = content.decode("latin-1")
        except UnicodeDecodeError:
            return "無法讀取為文字檔"

    has_cookie_line = False
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "\t" in stripped:
            has_cookie_line = True
            break
    if not has_cookie_line:
        return "不是有效的 Netscape cookies.txt 格式"
    return None


@contextmanager
def temp_cookie_file(cookie_content: str | None):
    """將 payload cookie 寫入暫存檔，用完自動刪除"""
    if not cookie_content:
        yield None
        return

    format_error = validate_cookie_content(cookie_content.encode("utf-8"))
    if format_error:
        raise ValueError(format_error)

    fd, path = tempfile.mkstemp(suffix=".txt", dir=config.TEMP_DIR)
    try:
        with os.fdopen(fd, "wb") as cookie_file:
            cookie_file.write(cookie_content.encode("utf-8"))
        yield path
    finally:
        if os.path.isfile(path):
            os.remove(path)


def write_cookie_temp_file(cookie_content: str) -> str:
    """寫入暫存 cookie 檔（由呼叫方負責刪除，用於 background thread）"""
    format_error = validate_cookie_content(cookie_content.encode("utf-8"))
    if format_error:
        raise ValueError(format_error)

    fd, path = tempfile.mkstemp(suffix=".txt", dir=config.TEMP_DIR)
    with os.fdopen(fd, "wb") as cookie_file:
        cookie_file.write(cookie_content.encode("utf-8"))
    return path


def get_cookie_args(cookie_path: str | None = None):
    """如果 cookie 檔案存在就帶參數，否則不帶"""
    if cookie_path and os.path.isfile(cookie_path):
        return ["--cookies", cookie_path]
    return []
