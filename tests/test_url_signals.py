import unittest

from pipeline.url_signals import analyze_url_signals


class TestURLSignals(unittest.TestCase):
    def test_analyze_url_signals_detects_suspicious_tld_and_keywords(self):
        signals = analyze_url_signals("https://example.xyz/login?account=123")
        self.assertIn("suspicious_tld", signals)
        self.assertIn("suspicious_url_keyword", signals)
        self.assertNotIn("suspicious_path_term", signals)

    def test_analyze_url_signals_returns_empty_for_safe_url(self):
        signals = analyze_url_signals("https://example.com/home")
        self.assertEqual(signals, [])


if __name__ == "__main__":
    unittest.main()
