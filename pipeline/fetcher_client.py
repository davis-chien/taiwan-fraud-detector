"""
Route URL-fetch operations to the fetcher worker when FETCHER_URL is set.
Falls back to in-process calls when running locally without Docker Compose.
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Tuple

import httpx

from .enricher import get_domain_info as _local_enrich
from .scraper import fetch_page as _local_fetch
from .unshortener import unshorten_url as _local_unshorten

_TIMEOUT = httpx.Timeout(connect=5.0, read=25.0, write=5.0, pool=5.0)


def _base() -> str:
    return os.getenv("FETCHER_URL", "").rstrip("/")


def unshorten_url(url: str) -> Tuple[str, bool, str, List[str]]:
    base = _base()
    if not base:
        return _local_unshorten(url)
    try:
        resp = httpx.post(f"{base}/unshorten", json={"url": url}, timeout=_TIMEOUT)
        resp.raise_for_status()
        d = resp.json()
        return d["resolved_url"], d["changed"], d["status"], d["chain"]
    except Exception:
        # Worker is configured but unreachable — don't fall back to in-process
        # resolution, which would defeat container isolation.
        return url, False, "fetcher_unavailable", []


def fetch_page(url: str) -> Dict[str, Any]:
    base = _base()
    if not base:
        return _local_fetch(url)
    try:
        resp = httpx.post(f"{base}/fetch", json={"url": url}, timeout=_TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return {"error": "fetcher_unavailable", "text": "", "title": ""}


def get_domain_info(hostname: str) -> Dict[str, Any]:
    base = _base()
    if not base:
        return _local_enrich(hostname)
    try:
        resp = httpx.post(f"{base}/enrich", json={"hostname": hostname}, timeout=_TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        # Worker is configured but unreachable — don't run WHOIS in-process.
        return {"hostname": hostname, "domain_age_days": None, "registrar": None, "error": "fetcher_unavailable"}
