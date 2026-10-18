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
from urllib.parse import urlsplit

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
HTML = """<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>AI Nexus · v0.1</title><style>body{font:16px system-ui;background:#10141c;color:#e5eaf2;max-width:850px;margin:3rem auto;padding:0 1rem}button,input,textarea{font:inherit;border:1px solid #687587;border-radius:6px;padding:.6rem;background:#202a39;color:white}button{cursor:pointer}section{background:#18212f;padding:1rem;border-radius:10px;margin:1rem 0}pre{white-space:pre-wrap;overflow-wrap:anywhere}label{display:block;margin:.6rem 0}input,textarea{width:95%;max-width:100%}a{color:#93ccff}</style>
<h1>AI Nexus <small>v0.1</small></h1><p>Local-first discovery and execution. Cloud providers are catalog entries only; no cloud inference is enabled.</p>
<section><h2>Provider catalog</h2><div id="providers">Loading...</div></section>
<section><h2>Local discovery</h2><button id="discover">Discover local models</button><pre id="models">Not checked yet</pre></section>
<section><h2>Test inference</h2><label>Discovered model ID<input id="model" placeholder="Choose an ID returned by discovery"></label><label>Prompt<textarea id="prompt" rows="3">Reply with a short hello.</textarea></label><button id="run">Run local request</button><pre id="result">No request yet</pre></section>
<script>
async function req(path,options){let r=await fetch(path,options);let j=await r.json();if(!r.ok)throw Error(j.error||r.status);return j}
(async()=>{try{let p=await req('/providers');document.querySelector('#providers').textContent=p.map(x=>x.name).join(' · ')}catch(e){document.querySelector('#providers').textContent=e.message}})();
document.querySelector('#discover').onclick=async()=>{let el=document.querySelector('#models');el.textContent='Checking...';try{let v=await req('/discover/local',{method:'POST'});el.textContent=JSON.stringify(v,null,2);if(v.models[0])document.querySelector('#model').value=v.models[0].id}catch(e){el.textContent=e.message}};
document.querySelector('#run').onclick=async()=>{let el=document.querySelector('#result');el.textContent='Running...';try{let v=await req('/execute',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({model:document.querySelector('#model').value,prompt:document.querySelector('#prompt').value})});el.textContent=JSON.stringify(v,null,2)}catch(e){el.textContent=e.message}};
</script></html>"""


def database():
    connection = sqlite3.connect(DB, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("CREATE TABLE IF NOT EXISTS models (id TEXT PRIMARY KEY, discovered_at INTEGER NOT NULL)")
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
        return json.loads(response.read(2_000_001))


class Handler(BaseHTTPRequestHandler):
    def respond(self, status, payload, content_type="application/json"):
        contents = json.dumps(payload).encode() if content_type == "application/json" else payload.encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type + "; charset=utf-8")
        self.send_header("Content-Length", str(len(contents)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(contents)

    def do_GET(self):
        if self.path == "/":
            return self.respond(200, HTML, "text/html")
        if self.path == "/health":
            return self.respond(200, {"ok": True, "version": "0.1.0"})
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
        if self.path not in ("/discover/local", "/execute"):
            return self.respond(404, {"error": "Not found"})
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if size < 0 or size > 16384:
                return self.respond(413, {"error": "Request too large"})
            body = json.loads(self.rfile.read(size)) if size else {}
            if not isinstance(body, dict):
                return self.respond(400, {"error": "JSON object required"})
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
            return self.respond(502, {"error": "Invalid upstream response or request: " + str(exc)[:180]})

    def log_message(self, fmt, *args):
        print("%s - %s" % (self.address_string(), fmt % args))


def main():
    host = os.getenv("AI_NEXUS_HOST", "127.0.0.1")
    port = int(os.getenv("AI_NEXUS_PORT", "8765"))
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
