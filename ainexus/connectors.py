"""Opt-in authenticated catalog connectors; credentials stay in process environment.

Only explicitly enumerated HTTPS model-list endpoints are contacted. Never
follow redirects or perform paid inference. Do not log tokens or response bodies.
"""
import json
import os
import urllib.request
from .discovery import NoRedirect, MAX_BYTES, parse_openrouter

CONNECTORS = {
    "groq": ("https://api.groq.com/openai/v1/models", "AI_NEXUS_GROQ_KEY"),
    "openrouter": ("https://openrouter.ai/api/v1/models", "AI_NEXUS_OPENROUTER_KEY"),
    "mistral": ("https://api.mistral.ai/v1/models", "AI_NEXUS_MISTRAL_KEY"),
    "cerebras": ("https://api.cerebras.ai/v1/models", "AI_NEXUS_CEREBRAS_KEY"),
}

def configured_connectors(environ=None):
    environ = os.environ if environ is None else environ
    return [{"id": k, "configured": bool(environ.get(env)), "endpoint": url}
            for k, (url, env) in CONNECTORS.items()]

def fetch_authenticated_models(provider, *, environ=None, opener=None):
    if provider not in CONNECTORS:
        raise ValueError("Unsupported authenticated provider")
    url, variable = CONNECTORS[provider]
    environ = os.environ if environ is None else environ
    key = environ.get(variable)
    if not key:
        raise ValueError("Credential not configured")
    if any(ord(c) < 33 or ord(c) > 126 for c in key):
        raise ValueError("Invalid credential format")
    opener = opener or urllib.request.build_opener(NoRedirect)
    request = urllib.request.Request(url, method="GET",
        headers={"Accept": "application/json", "Authorization": "Bearer " + key,
                 "User-Agent": "AI-Nexus/0.3"})
    with opener.open(request, timeout=12) as response:
        if response.status != 200:
            raise ValueError("Catalog response failed")
        raw = response.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise ValueError("Catalog too large")
    models = parse_openrouter(json.loads(raw))
    return {"provider_id": provider, "source_url": url, "models": models}
