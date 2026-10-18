"""Provider catalog provenance and discoverability tests."""
import unittest
from ainexus.catalog import CATALOG, get_providers, validate_evidence


class CatalogTests(unittest.TestCase):
    def test_provider_identity_and_discovery(self):
        ids = [p.id for p in CATALOG]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertGreaterEqual(len(ids), 12)
        self.assertTrue(all(p.documentation.startswith("https://") for p in CATALOG))
        self.assertTrue(all(p.checked_at is None for p in CATALOG))
        self.assertTrue(all(p.free_allowance == "unknown" for p in CATALOG))

    def test_capability_filter(self):
        results = get_providers("search")
        self.assertEqual({p["id"] for p in results}, {"tavily", "brave"})
        self.assertEqual(get_providers("not-real"), [])

    def test_evidence(self):
        item = {"provider_id": "groq", "source_url": "https://console.groq.com/docs/rate-limits",
                "observed_at": "2026-10-18T08:00:00Z", "statement": "Check current tier.",
                "status": "reported"}
        self.assertEqual(validate_evidence(item), item)
        for change in ({"provider_id": "unknown"}, {"source_url": "file:///etc/passwd"},
                       {"observed_at": "not-a-date"}, {"status": "official"}):
            with self.subTest(change=change):
                with self.assertRaises(ValueError):
                    validate_evidence({**item, **change})


if __name__ == "__main__":
    unittest.main()
