import ipaddress
import re
from typing import Tuple
from urllib.parse import urlparse

BLOCKED_HOSTS = {
    "localhost",
    "127.0.0.1",
    "::1",
    "169.254.169.254",
    "metadata.google.internal",
    "169.254.170.2",
}

HOSTNAME_RE = re.compile(r"^[A-Za-z0-9\-\.\u4e00-\u9fff%]+$")


def _is_private_ip(host: str) -> bool:
    try:
        ip = ipaddress.ip_address(host)
        return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved
    except ValueError:
        return False


def _has_valid_hostname(host: str) -> bool:
    if not host or host.startswith("-") or host.endswith("-"):
        return False
    if " " in host:
        return False
    if host.count(".") == 0:
        return False
    return bool(HOSTNAME_RE.match(host))


def validate_url(url: str) -> Tuple[bool, str]:
    """Validate a URL without making outbound network requests."""
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return False, "unsupported URL scheme"
    if not parsed.netloc:
        return False, "missing hostname"
    if parsed.username or parsed.password:
        return False, "URLs with embedded credentials are blocked"

    host = parsed.hostname or ""
    if not host:
        return False, "invalid hostname"
    host_lower = host.lower()
    if host_lower in BLOCKED_HOSTS:
        return False, "blocked host"
    if _is_private_ip(host_lower):
        return False, "private or internal IP address blocked"
    if not _has_valid_hostname(host_lower) and not _is_private_ip(host_lower):
        return False, "invalid or unsupported hostname"

    return True, "ok"
