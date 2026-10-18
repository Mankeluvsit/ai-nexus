"""Fail-closed, zero-spend-by-default model routing policy.

This module only selects a candidate; it never invokes a cloud API.
"""
from decimal import Decimal, InvalidOperation


def _cost(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        n = Decimal(str(value))
        return n if n.is_finite() and n >= 0 else None
    except (ValueError, InvalidOperation):
        return None


def choose_model(models, *, required_context=0, cloud_enabled=False,
                 allow_reported_free=False, max_input_price="0",
                 max_output_price="0"):
    """Return a decision with evidence, or an explicit refusal.

    Local candidates require `kind=local` and `available=True`.
    Cloud candidates require explicit opt-in plus verified zero-price evidence,
    unless allow_reported_free is explicitly enabled.
    """
    if type(required_context) is not int or required_context < 0:
        raise ValueError("required_context must be a nonnegative integer")
    input_cap, output_cap = _cost(max_input_price), _cost(max_output_price)
    if input_cap is None or output_cap is None:
        raise ValueError("Invalid price cap")
    candidates = []
    rejected = []
    for m in models:
        mid = m.get("id") if isinstance(m, dict) else None
        if not isinstance(mid, str) or not mid:
            rejected.append({"id": None, "reason": "invalid_record"})
            continue
        context = m.get("context_window")
        if required_context and (type(context) is not int or context < required_context):
            rejected.append({"id": mid, "reason": "insufficient_or_unknown_context"})
            continue
        if m.get("kind") == "local":
            if m.get("available") is True:
                candidates.append((0, mid, m))
            else:
                rejected.append({"id": mid, "reason": "local_unavailable"})
            continue
        if m.get("kind") != "cloud" or not cloud_enabled:
            rejected.append({"id": mid, "reason": "cloud_disabled"})
            continue
        pricing = m.get("pricing") if isinstance(m.get("pricing"), dict) else {}
        input_price = _cost(pricing.get("input_per_token_usd"))
        output_price = _cost(pricing.get("output_per_token_usd"))
        evidence = m.get("price_status")
        trusted = evidence == "verified" or (allow_reported_free and evidence == "reported_unverified")
        if not trusted or input_price is None or output_price is None:
            rejected.append({"id": mid, "reason": "price_unverified"})
        elif input_price > input_cap or output_price > output_cap:
            rejected.append({"id": mid, "reason": "price_cap_exceeded"})
        else:
            candidates.append((1, mid, m))
    candidates.sort(key=lambda row: (row[0], row[1]))
    selected = candidates[0][2] if candidates else None
    return {"selected": selected["id"] if selected else None,
            "provider": selected.get("provider_id") if selected else None,
            "decision": "selected" if selected else "blocked",
            "reason": "local_first" if selected and selected.get("kind") == "local" else
                      "cloud_explicitly_allowed" if selected else "no_eligible_model",
            "rejected": rejected}
