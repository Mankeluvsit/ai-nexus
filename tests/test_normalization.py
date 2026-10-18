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

    def test_misleading_free_claims_cannot_promote_evidence(self):
        model = {"id": "example:free", "pricing": {"prompt": "0", "completion": "0"}}
        baseline = normalize_openrouter(model)
        claims = {
            "paid_account_required": {"requires_paid_account": True},
            "hidden_quotas": {"rate_limit": "undisclosed", "remaining_quota": 1000},
            "first_month_only": {"free_trial_months": 1, "credits": 10},
            "injected_verification": {"price_status": "verified", "free_eligibility": "verified",
                                      "tool_use_verified": True, "verified_at": "2026-10-18T00:00:00Z"},
            "advertised_tools": {"supported_parameters": ["tools", "tool_choice"]},
        }
        for scenario, metadata in claims.items():
            with self.subTest(scenario=scenario):
                result = normalize_openrouter({**model, **metadata})
                self.assertEqual(result, baseline)
                self.assertEqual(result["price_status"], "reported_unverified")
                self.assertEqual(result["free_eligibility"], "unknown")
                self.assertIsNone(result["remaining_quota"])
                self.assertIsNone(result["tool_use_verified"])

    def test_partial_and_mixed_prices_do_not_establish_free_access(self):
        for pricing, expected_status, expected_input, expected_output in (
            ({"prompt": "0"}, "unknown", "0", None),
            ({"completion": "0"}, "unknown", None, "0"),
            ({"prompt": "0", "completion": "0.001"}, "reported_unverified", "0", "0.001"),
            ({"prompt": "0.001", "completion": "0"}, "reported_unverified", "0.001", "0"),
        ):
            with self.subTest(pricing=pricing):
                result = normalize_openrouter({"id": "example:free", "pricing": pricing})
                self.assertEqual(result["price_status"], expected_status)
                self.assertEqual(result["pricing"], {"input_per_token_usd": expected_input,
                                                     "output_per_token_usd": expected_output})
                self.assertEqual(result["free_eligibility"], "unknown")
                self.assertIsNone(result["remaining_quota"])

    def test_comparison_does_not_invent_winner(self):
        result = compare_models({"id": "a"}, {"id": "b"})
        self.assertIsNone(result["winner"])
        self.assertIn("benchmark", result["reason"])


if __name__ == "__main__":
    unittest.main()
