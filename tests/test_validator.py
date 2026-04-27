import unittest

from pipeline.validator import validate_url


class TestValidator(unittest.TestCase):
    def test_validate_url_accepts_safe_http_urls(self):
        valid, reason = validate_url("https://example.com/path")
        self.assertTrue(valid)
        self.assertEqual(reason, "ok")

    def test_validate_url_blocks_unsafe_or_invalid_urls(self):
        valid, reason = validate_url("http://localhost")
        self.assertFalse(valid)
        self.assertIn("blocked", reason)

        valid, reason = validate_url("ftp://example.com")
        self.assertFalse(valid)
        self.assertEqual(reason, "unsupported URL scheme")

        valid, reason = validate_url("https://user:pass@example.com")
        self.assertFalse(valid)
        self.assertEqual(reason, "URLs with embedded credentials are blocked")

        valid, reason = validate_url("http://example")
        self.assertFalse(valid)
        self.assertEqual(reason, "invalid or unsupported hostname")


if __name__ == "__main__":
    unittest.main()
