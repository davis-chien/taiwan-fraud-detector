from __future__ import annotations

from typing import List, Optional, Tuple
from urllib.parse import urlparse

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


def is_supported_shortener(url: str) -> bool:
    parsed = urlparse(_normalize_url(url))
    hostname = (parsed.hostname or "").lower()
    return hostname in SHORTENER_HOSTS


def unshorten_url(
    url: str,
    client: Optional[httpx.Client] = None,
) -> Tuple[str, bool, str, List[str]]:
    """Resolve a shortened URL safely and return the final destination.

    Returns:
        final_url: the resolved URL or the original normalized URL
        changed: whether the URL changed after following redirects
        status: resolution status string
        redirect_chain: list of URLs in the redirect chain
    """
    normalized_url = _normalize_url(url)
    if not normalized_url:
        return url, False, "invalid URL", []

    if not is_supported_shortener(normalized_url):
        return normalized_url, False, "unchanged", []

    local_client = client
    close_client = False
    if local_client is None:
        local_client = httpx.Client(
            follow_redirects=True,
            timeout=TIMEOUT,
            max_redirects=MAX_REDIRECTS,
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=5),
            trust_env=False,
        )
        close_client = True

    try:
        with local_client.stream("GET", normalized_url) as response:
            final_url = str(response.url)
            redirect_chain = [str(r.url) for r in response.history]
            total_bytes = 0
            for chunk in response.iter_bytes(chunk_size=8192):
                total_bytes += len(chunk)
                if total_bytes > MAX_RESPONSE_BYTES:
                    break

        changed = final_url != normalized_url
        status = "resolved" if changed else "unchanged"
        return final_url, changed, status, redirect_chain

    except httpx.TooManyRedirects:
        return normalized_url, False, "too many redirects", []
    except httpx.RequestError:
        return normalized_url, False, "resolution failed", []
    except Exception:
        return normalized_url, False, "resolution error", []
    finally:
        if close_client:
            local_client.close()
