import httpx
import unittest

from pipeline.unshortener import is_supported_shortener, unshorten_url


class TestUnshortener(unittest.TestCase):
    def test_is_supported_shortener_detects_known_shorteners(self):
        self.assertTrue(is_supported_shortener("http://bit.ly/abc"))
        self.assertTrue(is_supported_shortener("tinyurl.com/xyz"))
        self.assertFalse(is_supported_shortener("https://example.com/path"))

    def test_unshorten_url_resolves_shortened_redirect_chain(self):
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/abc":
                return httpx.Response(302, headers={"location": "https://example.com/final"})
            return httpx.Response(200, text="ok")

        transport = httpx.MockTransport(handler)
        client = httpx.Client(
            transport=transport,
            follow_redirects=True,
            timeout=httpx.Timeout(5.0, read=10.0, write=10.0, pool=5.0),
            max_redirects=3,
            trust_env=False,
        )

        final_url, changed, status, redirect_chain = unshorten_url(
            "http://bit.ly/abc", client=client
        )

        self.assertTrue(changed)
        self.assertEqual(final_url, "https://example.com/final")
        self.assertEqual(status, "resolved")
        self.assertTrue(len(redirect_chain) >= 1)


if __name__ == "__main__":
    unittest.main()
