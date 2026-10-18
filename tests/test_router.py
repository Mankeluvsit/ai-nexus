import unittest
from ainexus.router import choose_model


class RouterTests(unittest.TestCase):
    def test_default_blocks_cloud_even_when_price_is_zero(self):
        models = [{"id": "cloud", "kind": "cloud", "provider_id": "x",
                   "price_status": "verified", "pricing": {"input_per_token_usd": "0",
                   "output_per_token_usd": "0"}}]
        self.assertEqual(choose_model(models)["decision"], "blocked")

    def test_local_first(self):
        models = [{"id": "z-local", "kind": "local", "available": True},
                  {"id": "cloud", "kind": "cloud", "price_status": "verified",
                   "pricing": {"input_per_token_usd": "0", "output_per_token_usd": "0"}}]
        self.assertEqual(choose_model(models, cloud_enabled=True)["selected"], "z-local")

    def test_unknown_pricing_never_defaults_to_free(self):
        models = [{"id": "cloud", "kind": "cloud", "price_status": "unknown", "pricing": {}}]
        self.assertEqual(choose_model(models, cloud_enabled=True)["decision"], "blocked")

    def test_explicit_cloud_zero_spend(self):
        models = [{"id": "cloud", "kind": "cloud", "price_status": "verified",
                   "pricing": {"input_per_token_usd": "0", "output_per_token_usd": "0"}}]
        self.assertEqual(choose_model(models, cloud_enabled=True)["selected"], "cloud")

    def test_reported_free_requires_second_opt_in(self):
        models = [{"id": "cloud", "kind": "cloud", "price_status": "reported_unverified",
                   "pricing": {"input_per_token_usd": "0", "output_per_token_usd": "0"}}]
        self.assertIsNone(choose_model(models, cloud_enabled=True)["selected"])
        self.assertEqual(choose_model(models, cloud_enabled=True, allow_reported_free=True)["selected"], "cloud")

    def test_context_and_price_caps(self):
        models = [{"id": "local", "kind": "local", "available": True, "context_window": 4096},
                  {"id": "cloud", "kind": "cloud", "price_status": "verified", "context_window": 8192,
                   "pricing": {"input_per_token_usd": "0.0001", "output_per_token_usd": "0"}}]
        self.assertIsNone(choose_model(models, required_context=8192, cloud_enabled=True)["selected"])
        self.assertEqual(choose_model(models, required_context=8192, cloud_enabled=True,
                                      max_input_price="0.0001")["selected"], "cloud")


if __name__ == "__main__":
    unittest.main()
