from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

import whois

CACHE_TTL = 24 * 3600  # 24 hours

# hostname -> (result_dict, unix_timestamp)
_CACHE: Dict[str, Tuple[Dict[str, Any], float]] = {}


def _parse_age_days(creation_date: Any) -> Optional[int]:
    if creation_date is None:
        return None
    if isinstance(creation_date, list):
        creation_date = creation_date[0]
    if not isinstance(creation_date, datetime):
        return None
    now = datetime.now(timezone.utc)
    if creation_date.tzinfo is None:
        creation_date = creation_date.replace(tzinfo=timezone.utc)
    return max(0, (now - creation_date).days)


def get_domain_info(hostname: str) -> Dict[str, Any]:
    """Return WHOIS metadata for hostname. Results are cached for 24 hours."""
    hostname = hostname.lower().strip()
    empty: Dict[str, Any] = {
        "hostname": hostname,
        "domain_age_days": None,
        "registrar": None,
        "error": None,
    }
    if not hostname:
        return empty

    cached, ts = _CACHE.get(hostname, ({}, 0.0))
    if cached and time.time() - ts < CACHE_TTL:
        return cached

    result: Dict[str, Any] = {
        "hostname": hostname,
        "domain_age_days": None,
        "registrar": None,
        "error": None,
    }
    try:
        w = whois.whois(hostname)
        result["domain_age_days"] = _parse_age_days(w.creation_date)
        result["registrar"] = str(w.registrar or "")[:100] if w.registrar else None
    except Exception as exc:
        result["error"] = str(exc)[:100]

    _CACHE[hostname] = (result, time.time())
    return result
