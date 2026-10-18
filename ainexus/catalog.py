"""Evidence-aware provider registry. No network calls and no unverifiable quota claims."""
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Optional


@dataclass(frozen=True)
class Provider:
    id: str
    name: str
    documentation: str
    api_base: Optional[str] = None
    auth: str = "api_key"
    capabilities: tuple = ("text",)
    access: str = "verify_account"
    free_allowance: str = "unknown"
    verification: str = "documentation_reference"
    checked_at: Optional[str] = None

    def to_dict(self):
        result = asdict(self)
        result["capabilities"] = list(self.capabilities)
        return result


CATALOG = (
    Provider("google", "Google AI Studio", "https://ai.google.dev/gemini-api/docs/rate-limits", capabilities=("text", "vision", "audio", "tools")),
    Provider("groq", "Groq", "https://console.groq.com/docs/rate-limits", "https://api.groq.com/openai/v1", capabilities=("text", "audio", "tools")),
    Provider("openrouter", "OpenRouter", "https://openrouter.ai/docs", "https://openrouter.ai/api/v1", capabilities=("text", "vision", "tools")),
    Provider("mistral", "Mistral", "https://docs.mistral.ai/", "https://api.mistral.ai/v1", capabilities=("text", "tools")),
    Provider("sambanova", "SambaNova", "https://docs.sambanova.ai/", "https://api.sambanova.ai/v1"),
    Provider("cerebras", "Cerebras", "https://inference-docs.cerebras.ai/", "https://api.cerebras.ai/v1"),
    Provider("nvidia", "NVIDIA NIM", "https://docs.api.nvidia.com/", "https://integrate.api.nvidia.com/v1"),
    Provider("cloudflare", "Cloudflare Workers AI", "https://developers.cloudflare.com/workers-ai/", capabilities=("text", "vision", "audio", "embeddings")),
    Provider("huggingface", "Hugging Face", "https://huggingface.co/docs/inference-providers/", capabilities=("text", "vision", "embeddings")),
    Provider("tavily", "Tavily", "https://docs.tavily.com/", capabilities=("search",)),
    Provider("brave", "Brave Search", "https://api-dashboard.search.brave.com/app/documentation/web-search/get-started", capabilities=("search",)),
    Provider("jina", "Jina AI", "https://jina.ai/reader/", capabilities=("retrieval", "embeddings")),
)


def get_providers(capability=None):
    if capability is not None and capability not in {x for p in CATALOG for x in p.capabilities}:
        return []
    return [p.to_dict() for p in CATALOG if capability is None or capability in p.capabilities]


def validate_evidence(record):
    """Accept only explicit verification provenance, never imply that a cited limit is current."""
    if not isinstance(record, dict):
        raise ValueError("Evidence record must be an object")
    required = ("provider_id", "source_url", "observed_at", "statement", "status")
    if any(not isinstance(record.get(k), str) or not record[k].strip() for k in required):
        raise ValueError("Missing evidence field")
    if record["provider_id"] not in {p.id for p in CATALOG}:
        raise ValueError("Unknown provider")
    from urllib.parse import urlsplit
    target = urlsplit(record["source_url"])
    if target.scheme != "https" or not target.hostname:
        raise ValueError("Evidence source must be HTTPS")
    try:
        datetime.fromisoformat(record["observed_at"].replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("Invalid observed_at timestamp")
    if record["status"] not in ("reported", "verified", "stale", "disputed"):
        raise ValueError("Invalid evidence status")
    if len(record["statement"]) > 1500 or len(record["source_url"]) > 2048:
        raise ValueError("Evidence too long")
    return {k: record[k] for k in required}
