"""Offline end-to-end HTTP tests: no LM Studio or cloud credentials required."""
import json
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from contextlib import closing
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

from ainexus import __main__ as nexus


class FakeInference(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/v1/models":
            self.send_json({"data": [{"id": "offline-fixture"}]})
        else:
            self.send_json({"error": "not found"}, 404)

    def do_POST(self):
        data = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))
        if self.path == "/v1/chat/completions" and data["model"] == "offline-fixture":
            self.send_json({"choices": [{"message": {"content": "hello from test model"}}], "usage": {"prompt_tokens": 4, "completion_tokens": 5}})
        else:
            self.send_json({"error": "not found"}, 404)

    def send_json(self, value, code=200):
        raw = json.dumps(value).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, *args):
        pass


class OfflineIntegration(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.mock = ThreadingHTTPServer(("127.0.0.1", 0), FakeInference)
        self.app = ThreadingHTTPServer(("127.0.0.1", 0), nexus.Handler)
        self.addCleanup(self.app.server_close)
        self.addCleanup(self.mock.server_close)
        self.patches = [
            patch.object(nexus, "DB", os.path.join(self.temp.name, "test.sqlite")),
            patch.object(nexus, "ENDPOINT", "http://127.0.0.1:%s/v1" % self.mock.server_port),
        ]
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)
        self.threads = []
        for server in (self.mock, self.app):
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            self.threads.append(thread)
            self.addCleanup(server.shutdown)

    def request(self, path, body=None, headers=None):
        raw = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(
            "http://127.0.0.1:%s%s" % (self.app.server_port, path),
            data=raw,
            headers=headers or ({"Content-Type": "application/json"} if raw is not None else {}),
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as res:
                data = res.read()
                return res.status, json.loads(data) if path != "/" else data.decode(), res.headers
        except urllib.error.HTTPError as err:
            return err.code, json.loads(err.read()), err.headers

    def test_health_and_catalog(self):
        code, data, headers = self.request("/health")
        self.assertEqual(code, 200)
        self.assertTrue(data["ok"])
        self.assertEqual(headers["X-Frame-Options"], "DENY")
        code, providers, _ = self.request("/providers")
        self.assertEqual(code, 200)
        self.assertGreaterEqual(len(providers), 5)
        self.assertTrue(all(p["verification"] == "not_checked" for p in providers))

    def test_catalog_api(self):
        code, providers, _ = self.request("/catalog")
        self.assertEqual(code, 200)
        self.assertGreaterEqual(len(providers), 12)
        self.assertTrue(all(p["free_allowance"] == "unknown" for p in providers))
        self.assertTrue(all(p["checked_at"] is None for p in providers))
        code, capabilities, _ = self.request("/catalog/capabilities")
        self.assertEqual(code, 200)
        self.assertIn("search", capabilities)
        self.assertIn("tools", capabilities)

    def test_public_model_search_pagination_and_freshness(self):
        with closing(nexus.database()) as con:
            now = int(__import__("time").time())
            for name, context, age in (("alpha", 8000, 0), ("alphabet", None, 8000), ("beta", 16000, 0)):
                con.execute("INSERT INTO public_models VALUES (?,?,?,?,?)",
                            ("openrouter", name, context, now-age, "https://openrouter.ai/api/v1/models"))
            con.commit()
        code, data, _ = self.request("/discovery/public?limit=1&offset=0&q=alpha")
        self.assertEqual(code, 200)
        self.assertEqual(data["total"], 2)
        self.assertEqual(data["models"][0]["id"], "alpha")
        self.assertFalse(data["models"][0]["stale"])
        code, data, _ = self.request("/discovery/public?limit=1&offset=1&q=alpha")
        self.assertEqual(code, 200)
        self.assertEqual(data["models"][0]["id"], "alphabet")
        self.assertTrue(data["models"][0]["stale"])
        self.assertIsNone(data["models"][0]["context_window"])
        code, _, _ = self.request("/discovery/public?limit=500")
        self.assertEqual(code, 400)
        code, data, _ = self.request("/discovery/public?q=%25")
        self.assertEqual(code, 200)
        self.assertEqual(data["total"], 0)

    def test_discover_execute_persist(self):
        code, result, _ = self.request("/discover/local", {})
        self.assertEqual(code, 200)
        self.assertEqual(result["count"], 1)
        code, result, _ = self.request("/execute", {"model": "offline-fixture", "prompt": "hello"})
        self.assertEqual(code, 200)
        self.assertEqual(result["reply"], "hello from test model")
        self.assertEqual(result["usage"]["completion_tokens"], 5)
        code, history, _ = self.request("/executions")
        self.assertEqual(code, 200)
        self.assertEqual(history[0]["model"], "offline-fixture")
        self.assertNotIn("hello", json.dumps(history))
        with closing(nexus.database()) as con:
            self.assertEqual(con.execute("SELECT COUNT(*) FROM executions").fetchone()[0], 1)

    def test_invalid_model_and_origin(self):
        code, _, _ = self.request("/execute", {"model": "unknown", "prompt": "x"})
        self.assertEqual(code, 400)
        code, _, _ = self.request("/discover/local", {}, {"Content-Type": "application/json", "Origin": "https://evil.example"})
        self.assertEqual(code, 403)
        code, _, _ = self.request("/execute", {"model": "offline-fixture", "prompt": "x"}, {"Content-Type": "text/plain"})
        self.assertEqual(code, 415)

    def test_html_served(self):
        code, markup, _ = self.request("/")
        self.assertEqual(code, 200)
        self.assertIn("Discovery Hub", markup)
        self.assertIn('data-view="settings"', markup)


if __name__ == "__main__":
    unittest.main()
