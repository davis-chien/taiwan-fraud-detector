import os
import unittest
from unittest.mock import MagicMock, patch

from pipeline.llm import infer_llm_prompt
from pipeline.output import FraudVerdict


class TestLLMInference(unittest.TestCase):
    @patch("pipeline.llm.anthropic.Anthropic")
    def test_infer_llm_prompt_returns_fraud_verdict(self, mock_anthropic_class):
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client

        mock_block = MagicMock()
        mock_block.type = "tool_use"
        mock_block.name = "submit_verdict"
        mock_block.input = {
            "verdict": "suspicious",
            "confidence": 0.87,
            "matched_patterns": ["bank_phishing"],
            "message_signals": ["urgency"],
            "url_signals": [],
            "plain_summary": "這是可疑訊息。",
        }
        mock_client.messages.create.return_value.content = [mock_block]

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            result = infer_llm_prompt("some prompt")

        self.assertIsInstance(result, FraudVerdict)
        self.assertEqual(result.verdict, "suspicious")
        self.assertAlmostEqual(result.confidence, 0.87)
        self.assertEqual(result.matched_patterns, ["bank_phishing"])
        self.assertEqual(result.message_signals, ["urgency"])
        self.assertEqual(result.plain_summary, "這是可疑訊息。")

    @patch("pipeline.llm.anthropic.Anthropic")
    def test_infer_llm_prompt_returns_fraud_verdict_for_confirmed_fraud(self, mock_anthropic_class):
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client

        mock_block = MagicMock()
        mock_block.type = "tool_use"
        mock_block.name = "submit_verdict"
        mock_block.input = {
            "verdict": "fraud",
            "confidence": 0.95,
            "matched_patterns": ["bank_phishing", "government_impersonation"],
            "message_signals": ["urgency", "impersonation"],
            "url_signals": ["suspicious_tld"],
            "plain_summary": "這是詐騙訊息，請勿點擊。",
        }
        mock_client.messages.create.return_value.content = [mock_block]

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            result = infer_llm_prompt("some prompt")

        self.assertEqual(result.verdict, "fraud")
        self.assertAlmostEqual(result.confidence, 0.95)
        self.assertEqual(result.matched_patterns, ["bank_phishing", "government_impersonation"])

    @patch("pipeline.llm.anthropic.Anthropic")
    def test_infer_llm_prompt_clamps_confidence(self, mock_anthropic_class):
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client

        mock_block = MagicMock()
        mock_block.type = "tool_use"
        mock_block.name = "submit_verdict"
        mock_block.input = {
            "verdict": "safe",
            "confidence": 1.5,
            "matched_patterns": [],
            "message_signals": [],
            "url_signals": [],
            "plain_summary": "看起來正常。",
        }
        mock_client.messages.create.return_value.content = [mock_block]

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            result = infer_llm_prompt("some prompt")

        self.assertEqual(result.confidence, 1.0)

    def test_infer_llm_prompt_raises_without_api_key(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(RuntimeError):
                infer_llm_prompt("some prompt")

    @patch("pipeline.llm.anthropic.Anthropic")
    def test_infer_llm_prompt_raises_when_no_tool_call(self, mock_anthropic_class):
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client

        mock_block = MagicMock()
        mock_block.type = "text"
        mock_client.messages.create.return_value.content = [mock_block]

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            with self.assertRaises(ValueError):
                infer_llm_prompt("some prompt")


if __name__ == "__main__":
    unittest.main()
