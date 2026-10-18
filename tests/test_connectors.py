"""Credentials stay scoped to allowlisted catalog origins; no live network required."""
import json
import unittest
from unittest.mock import patch

from ainexus.connectors import CONNECTORS, configured_connectors, fetch_authenticated_models


class FakeResponse:
    status = 200
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def read(self, n):
        return json.dumps({"data": [{"id": "mock-model", "context_length": 8192}]}).encode()


class FakeOpener:
    def __init__(self): self.calls = []
    def open(self, req, timeout):
        self.calls.append((req.full_url, req.get_header("Authorization"), timeout, req.get_method()))
        return FakeResponse()


class ConnectorTests(unittest.TestCase):
    def test_no_secret_exposure(self):
        env = {"AI_NEXUS_GROQ_KEY": "never-share-this-key"}
        output = configured_connectors(env)
        self.assertTrue(next(x for x in output if x["id"] == "groq")["configured"])
        self.assertNotIn("never-share-this-key", json.dumps(output))
        self.assertFalse(next(x for x in output if x["id"] == "mistral")["configured"])

    def test_scoped_read_only_request(self):
        fake = FakeOpener()
        result = fetch_authenticated_models("groq", environ={"AI_NEXUS_GROQ_KEY": "fixture-key"}, opener=fake)
        self.assertEqual(result["models"][0]["id"], "mock-model")
        self.assertEqual(fake.calls, [(CONNECTORS["groq"][0], "Bearer fixture-key", 12, "GET")])
        self.assertNotIn("fixture-key", json.dumps(result))

    def test_missing_key_and_unsupported_provider(self):
        for provider, env in (("groq", {}), ("other", {"AI_NEXUS_GROQ_KEY": "fixture"})):
            with self.subTest(provider=provider):
                with self.assertRaises(ValueError):
                    fetch_authenticated_models(provider, environ=env, opener=FakeOpener())

    def test_reject_header_injection(self):
        with self.assertRaises(ValueError):
            fetch_authenticated_models("groq", environ={"AI_NEXUS_GROQ_KEY": "key\r\nBad: value"}, opener=FakeOpener())


if __name__ == "__main__":
    unittest.main()
