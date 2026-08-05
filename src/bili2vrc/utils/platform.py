import urllib.parse

from bili2vrc.download.cookies import validate_cookie_content


def detect_platform(url: str) -> str | None:
    """從影片 URL 判斷平台"""
    try:
        host = urllib.parse.urlparse(url).netloc.lower()
    except Exception:
        return None
    if "bilibili.com" in host or host.endswith("b23.tv"):
        return "bilibili"
    if "youtube.com" in host or host in ("youtu.be",) or host.endswith(".youtu.be"):
        return "youtube"
    return None


def domain_matches_platform(domain: str, platform: str) -> bool:
    host = domain.lower().lstrip(".")
    if platform == "bilibili":
        return "bilibili.com" in host or host.endswith("b23.tv")
    if platform == "youtube":
        return "youtube.com" in host or host in ("youtu.be",) or host.endswith(".youtu.be")
    return False


def detect_platforms_from_cookie_content(content: str) -> set[str]:
    """從 Netscape cookies.txt 內容解析域名，判斷所屬平台"""
    found: set[str] = set()
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "\t" not in stripped:
            continue
        domain = stripped.split("\t", 1)[0]
        for platform in ("bilibili", "youtube"):
            if domain_matches_platform(domain, platform):
                found.add(platform)
    return found


def validate_cookie_for_url(url: str, cookie_content: str | None) -> str | None:
    """驗證 cookie 內容與 URL 平台是否匹配"""
    if not cookie_content:
        return None

    format_error = validate_cookie_content(cookie_content.encode("utf-8"))
    if format_error:
        return format_error

    url_platform = detect_platform(url)
    if not url_platform:
        return None

    content_platforms = detect_platforms_from_cookie_content(cookie_content)
    if url_platform not in content_platforms:
        label = "Bilibili" if url_platform == "bilibili" else "YouTube"
        return f"Cookie 與網址平台不符（需要 {label} cookie）"
    return None
