import json
import subprocess
import unittest
from unittest.mock import MagicMock, patch

from pipeline.scraper import _is_blocked_ip, _dns_rebinding_blocked, fetch_page


class TestIsBlockedIP(unittest.TestCase):
    def test_private_ranges_blocked(self):
        for ip in ("10.0.0.1", "10.255.255.255", "192.168.1.1", "172.16.0.1", "172.31.255.255"):
            with self.subTest(ip=ip):
                self.assertTrue(_is_blocked_ip(ip))

    def test_loopback_blocked(self):
        self.assertTrue(_is_blocked_ip("127.0.0.1"))
        self.assertTrue(_is_blocked_ip("127.0.0.42"))

    def test_link_local_blocked(self):
        self.assertTrue(_is_blocked_ip("169.254.169.254"))
        self.assertTrue(_is_blocked_ip("169.254.0.1"))

    def test_public_ips_allowed(self):
        for ip in ("8.8.8.8", "1.1.1.1", "93.184.216.34", "140.82.113.4"):
            with self.subTest(ip=ip):
                self.assertFalse(_is_blocked_ip(ip))

    def test_invalid_string_not_blocked(self):
        self.assertFalse(_is_blocked_ip("not-an-ip"))
        self.assertFalse(_is_blocked_ip(""))


class TestDnsRebindingBlocked(unittest.TestCase):
    @patch("pipeline.scraper.socket.gethostbyname")
    def test_private_resolution_blocked(self, mock_resolve):
        mock_resolve.return_value = "192.168.1.100"
        self.assertTrue(_dns_rebinding_blocked("evil.example.com"))

    @patch("pipeline.scraper.socket.gethostbyname")
    def test_loopback_resolution_blocked(self, mock_resolve):
        mock_resolve.return_value = "127.0.0.1"
        self.assertTrue(_dns_rebinding_blocked("rebind.example.com"))

    @patch("pipeline.scraper.socket.gethostbyname")
    def test_public_resolution_allowed(self, mock_resolve):
        mock_resolve.return_value = "93.184.216.34"
        self.assertFalse(_dns_rebinding_blocked("example.com"))

    @patch("pipeline.scraper.socket.gethostbyname", side_effect=Exception("DNS error"))
    def test_dns_failure_not_blocked(self, _mock_resolve):
        self.assertFalse(_dns_rebinding_blocked("unreachable.example.com"))


class TestFetchPage(unittest.TestCase):
    @patch("pipeline.scraper.subprocess.run")
    def test_returns_parsed_json_on_success(self, mock_run):
        payload = {"error": None, "text": "頁面內容", "title": "詐騙標題"}
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps(payload),
            stderr="",
        )
        result = fetch_page("https://example.com")
        self.assertIsNone(result["error"])
        self.assertEqual(result["text"], "頁面內容")
        self.assertEqual(result["title"], "詐騙標題")

    @patch("pipeline.scraper.subprocess.run")
    def test_returns_error_on_nonzero_exit(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="fetch failed")
        result = fetch_page("https://example.com")
        self.assertIsNotNone(result["error"])
        self.assertEqual(result["text"], "")

    @patch("pipeline.scraper.subprocess.run")
    def test_handles_subprocess_timeout(self, mock_run):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="python", timeout=15)
        result = fetch_page("https://example.com")
        self.assertEqual(result["error"], "subprocess_timeout")
        self.assertEqual(result["text"], "")

    @patch("pipeline.scraper.subprocess.run")
    def test_handles_invalid_json_from_subprocess(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="not json", stderr="")
        result = fetch_page("https://example.com")
        self.assertEqual(result["error"], "invalid_json_from_subprocess")
        self.assertEqual(result["text"], "")

    @patch("pipeline.scraper.subprocess.run")
    def test_handles_empty_stdout(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        result = fetch_page("https://example.com")
        self.assertIn("error", result)
        self.assertEqual(result["text"], "")


if __name__ == "__main__":
    unittest.main()
