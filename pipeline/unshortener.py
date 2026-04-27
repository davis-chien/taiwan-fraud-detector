from __future__ import annotations

import ipaddress
import socket
from typing import List, Optional, Tuple
from urllib.parse import urlparse, urljoin

import httpx

SHORTENER_HOSTS = {
    "lin.ee",
    "bit.ly",
    "tinyurl.com",
    "t.co",
    "shorturl.at",
    "tiny.cc",
    "rb.gy",
}

MAX_REDIRECTS = 3
MAX_RESPONSE_BYTES = 64 * 1024
TIMEOUT = httpx.Timeout(connect=5.0, read=10.0, write=10.0, pool=5.0)


def _normalize_url(url: str) -> str:
    normalized = url.strip()
    if not normalized:
        return normalized

    parsed = urlparse(normalized)
    if not parsed.scheme:
        normalized = "http://" + normalized
    return normalized


def _is_ssrf_target(url: str) -> bool:
    """Return True if url resolves to a private/internal address (SSRF risk)."""
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname or ""
        if not hostname:
            return True
        ip_str = socket.gethostbyname(hostname)
        ip = ipaddress.ip_address(ip_str)
        return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved
    except Exception:
        return False


def is_supported_shortener(url: str) -> bool:
    parsed = urlparse(_normalize_url(url))
    hostname = (parsed.hostname or "").lower()
    return hostname in SHORTENER_HOSTS


def unshorten_url(
    url: str,
    client: Optional[httpx.Client] = None,
) -> Tuple[str, bool, str, List[str]]:
    """Resolve a shortened URL, blocking SSRF redirects at every hop.

    Returns:
        final_url: the resolved URL or the original normalized URL
        changed: whether the URL changed after following redirects
        status: resolution status string
        redirect_chain: list of intermediate URLs visited before final destination
    """
    normalized_url = _normalize_url(url)
    if not normalized_url:
        return url, False, "invalid URL", []

    if not is_supported_shortener(normalized_url):
        return normalized_url, False, "unchanged", []

    # Block SSRF on the shortener URL itself before any connection
    if _is_ssrf_target(normalized_url):
        return normalized_url, False, "ssrf_blocked", []

    local_client = client
    close_client = False
    if local_client is None:
        local_client = httpx.Client(
            follow_redirects=False,
            timeout=TIMEOUT,
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=5),
            trust_env=False,
        )
        close_client = True

    try:
        current_url = normalized_url
        redirect_chain: List[str] = []

        for _ in range(MAX_REDIRECTS):
            try:
                with local_client.stream("GET", current_url) as response:
                    for _chunk in response.iter_bytes(chunk_size=8192):
                        break
                    is_redirect = response.is_redirect
                    location = response.headers.get("location", "")
            except httpx.RequestError:
                return normalized_url, False, "resolution failed", redirect_chain

            if not is_redirect or not location:
                changed = current_url != normalized_url
                status = "resolved" if changed else "unchanged"
                return current_url, changed, status, redirect_chain

            next_url = urljoin(current_url, location)

            # SSRF check before following each redirect hop
            if _is_ssrf_target(next_url):
                return normalized_url, False, "ssrf_blocked", redirect_chain

            redirect_chain.append(current_url)
            current_url = next_url

        return normalized_url, False, "too many redirects", redirect_chain

    except Exception:
        return normalized_url, False, "resolution error", []
    finally:
        if close_client:
            local_client.close()
