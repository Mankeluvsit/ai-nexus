"""Normalize model catalog metadata without treating provider claims as verified facts.

Only documented fields are admitted. Unknown prices and quotas stay None.
"""
from decimal import Decimal, InvalidOperation

def _nonnegative_decimal(value):
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    if not number.is_finite() or number < 0:
        return None
    return str(number)

def normalize_openrouter(item):
    if not isinstance(item, dict):
        return None
    mid = item.get("id")
    if not isinstance(mid, str) or not 1 <= len(mid) <= 256:
        return None
    context = item.get("context_length")
    if type(context) is not int or context <= 0:
        context = None
    pricing = item.get("pricing") if isinstance(item.get("pricing"), dict) else {}
    # OpenRouter prices are typically USD per token. These are listed claims,
    # not proof of free access or a remaining account quota.
    prompt_price = _nonnegative_decimal(pricing.get("prompt"))
    completion_price = _nonnegative_decimal(pricing.get("completion"))
    return {
        "id": mid,
        "context_window": context,
        "pricing": {"input_per_token_usd": prompt_price, "output_per_token_usd": completion_price},
        "price_status": "reported_unverified" if prompt_price is not None and completion_price is not None else "unknown",
        "free_eligibility": "unknown",
        "remaining_quota": None,
        "tool_use_verified": None,
    }

def compare_models(left, right):
    """Return a factual, non-ranking comparison without inventing capabilities."""
    return {"left": normalize_openrouter(left), "right": normalize_openrouter(right),
            "winner": None, "reason": "No empirical benchmark or account-level quota verification"}
