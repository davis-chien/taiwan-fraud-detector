import re
from typing import Optional

URL_REGEX = re.compile(
    r"(?P<url>(https?://[\w\-\.\u4e00-\u9fff%:/?#\[\]@!$&'()*+,;=]+|www\.[\w\-\.\u4e00-\u9fff%:/?#\[\]@!$&'()*+,;=]+))",
    re.IGNORECASE,
)
BARE_DOMAIN_REGEX = re.compile(
    r"(?P<url>[a-zA-Z0-9\-]+\.(?:com|net|org|tw|co|cc|io|jp|hk|top|xyz|app|online|shop|info)(?:/[\w\-\.\u4e00-\u9fff%:/?#\[\]@!$&'()*+,;=]*)?)",
    re.IGNORECASE,
)
TRAILING_PUNCTUATION = "\"'.,;:!?()[]{}。！？；：」』"


def _normalize_url(url: str) -> str:
    """Normalize a captured URL and remove trailing punctuation."""
    url = url.strip()
    while url and url[-1] in TRAILING_PUNCTUATION:
        url = url[:-1]
    if url.startswith("www."):
        url = "http://" + url
    return url


def extract_url(text: str) -> Optional[str]:
    """Extract the first URL-like string from a message."""
    if not isinstance(text, str) or not text.strip():
        return None

    normalized_text = text.replace("\n", " ")
    match = URL_REGEX.search(normalized_text)
    if match:
        return _normalize_url(match.group("url"))

    match = BARE_DOMAIN_REGEX.search(normalized_text)
    if match:
        return _normalize_url(match.group("url"))

    return None
