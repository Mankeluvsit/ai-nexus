"""Strict read-only model catalog discovery.

Public catalog access is explicit and optional. Redirects are forbidden, URLs are
hardcoded (not derived from user input), and no API keys or inference calls are made.
"""
import json
import time
import urllib.request
from urllib.parse import urlsplit

SOURCES = {
    "openrouter": "https://openrouter.ai/api/v1/models",
}
MAX_BYTES = 2_000_000
CACHE_SECONDS = 3600


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Catalog redirects are disabled")


def parse_openrouter(data):
    if not isinstance(data, dict) or not isinstance(data.get("data"), list):
        raise ValueError("Expected model data array")
    models = []
    for item in data["data"]:
        if not isinstance(item, dict):
            continue
        identifier = item.get("id")
        if not isinstance(identifier, str) or not (1 <= len(identifier) <= 256):
            continue
        context = item.get("context_length")
        if isinstance(context, bool) or not isinstance(context, int) or context <= 0:
            context = None
        models.append({"id": identifier, "context_window": context})
        if len(models) >= 10000:
            break
    return sorted(models, key=lambda x: x["id"])


def fetch_public_models(provider, *, opener=None):
    if provider not in SOURCES:
        raise ValueError("Provider does not offer an enabled public catalog connector")
    url = SOURCES[provider]
    target = urlsplit(url)
    if target.scheme != "https" or not target.hostname:
        raise ValueError("Catalog origin must be HTTPS")
    opener = opener or urllib.request.build_opener(NoRedirect)
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "AI-Nexus/0.3"}, method="GET")
    with opener.open(req, timeout=12) as response:
        if response.status != 200:
            raise ValueError("Catalog HTTP status invalid")
        raw = response.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise ValueError("Catalog response exceeds size limit")
    document = json.loads(raw)
    parsed = parse_openrouter(document)
    return {"provider_id": provider, "source_url": url, "fetched_at": int(time.time()), "models": parsed}
