"""Local-first resource registry and inference API (standard library only)."""
import json
import os
import sqlite3
import time
import urllib.error
import urllib.request
from contextlib import closing
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from ipaddress import ip_address
from .catalog import get_providers, CATALOG
from .discovery import SOURCES, CACHE_SECONDS, fetch_public_models
from .connectors import configured_connectors, fetch_authenticated_models
from urllib.parse import urlsplit, parse_qs

DB = os.getenv("AI_NEXUS_DB", "ai-nexus.sqlite3")
ENDPOINT = os.getenv("AI_NEXUS_LOCAL_ENDPOINT", "http://127.0.0.1:1234/v1").rstrip("/")
KEY = os.getenv("AI_NEXUS_LOCAL_KEY", "")
PROVIDERS = [
    ("google", "Google AI Studio", "https://ai.google.dev/gemini-api/docs/rate-limits"),
    ("groq", "Groq", "https://console.groq.com/docs/rate-limits"),
    ("openrouter", "OpenRouter", "https://openrouter.ai/docs"),
    ("mistral", "Mistral", "https://docs.mistral.ai/"),
    ("sambanova", "SambaNova", "https://docs.sambanova.ai/"),
    ("cerebras", "Cerebras", "https://inference-docs.cerebras.ai/"),
    ("nvidia", "NVIDIA NIM", "https://docs.api.nvidia.com/"),
]
HTML = (Path(__file__).with_name("ui.html")).read_text(encoding="utf-8")


def database():
    connection = sqlite3.connect(DB, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("CREATE TABLE IF NOT EXISTS models (id TEXT PRIMARY KEY, discovered_at INTEGER NOT NULL)")
    connection.execute("CREATE TABLE IF NOT EXISTS public_models (provider_id TEXT NOT NULL, id TEXT NOT NULL, context_window INTEGER, fetched_at INTEGER NOT NULL, source_url TEXT NOT NULL, PRIMARY KEY(provider_id,id))")
    connection.execute("CREATE TABLE IF NOT EXISTS public_refresh (provider_id TEXT PRIMARY KEY, fetched_at INTEGER NOT NULL, source_url TEXT NOT NULL)")
    connection.execute("CREATE TABLE IF NOT EXISTS executions (id INTEGER PRIMARY KEY, model TEXT NOT NULL, elapsed_ms INTEGER NOT NULL, status TEXT NOT NULL, prompt_tokens INTEGER, completion_tokens INTEGER, created_at INTEGER NOT NULL)")
    connection.commit()
    return connection


def fetch_json(url, method="GET", data=None):
    headers = {"Accept": "application/json"}
    if KEY:
        headers["Authorization"] = "Bearer " + KEY
    if data is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=json.dumps(data).encode() if data is not None else None, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=30) as response:
        if response.status < 200 or response.status >= 300:
            raise ValueError("Unexpected upstream status")
        if int(response.headers.get("Content-Length", "0")) > 2_000_000:
            raise ValueError("Upstream response too large")
        payload = response.read(2_000_001)
        if len(payload) > 2_000_000:
            raise ValueError("Upstream response too large")
        return json.loads(payload)


