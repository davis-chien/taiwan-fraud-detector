from __future__ import annotations

from typing import List, Tuple
from urllib.parse import unquote, urlparse

SUSPICIOUS_TLDS = {
    ".xyz",
    ".top",
    ".loan",
    ".win",
    ".click",
    ".website",
    ".space",
    ".review",
    ".online",
    ".site",
    ".live",
    ".pw",
    ".kim",
    ".work",
    ".info",
    ".club",
    ".shop",
    ".cc",
    ".biz",
    ".download",
    ".tokyo",
}

URL_KEYWORDS = {
    "login",
    "signin",
    "verify",
    "confirm",
    "account",
    "secure",
    "security",
    "payment",
    "pay",
    "invoice",
    "bank",
    "atm",
    "voucher",
    "gift",
    "coupon",
    "password",
    "token",
    "auth",
    "credential",
    "pwd",
    "passcode",
}

PATH_SENSITIVE_TERMS = {
    "password",
    "passcode",
    "pwd",
    "token",
    "auth",
    "credential",
    "secure",
}


def _has_suspicious_tld(hostname: str) -> bool:
    normalized = hostname.lower().strip()
    return any(normalized.endswith(tld) for tld in SUSPICIOUS_TLDS)


def _has_idn_homograph(hostname: str) -> bool:
    hostname = hostname.lower().strip()
    if hostname.startswith("xn--") or ".xn--" in hostname:
        return True
    return any(ord(char) > 127 for char in hostname)


def _has_suspicious_keyword(url_text: str) -> Tuple[bool, str]:
    for keyword in URL_KEYWORDS:
        if keyword in url_text:
            return True, keyword
    return False, ""


def _has_sensitive_path_term(path_text: str) -> Tuple[bool, str]:
    for term in PATH_SENSITIVE_TERMS:
        if term in path_text:
            return True, term
    return False, ""


def analyze_url_signals(url: str) -> List[str]:
    """Extract URL-origin fraud signals from a normalized URL string."""
    if not isinstance(url, str) or not url.strip():
        return []

    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower()
    if not hostname:
        return []

    path = unquote(parsed.path or "").lower()
    query = unquote(parsed.query or "").lower()
    url_text = f"{hostname}{path}{query}"

    signals: List[str] = []

    if _has_suspicious_tld(hostname):
        signals.append("suspicious_tld")

    if _has_idn_homograph(hostname):
        signals.append("idn_homograph")

    suspicious_keyword, keyword = _has_suspicious_keyword(url_text)
    if suspicious_keyword:
        signals.append("suspicious_url_keyword")

    sensitive_path, _path_term = _has_sensitive_path_term(path)
    if sensitive_path:
        signals.append("suspicious_path_term")

    return signals


def analyze_url_signals_with_matches(url: str) -> List[Tuple[str, str]]:
    if not isinstance(url, str) or not url.strip():
        return []

    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower()
    if not hostname:
        return []

    path = unquote(parsed.path or "").lower()
    query = unquote(parsed.query or "").lower()
    url_text = f"{hostname}{path}{query}"

    results: List[Tuple[str, str]] = []

    if _has_suspicious_tld(hostname):
        results.append(("suspicious_tld", hostname))

    if _has_idn_homograph(hostname):
        results.append(("idn_homograph", hostname))

    suspicious_keyword, keyword = _has_suspicious_keyword(url_text)
    if suspicious_keyword:
        results.append(("suspicious_url_keyword", keyword))

    sensitive_path, path_term = _has_sensitive_path_term(path)
    if sensitive_path:
        results.append(("suspicious_path_term", path_term))

    return results
