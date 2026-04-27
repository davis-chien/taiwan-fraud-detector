from __future__ import annotations

from typing import Any, Dict, List, Optional
from urllib.parse import unquote, urlparse


def _normalize_url(url: str) -> str:
    url = url.strip()
    if not url:
        return url

    parsed = urlparse(url)
    if not parsed.scheme:
        return "http://" + url

    return url


def extract_url_metadata(
    final_url: str,
    original_url: Optional[str] = None,
    redirect_chain: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Extract safe metadata from a normalized URL and redirect chain."""
    metadata: Dict[str, Any] = {
        "original_url": original_url or "",
        "final_url": final_url,
        "redirect_chain": redirect_chain or [],
        "redirect_hops": len(redirect_chain or []),
    }

    normalized_url = _normalize_url(final_url)
    parsed = urlparse(normalized_url)

    metadata["scheme"] = parsed.scheme
    metadata["hostname"] = parsed.hostname or ""
    metadata["domain"] = parsed.hostname or ""
    metadata["path"] = unquote(parsed.path or "")
    metadata["query"] = unquote(parsed.query or "")
    metadata["has_credentials"] = bool(parsed.username or parsed.password)
    metadata["netloc"] = parsed.netloc

    return metadata
