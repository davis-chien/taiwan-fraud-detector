import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from pipeline.enricher import _parse_age_days, get_domain_info, _CACHE


class TestParseAgeDays(unittest.TestCase):
    def test_old_domain_returns_large_value(self):
        creation = datetime(2020, 1, 1, tzinfo=timezone.utc)
        result = _parse_age_days(creation)
        self.assertIsNotNone(result)
        self.assertGreater(result, 365)

    def test_new_domain_returns_small_value(self):
        now = datetime.now(timezone.utc)
        result = _parse_age_days(now)
        self.assertIsNotNone(result)
        self.assertEqual(result, 0)

    def test_list_input_uses_first_element(self):
        early = datetime(2020, 1, 1, tzinfo=timezone.utc)
        late = datetime(2024, 1, 1, tzinfo=timezone.utc)
        result = _parse_age_days([early, late])
        expected = _parse_age_days(early)
        self.assertEqual(result, expected)

    def test_naive_datetime_treated_as_utc(self):
        creation = datetime(2020, 1, 1)
        result = _parse_age_days(creation)
        self.assertIsNotNone(result)
        self.assertGreater(result, 0)

    def test_none_returns_none(self):
        self.assertIsNone(_parse_age_days(None))

    def test_non_datetime_returns_none(self):
        self.assertIsNone(_parse_age_days("2020-01-01"))
        self.assertIsNone(_parse_age_days(12345))


class TestGetDomainInfo(unittest.TestCase):
    def setUp(self):
        _CACHE.clear()

    @patch("pipeline.enricher.whois.whois")
    def test_returns_age_and_registrar(self, mock_whois):
        mock_result = MagicMock()
        mock_result.creation_date = datetime(2022, 1, 1, tzinfo=timezone.utc)
        mock_result.registrar = "GoDaddy"
        mock_whois.return_value = mock_result

        result = get_domain_info("example.com")

        self.assertEqual(result["hostname"], "example.com")
        self.assertIsNotNone(result["domain_age_days"])
        self.assertGreater(result["domain_age_days"], 0)
        self.assertEqual(result["registrar"], "GoDaddy")
        self.assertIsNone(result["error"])

    @patch("pipeline.enricher.whois.whois")
    def test_handles_whois_failure_gracefully(self, mock_whois):
        mock_whois.side_effect = Exception("WHOIS lookup failed")

        result = get_domain_info("no-whois.tw")

        self.assertIsNotNone(result["error"])
        self.assertIsNone(result["domain_age_days"])
        self.assertIsNone(result["registrar"])

    @patch("pipeline.enricher.whois.whois")
    def test_result_is_cached(self, mock_whois):
        mock_result = MagicMock()
        mock_result.creation_date = datetime(2022, 1, 1, tzinfo=timezone.utc)
        mock_result.registrar = "TestReg"
        mock_whois.return_value = mock_result

        get_domain_info("cached.com")
        get_domain_info("cached.com")

        self.assertEqual(mock_whois.call_count, 1)

    @patch("pipeline.enricher.whois.whois")
    def test_different_hosts_not_conflated(self, mock_whois):
        mock_result = MagicMock()
        mock_result.creation_date = datetime(2022, 1, 1, tzinfo=timezone.utc)
        mock_result.registrar = "Reg"
        mock_whois.return_value = mock_result

        get_domain_info("alpha.com")
        get_domain_info("beta.com")

        self.assertEqual(mock_whois.call_count, 2)

    def test_empty_hostname_returns_null_age(self):
        result = get_domain_info("")
        self.assertIsNone(result["domain_age_days"])

    @patch("pipeline.enricher.whois.whois")
    def test_none_registrar_handled(self, mock_whois):
        mock_result = MagicMock()
        mock_result.creation_date = datetime(2021, 6, 1, tzinfo=timezone.utc)
        mock_result.registrar = None
        mock_whois.return_value = mock_result

        result = get_domain_info("no-registrar.tw")
        self.assertIsNone(result["registrar"])
        self.assertIsNone(result["error"])


if __name__ == "__main__":
    unittest.main()