class Handler(BaseHTTPRequestHandler):
    def valid_host(self):
        value = self.headers.get("Host", "")
        try:
            host = urlsplit("http://" + value).hostname
        except ValueError:
            return False
        return host in ("127.0.0.1", "localhost", "::1")

    def respond(self, status, payload, content_type="application/json"):
        contents = json.dumps(payload).encode() if content_type == "application/json" else payload.encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type + "; charset=utf-8")
        self.send_header("Content-Length", str(len(contents)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy", "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; img-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(contents)

    def do_GET(self):
        if not self.valid_host():
            return self.respond(403, {"error": "Local host required"})
        if self.path == "/":
            return self.respond(200, HTML, "text/html")
        if self.path == "/health":
            return self.respond(200, {"ok": True, "version": "0.1.0"})
        if self.path == "/connectors":
            return self.respond(200, configured_connectors())
        if self.path == "/catalog":
            return self.respond(200, get_providers())
        if self.path == "/catalog/capabilities":
            return self.respond(200, sorted({c for p in CATALOG for c in p.capabilities}))
        if self.path.split("?", 1)[0] == "/discovery/public":
            query = parse_qs(urlsplit(self.path).query)
            if any(k not in ("q", "limit", "offset", "provider") for k in query):
                return self.respond(400, {"error": "Unsupported query parameter"})
            try:
                limit = int(query.get("limit", ["100"])[0])
                offset = int(query.get("offset", ["0"])[0])
            except ValueError:
                return self.respond(400, {"error": "Invalid pagination"})
            if not 1 <= limit <= 200 or offset < 0 or offset > 1000000:
                return self.respond(400, {"error": "Pagination out of bounds"})
            search = query.get("q", [""])[0].strip()
            provider = query.get("provider", [""])[0].strip()
            if len(search) > 128 or len(provider) > 64:
                return self.respond(400, {"error": "Filter too long"})
            where = []
            params = []
            if search:
                where.append("id LIKE ? ESCAPE '!'")
                params.append("%" + search.replace("!", "!!").replace("%", "!%").replace("_", "!_") + "%")
            if provider:
                where.append("provider_id = ?")
                params.append(provider)
            clause = " WHERE " + " AND ".join(where) if where else ""
            with closing(database()) as con:
                total = con.execute("SELECT COUNT(*) FROM public_models" + clause, params).fetchone()[0]
                records = [dict(x) for x in con.execute("SELECT provider_id,id,context_window,fetched_at,source_url FROM public_models" + clause + " ORDER BY provider_id,id LIMIT ? OFFSET ?", params + [limit, offset])]
                refreshed = [dict(x) for x in con.execute("SELECT * FROM public_refresh ORDER BY provider_id")]
            now = int(time.time())
            for record in records:
                # The cache retains identity/provenance, not reported prices or
                # account-level evidence. Make that absence explicit to clients.
                record.update({
                    "pricing": {"input_per_token_usd": None, "output_per_token_usd": None},
                    "price_status": "unknown",
                    "free_eligibility": "unknown",
                    "remaining_quota": None,
                    "tool_use_verified": None,
                })
                record["age_seconds"] = max(0, now - record["fetched_at"])
                record["stale"] = record["age_seconds"] >= CACHE_SECONDS
            return self.respond(200, {"models": records, "refreshes": refreshed, "total": total, "limit": limit, "offset": offset})
        if self.path == "/providers":
            return self.respond(200, [{"id": i, "name": n, "docs": d, "verification": "not_checked"} for i, n, d in PROVIDERS])
        if self.path in ("/models", "/executions"):
            with closing(database()) as con:
                if self.path == "/models":
                    rows = con.execute("SELECT id, discovered_at FROM models ORDER BY id").fetchall()
                else:
                    rows = con.execute("SELECT * FROM executions ORDER BY id DESC LIMIT 50").fetchall()
            return self.respond(200, [dict(row) for row in rows])
        return self.respond(404, {"error": "Not found"})

    def do_POST(self):
        if not self.valid_host():
            return self.respond(403, {"error": "Local host required"})
        origin = self.headers.get("Origin")
        if origin:
            expected = "http://" + self.headers.get("Host", "")
            if origin != expected and origin != expected.replace("http://", "https://", 1):
                return self.respond(403, {"error": "Cross-origin request denied"})
        site = self.headers.get("Sec-Fetch-Site", "")
        if site and site not in ("same-origin", "none"):
            return self.respond(403, {"error": "Cross-site request denied"})
        if self.path == "/execute" and self.headers.get("Content-Type", "").split(";")[0].strip().lower() != "application/json":
            return self.respond(415, {"error": "JSON content type required"})
        if self.path not in ("/discover/local", "/discover/public", "/discover/authenticated", "/execute"):
            return self.respond(404, {"error": "Not found"})
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if size < 0 or size > 16384:
                return self.respond(413, {"error": "Request too large"})
            body = json.loads(self.rfile.read(size)) if size else {}
            if not isinstance(body, dict):
                return self.respond(400, {"error": "JSON object required"})
            if self.path == "/discover/authenticated":
                provider = body.get("provider")
                if not isinstance(provider, str) or provider not in {p["id"] for p in configured_connectors()}:
                    return self.respond(400, {"error": "Unsupported provider"})
                if not any(p["id"] == provider and p["configured"] for p in configured_connectors()):
                    return self.respond(400, {"error": "Credential not configured"})
                result = fetch_authenticated_models(provider)
                return self.respond(200, {"provider_id": provider, "count": len(result["models"]),
                                          "models": result["models"][:200],
                                          "source_url": result["source_url"],
                                          "persisted": False})
            if self.path == "/discover/public":
                provider = body.get("provider")
                if not isinstance(provider, str) or provider not in SOURCES:
                    return self.respond(400, {"error": "Unsupported public catalog"})
                with closing(database()) as con:
                    row = con.execute("SELECT fetched_at FROM public_refresh WHERE provider_id=?", (provider,)).fetchone()
                    if row and int(time.time()) - row["fetched_at"] < CACHE_SECONDS:
                        count = con.execute("SELECT count(*) FROM public_models WHERE provider_id=?", (provider,)).fetchone()[0]
                        return self.respond(200, {"provider_id": provider, "count": count, "cached": True})
                result = fetch_public_models(provider)
                with closing(database()) as con:
                    con.execute("BEGIN IMMEDIATE")
                    con.execute("DELETE FROM public_models WHERE provider_id=?", (provider,))
                    con.executemany("INSERT INTO public_models VALUES (?,?,?,?,?)", [
                        (provider, model["id"], model["context_window"], result["fetched_at"], result["source_url"])
                        for model in result["models"]])
                    con.execute("INSERT OR REPLACE INTO public_refresh VALUES (?,?,?)", (provider, result["fetched_at"], result["source_url"]))
                    con.commit()
                return self.respond(200, {"provider_id": provider, "count": len(result["models"]), "cached": False})
            if self.path == "/discover/local":
                upstream = fetch_json(ENDPOINT + "/models")
                models = upstream.get("data", [])
                if not isinstance(models, list):
                    raise ValueError("Invalid model response")
                selected = sorted({m["id"] for m in models if isinstance(m, dict) and isinstance(m.get("id"), str) and 0 < len(m["id"]) <= 256})
                now = int(time.time())
                with closing(database()) as con:
                    con.executemany("INSERT OR REPLACE INTO models (id,discovered_at) VALUES (?,?)", [(x, now) for x in selected])
                    con.commit()
                return self.respond(200, {"count": len(selected), "models": [{"id": x} for x in selected]})
            model, prompt = body.get("model"), body.get("prompt")
            if not isinstance(model, str) or not isinstance(prompt, str) or not 1 <= len(prompt) <= 10000 or len(model) > 256:
                return self.respond(400, {"error": "Valid model and prompt (1-10000 chars) required"})
            with closing(database()) as con:
                if not con.execute("SELECT 1 FROM models WHERE id=?", (model,)).fetchone():
                    return self.respond(400, {"error": "Model must be discovered first"})
            start = time.monotonic()
            output = fetch_json(ENDPOINT + "/chat/completions", "POST", {"model": model, "messages": [{"role": "user", "content": prompt}], "max_tokens": 256})
            elapsed = round((time.monotonic() - start) * 1000)
            reply = output["choices"][0]["message"].get("content", "")
            usage = output.get("usage") or {}
            with closing(database()) as con:
                con.execute("INSERT INTO executions (model,elapsed_ms,status,prompt_tokens,completion_tokens,created_at) VALUES (?,?,?,?,?,?)",
                    (model, elapsed, "success", usage.get("prompt_tokens"), usage.get("completion_tokens"), int(time.time())))
                con.commit()
            return self.respond(200, {"model": model, "reply": reply, "elapsed_ms": elapsed, "usage": usage})
        except (urllib.error.URLError, TimeoutError) as exc:
            return self.respond(502, {"error": "Local inference endpoint unavailable: " + type(exc).__name__})
        except (ValueError, KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            return self.respond(502, {"error": "Invalid upstream response or request: " + type(exc).__name__})

    def log_message(self, fmt, *args):
        print("%s - %s" % (self.address_string(), fmt % args))


def main():
    host = os.getenv("AI_NEXUS_HOST", "127.0.0.1")
    port = int(os.getenv("AI_NEXUS_PORT", "8765"))
    if host != "localhost" and not ip_address(host).is_loopback:
        raise SystemExit("AI Nexus v0.2 must bind to loopback; public binding requires authentication first")
    parsed = urlsplit(ENDPOINT)
    if parsed.scheme not in ("http", "https") or parsed.hostname not in ("127.0.0.1", "localhost", "::1"):
        raise SystemExit("Local endpoint must use loopback; remote provider integration is not enabled in v0.1")
    with closing(database()):
        pass
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"AI Nexus http://{host}:{port} | local endpoint {ENDPOINT}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
