import unittest

from pipeline.signal_analyzer import analyze_message_signals


class TestSignalAnalyzer(unittest.TestCase):
    def test_analyze_message_signals_detects_scam_language(self):
        signals = analyze_message_signals("恭喜您中獎，點擊連結領取免費禮券。")
        self.assertIn("gift_or_prize", signals)
        self.assertIn("urgency", analyze_message_signals("請馬上處理，限時優惠。"))
        self.assertEqual(analyze_message_signals("正常問候訊息"), [])


if __name__ == "__main__":
    unittest.main()
