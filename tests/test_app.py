import unittest

from app import analyze_line_message


class TestAppIntegration(unittest.TestCase):
    def test_analyze_line_message_returns_safe_for_empty_input(self):
        verdict, confidence, summary, url, status, metadata = analyze_line_message("")
        self.assertEqual(verdict, "safe")
        self.assertEqual(confidence, 0.0)
        self.assertEqual(metadata, "")

    def test_analyze_line_message_blocks_localhost_urls(self):
        verdict, confidence, summary, url, status, metadata = analyze_line_message(
            "這是詐騙訊息，請立即點擊 http://localhost/evil"
        )
        self.assertEqual(verdict, "suspicious")
        self.assertEqual(status, "blocked host")
        self.assertTrue(metadata)

    def test_analyze_line_message_marks_suspicious_url_signals(self):
        verdict, confidence, summary, url, status, metadata = analyze_line_message(
            "請點擊 https://example.xyz/login 立即驗證帳號"
        )
        self.assertEqual(verdict, "suspicious")
        self.assertEqual(status, "ok")
        self.assertIn("連結包含可疑網址特徵", summary)
        self.assertTrue(metadata)

    def test_analyze_line_message_returns_safe_for_normal_text(self):
        verdict, confidence, summary, url, status, metadata = analyze_line_message(
            "這是一封普通通知，沒有問題。"
        )
        self.assertEqual(verdict, "safe")
        self.assertEqual(status, "ok")
        self.assertEqual(metadata, "")


if __name__ == "__main__":
    unittest.main()
