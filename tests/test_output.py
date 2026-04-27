import unittest

from pydantic import ValidationError

from pipeline.output import FraudVerdict


def _base() -> dict:
    return {
        "verdict": "fraud",
        "confidence": 0.9,
        "matched_patterns": ["bank_phishing"],
        "message_signals": ["urgency"],
        "url_signals": ["suspicious_tld"],
        "plain_summary": "這是詐騙訊息。",
    }


class TestFraudVerdict(unittest.TestCase):
    def test_all_three_verdicts_accepted(self):
        for v in ("fraud", "suspicious", "safe"):
            kw = {**_base(), "verdict": v}
            fv = FraudVerdict(**kw)
            self.assertEqual(fv.verdict, v)

    def test_invalid_verdict_raises(self):
        with self.assertRaises(ValidationError):
            FraudVerdict(**{**_base(), "verdict": "unknown"})

    def test_confidence_clamped_above_one(self):
        fv = FraudVerdict(**{**_base(), "confidence": 1.5})
        self.assertEqual(fv.confidence, 1.0)

    def test_confidence_clamped_below_zero(self):
        fv = FraudVerdict(**{**_base(), "confidence": -0.3})
        self.assertEqual(fv.confidence, 0.0)

    def test_confidence_valid_range_unchanged(self):
        fv = FraudVerdict(**{**_base(), "confidence": 0.75})
        self.assertAlmostEqual(fv.confidence, 0.75)

    def test_domain_age_days_defaults_to_none(self):
        fv = FraudVerdict(**_base())
        self.assertIsNone(fv.domain_age_days)

    def test_domain_age_days_set(self):
        fv = FraudVerdict(**{**_base(), "domain_age_days": 15})
        self.assertEqual(fv.domain_age_days, 15)

    def test_empty_matched_patterns_allowed(self):
        fv = FraudVerdict(**{**_base(), "matched_patterns": []})
        self.assertEqual(fv.matched_patterns, [])

    def test_multiple_matched_patterns(self):
        patterns = ["bank_phishing", "government_impersonation"]
        fv = FraudVerdict(**{**_base(), "matched_patterns": patterns})
        self.assertEqual(fv.matched_patterns, patterns)

    def test_missing_required_field_raises(self):
        kw = _base()
        del kw["plain_summary"]
        with self.assertRaises(ValidationError):
            FraudVerdict(**kw)

    def test_model_copy_updates_field(self):
        fv = FraudVerdict(**_base())
        updated = fv.model_copy(update={"domain_age_days": 42})
        self.assertEqual(updated.domain_age_days, 42)
        self.assertIsNone(fv.domain_age_days)


if __name__ == "__main__":
    unittest.main()
