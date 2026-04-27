"""
Subprocess-isolated page fetcher.

Public API: fetch_page(url) -> Dict[str, Any]

When run as __main__, fetches the URL in sys.argv[1] and prints JSON to stdout.
The parent process calls this via subprocess.run() so that any crash or exploit
in httpx/BeautifulSoup is contained in the child, not the main app (Layer 2/4).
"""
from __future__ import annotations

import ipaddress
import json
import socket
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict

MAX_RESPONSE_BYTES = 2 * 1024 * 1024  # 2 MB cap
HARD_TIMEOUT_SECS = 15


def _is_blocked_ip(ip_str: str) -> bool:
    try:
        ip = ipaddress.ip_address(ip_str)
        return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved
    except ValueError:
        return False


def _dns_rebinding_blocked(hostname: str) -> bool:
    """Return True if hostname resolves to an internal address (Layer 4 defense)."""
    try:
        ip_str = socket.gethostbyname(hostname)
        return _is_blocked_ip(ip_str)
    except Exception:
        return False


def _do_fetch(url: str) -> Dict[str, Any]:
    """Perform the HTTP fetch. Only called inside the subprocess."""
    from urllib.parse import urlparse

    import httpx
    from bs4 import BeautifulSoup

    parsed = urlparse(url)
    hostname = parsed.hostname or ""

    if _dns_rebinding_blocked(hostname):
        return {"error": "dns_rebinding_blocked", "text": "", "title": ""}

    timeout = httpx.Timeout(connect=5.0, read=10.0, write=10.0, pool=5.0)
    try:
        body = b""
        with httpx.Client(
            follow_redirects=True,
            max_redirects=3,
            timeout=timeout,
            trust_env=False,
            headers={"User-Agent": "Mozilla/5.0 (compatible; fraud-detector/1.0)"},
        ) as client:
            with client.stream("GET", url) as response:
                content_type = response.headers.get("content-type", "")
                if "text/html" not in content_type and "text/plain" not in content_type:
                    return {"error": "non_html_content", "text": "", "title": ""}
                for chunk in response.iter_bytes(chunk_size=8192):
                    body += chunk
                    if len(body) >= MAX_RESPONSE_BYTES:
                        break

        soup = BeautifulSoup(body, "lxml")
        title_tag = soup.find("title")
        title = title_tag.get_text(strip=True) if title_tag else ""

        for tag in soup.find_all(["script", "style", "nav", "footer", "header", "noscript"]):
            tag.decompose()

        text = soup.get_text(separator=" ", strip=True)
        return {"error": None, "text": text, "title": title}

    except httpx.TooManyRedirects:
        return {"error": "too_many_redirects", "text": "", "title": ""}
    except httpx.TimeoutException:
        return {"error": "request_timeout", "text": "", "title": ""}
    except Exception as exc:
        return {"error": str(exc)[:100], "text": "", "title": ""}


def fetch_page(url: str, hard_timeout: int = HARD_TIMEOUT_SECS) -> Dict[str, Any]:
    """Fetch page content in an isolated subprocess.

    The child is hard-killed after hard_timeout seconds. Returns a dict with
    keys: text (visible page text), title (page <title>), error (None on success).
    """
    try:
        proc = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), url],
            capture_output=True,
            text=True,
            timeout=hard_timeout,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return json.loads(proc.stdout)
        return {
            "error": (proc.stderr or "non-zero exit")[:200],
            "text": "",
            "title": "",
        }
    except subprocess.TimeoutExpired:
        return {"error": "subprocess_timeout", "text": "", "title": ""}
    except json.JSONDecodeError:
        return {"error": "invalid_json_from_subprocess", "text": "", "title": ""}
    except Exception as exc:
        return {"error": str(exc)[:100], "text": "", "title": ""}


if __name__ == "__main__":
    _url = sys.argv[1] if len(sys.argv) > 1 else ""
    print(json.dumps(_do_fetch(_url), ensure_ascii=False))
