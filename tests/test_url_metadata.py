import unittest

from pipeline.url_metadata import extract_url_metadata


class TestURLMetadata(unittest.TestCase):
    def test_extract_url_metadata_includes_redirect_chain_and_hostname(self):
        metadata = extract_url_metadata(
            final_url="https://example.com/final",
            original_url="http://bit.ly/abc",
            redirect_chain=["http://bit.ly/abc", "https://example.com/final"],
        )

        self.assertEqual(metadata["original_url"], "http://bit.ly/abc")
        self.assertEqual(metadata["final_url"], "https://example.com/final")
        self.assertEqual(metadata["redirect_hops"], 2)
        self.assertEqual(metadata["hostname"], "example.com")
        self.assertEqual(metadata["domain"], "example.com")
        self.assertEqual(metadata["path"], "/final")
        self.assertFalse(metadata["has_credentials"])

    def test_extract_url_metadata_handles_empty_chain(self):
        metadata = extract_url_metadata(final_url="https://example.com")
        self.assertEqual(metadata["redirect_chain"], [])
        self.assertEqual(metadata["redirect_hops"], 0)


if __name__ == "__main__":
    unittest.main()
