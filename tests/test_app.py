import os
import unittest
from unittest.mock import patch

from app import analyze_line_message


class TestAppIntegration(unittest.TestCase):
    def test_analyze_line_message_returns_safe_for_empty_input(self):
        verdict, confidence, summary, url, status, metadata, prompt, matched = analyze_line_message("")
        self.assertEqual(verdict, "safe")
        self.assertEqual(confidence, 0.0)
        self.assertEqual(metadata, "")
        self.assertEqual(prompt, "")
        self.assertEqual(matched, "")

    def test_analyze_line_message_blocks_localhost_urls(self):
        verdict, confidence, summary, url, status, metadata, prompt, matched = analyze_line_message(
            "這是詐騙訊息，請立即點擊 http://localhost/evil"
        )
        self.assertEqual(verdict, "suspicious")
        self.assertEqual(status, "blocked host")
        self.assertTrue(metadata)
        self.assertIn("使用者 LINE 訊息:", prompt)

    def test_analyze_line_message_marks_suspicious_url_signals(self):
        verdict, confidence, summary, url, status, metadata, prompt, matched = analyze_line_message(
            "請點擊 https://example.xyz/login 立即驗證帳號"
        )
        self.assertEqual(verdict, "suspicious")
        self.assertEqual(status, "ok")
        self.assertIn("連結包含可疑網址特徵", summary)
        self.assertTrue(metadata)
        self.assertIn("知識庫檢索結果", prompt)

    def test_analyze_line_message_returns_safe_for_normal_text(self):
        verdict, confidence, summary, url, status, metadata, prompt, matched = analyze_line_message(
            "這是一封普通通知，沒有問題。"
        )
        self.assertEqual(verdict, "safe")
        self.assertEqual(status, "ok")
        self.assertEqual(metadata, "")
        self.assertIn("使用者 LINE 訊息:", prompt)

    def test_prompt_includes_kb_doc_ids_when_kb_loaded(self):
        # KB docs exist in knowledge_base/ so the prompt should reference them.
        _, _, _, _, _, _, prompt, _ = analyze_line_message(
            "請點擊 https://example.xyz/login 立即驗證帳號"
        )
        self.assertIn("文件 ID:", prompt)

    @patch("app.infer_llm_prompt")
    def test_matched_patterns_from_llm_appear_in_output(self, mock_infer):
        from pipeline.output import FraudVerdict

        mock_infer.return_value = FraudVerdict(
            verdict="fraud",
            confidence=0.95,
            matched_patterns=["bank_phishing", "government_impersonation"],
            message_signals=["urgency", "impersonation"],
            url_signals=[],
            plain_summary="這是銀行詐騙，請勿點擊。",
        )

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            verdict, confidence, summary, url, status, metadata, prompt, matched = analyze_line_message(
                "您的玉山銀行帳號異常，請立即點擊 https://example.com/verify"
            )

        self.assertEqual(verdict, "fraud")
        self.assertAlmostEqual(confidence, 0.95)
        self.assertIn("bank_phishing", matched)
        self.assertIn("government_impersonation", matched)

    @patch("app.infer_llm_prompt")
    def test_domain_age_backfilled_from_whois(self, mock_infer):
        from pipeline.output import FraudVerdict

        mock_infer.return_value = FraudVerdict(
            verdict="suspicious",
            confidence=0.7,
            matched_patterns=[],
            message_signals=[],
            url_signals=["suspicious_tld"],
            plain_summary="這個連結疑似可疑。",
            domain_age_days=None,
        )

        fake_domain_info = {"domain_age_days": 7, "registrar": "CheapReg", "error": None}

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            with patch("app.get_domain_info", return_value=fake_domain_info):
                with patch("app.fetch_page", return_value={"error": None, "text": "", "title": ""}):
                    result = analyze_line_message(
                        "請點擊 https://new-site.xyz/offer 立即領獎"
                    )

        # domain_age_days should be back-filled into the verdict (visible in prompt)
        _, _, _, _, _, _, prompt, _ = result
        self.assertIn("域名年齡: 7 天", prompt)


if __name__ == "__main__":
    unittest.main()
