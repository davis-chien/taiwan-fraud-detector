import socket
import unittest
from unittest.mock import patch

import httpx

from pipeline.unshortener import _is_ssrf_target, is_supported_shortener, unshorten_url


def _mock_client(handler):
    """Return an httpx.Client backed by a mock transport with follow_redirects=False."""
    return httpx.Client(
        transport=httpx.MockTransport(handler),
        follow_redirects=False,
        timeout=httpx.Timeout(5.0, read=10.0, write=10.0, pool=5.0),
        trust_env=False,
    )


class TestIsSSRFTarget(unittest.TestCase):
    def test_blocks_private_ip(self):
        with patch("socket.gethostbyname", return_value="192.168.1.1"):
            self.assertTrue(_is_ssrf_target("http://evil.example.com/"))

    def test_blocks_loopback(self):
        with patch("socket.gethostbyname", return_value="127.0.0.1"):
            self.assertTrue(_is_ssrf_target("http://localhost/"))

    def test_blocks_link_local(self):
        with patch("socket.gethostbyname", return_value="169.254.169.254"):
            self.assertTrue(_is_ssrf_target("http://metadata.internal/"))

    def test_allows_public_ip(self):
        with patch("socket.gethostbyname", return_value="93.184.216.34"):
            self.assertFalse(_is_ssrf_target("http://example.com/"))

    def test_blocks_empty_hostname(self):
        self.assertTrue(_is_ssrf_target("http:///path"))

    def test_dns_failure_does_not_block(self):
        with patch("socket.gethostbyname", side_effect=socket.gaierror("DNS error")):
            self.assertFalse(_is_ssrf_target("http://nonexistent.example.com/"))


class TestIsSupportedShortener(unittest.TestCase):
    def test_detects_known_shorteners(self):
        self.assertTrue(is_supported_shortener("http://bit.ly/abc"))
        self.assertTrue(is_supported_shortener("tinyurl.com/xyz"))
        self.assertFalse(is_supported_shortener("https://example.com/path"))


class TestUnshortenUrl(unittest.TestCase):
    def test_resolves_shortened_redirect(self):
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/abc":
                return httpx.Response(302, headers={"location": "https://example.com/final"})
            return httpx.Response(200, text="ok")

        with patch("pipeline.unshortener._is_ssrf_target", return_value=False):
            final_url, changed, status, redirect_chain = unshorten_url(
                "http://bit.ly/abc", client=_mock_client(handler)
            )

        self.assertTrue(changed)
        self.assertEqual(final_url, "https://example.com/final")
        self.assertEqual(status, "resolved")
        self.assertEqual(redirect_chain, ["http://bit.ly/abc"])

    def test_unchanged_when_no_redirect(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text="ok")

        with patch("pipeline.unshortener._is_ssrf_target", return_value=False):
            final_url, changed, status, redirect_chain = unshorten_url(
                "http://bit.ly/abc", client=_mock_client(handler)
            )

        self.assertFalse(changed)
        self.assertEqual(status, "unchanged")
        self.assertEqual(redirect_chain, [])

    def test_blocks_ssrf_on_initial_url(self):
        with patch("pipeline.unshortener._is_ssrf_target", return_value=True):
            final_url, changed, status, redirect_chain = unshorten_url("http://bit.ly/evil")

        self.assertFalse(changed)
        self.assertEqual(status, "ssrf_blocked")
        self.assertEqual(redirect_chain, [])

    def test_blocks_ssrf_on_redirect_hop(self):
        """Shortener redirecting to an internal IP must be blocked before fetching."""
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.host == "bit.ly":
                return httpx.Response(302, headers={"location": "http://169.254.169.254/meta-data/"})
            return httpx.Response(200, text="metadata")

        def ssrf_check(url: str) -> bool:
            return "169.254" in url

        with patch("pipeline.unshortener._is_ssrf_target", side_effect=ssrf_check):
            final_url, changed, status, redirect_chain = unshorten_url(
                "http://bit.ly/evil", client=_mock_client(handler)
            )

        self.assertFalse(changed)
        self.assertEqual(status, "ssrf_blocked")

    def test_too_many_redirects(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(302, headers={"location": str(request.url) + "x"})

        with patch("pipeline.unshortener._is_ssrf_target", return_value=False):
            _final_url, changed, status, _chain = unshorten_url(
                "http://bit.ly/abc", client=_mock_client(handler)
            )

        self.assertFalse(changed)
        self.assertEqual(status, "too many redirects")

    def test_unsupported_shortener_returned_unchanged(self):
        final_url, changed, status, redirect_chain = unshorten_url("https://example.com/page")
        self.assertFalse(changed)
        self.assertEqual(status, "unchanged")

    def test_empty_url_returns_invalid(self):
        final_url, changed, status, redirect_chain = unshorten_url("")
        self.assertFalse(changed)
        self.assertEqual(status, "invalid URL")


if __name__ == "__main__":
    unittest.main()
