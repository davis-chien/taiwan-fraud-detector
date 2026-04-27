import unittest

from pipeline.extractor import extract_url


class TestExtractor(unittest.TestCase):
    def test_extract_url_from_http_https_and_bare_domain(self):
        self.assertEqual(
            extract_url("請點擊 https://example.com/test 立即確認"),
            "https://example.com/test",
        )
        self.assertEqual(
            extract_url("網址是 www.example.com/abc，請小心"),
            "http://www.example.com/abc",
        )
        self.assertEqual(
            extract_url("詐騙連結 example.com/login 請勿點擊"),
            "example.com/login",
        )

    def test_extract_url_returns_none_for_no_link(self):
        self.assertIsNone(extract_url("沒有連結的訊息"))


if __name__ == "__main__":
    unittest.main()
