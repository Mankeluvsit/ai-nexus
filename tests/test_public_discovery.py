"""Offline public discovery tests, with no calls to any external provider."""
import io
import json
import os
import tempfile
import unittest
from unittest.mock import patch
from contextlib import closing

from ainexus import __main__ as app
from ainexus.discovery import parse_openrouter, fetch_public_models, MAX_BYTES


class FakeResponse:
    status = 200
    def __init__(self, data):
        self.stream = io.BytesIO(data)
    def read(self, size):
        return self.stream.read(size)
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return None


class FakeOpener:
    def __init__(self, payload):
        self.payload = payload
        self.calls = 0
    def open(self, request, timeout):
        self.calls += 1
        assert request.full_url == "https://openrouter.ai/api/v1/models"
        assert timeout <= 12
        return FakeResponse(self.payload)


class DiscoveryTests(unittest.TestCase):
    def test_schema_validation(self):
        with self.assertRaises(ValueError):
            parse_openrouter({"foo": []})
        records = parse_openrouter({"data": [{"id": "test", "context_length": 128000},
                                             {"id": "bad", "context_length": True},
                                             {"id": ""}, {"other": 3}]})
        self.assertEqual([item["id"] for item in records], ["bad", "test"])
        self.assertIsNone(records[0]["context_window"])
        self.assertEqual(records[1]["context_window"], 128000)
        self.assertEqual(records[0]["free_eligibility"], "unknown")
        self.assertIsNone(records[0]["remaining_quota"])

    def test_allowlist_and_payload_limit(self):
        with self.assertRaises(ValueError):
            fetch_public_models("google")
        payload = json.dumps({"data": [{"id": "model-one", "context_length": 4096}]}).encode()
        fake = FakeOpener(payload)
        result = fetch_public_models("openrouter", opener=fake)
        self.assertEqual(fake.calls, 1)
        self.assertEqual(result["models"][0]["id"], "model-one")
        with self.assertRaises(ValueError):
            fetch_public_models("openrouter", opener=FakeOpener(b"x" * (MAX_BYTES + 1)))

    def test_local_storage_schemas(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(app, "DB", os.path.join(folder, "db.sqlite")):
                with closing(app.database()) as con:
                    con.execute("INSERT INTO public_models VALUES (?,?,?,?,?)",
                                ("openrouter", "unit-fixture", 8192, 123, "https://openrouter.ai/api/v1/models"))
                    con.execute("INSERT INTO public_refresh VALUES (?,?,?)",
                                ("openrouter", 123, "https://openrouter.ai/api/v1/models"))
                    con.commit()
                with closing(app.database()) as con:
                    self.assertEqual(con.execute("SELECT context_window FROM public_models").fetchone()[0], 8192)
                    self.assertEqual(con.execute("SELECT fetched_at FROM public_refresh").fetchone()[0], 123)


if __name__ == "__main__":
    unittest.main()
