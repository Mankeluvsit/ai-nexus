import unittest

from ainexus.normalization import normalize_openrouter, compare_models


class NormalizationTests(unittest.TestCase):
    def test_unknown_is_not_free(self):
        result = normalize_openrouter({"id": "example", "context_length": 32768})
        self.assertEqual(result["free_eligibility"], "unknown")
        self.assertIsNone(result["remaining_quota"])
        self.assertEqual(result["price_status"], "unknown")

    def test_zero_price_is_only_a_reported_claim(self):
        result = normalize_openrouter({"id": "example", "pricing": {"prompt": "0", "completion": "0"}})
        self.assertEqual(result["price_status"], "reported_unverified")
        self.assertEqual(result["free_eligibility"], "unknown")
        self.assertEqual(result["pricing"]["input_per_token_usd"], "0")

    def test_bad_pricing_and_context(self):
        for value in (True, -1, "NaN", "Infinity", "bad", None):
            with self.subTest(value=value):
                result = normalize_openrouter({"id": "example", "context_length": True,
                                               "pricing": {"prompt": value, "completion": 0}})
                self.assertIsNone(result["context_window"])
                self.assertIsNone(result["pricing"]["input_per_token_usd"])

    def test_comparison_does_not_invent_winner(self):
        result = compare_models({"id": "a"}, {"id": "b"})
        self.assertIsNone(result["winner"])
        self.assertIn("benchmark", result["reason"])


if __name__ == "__main__":
    unittest.main()
