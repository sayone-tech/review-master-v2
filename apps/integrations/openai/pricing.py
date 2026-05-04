"""Phase 12 — Cost formula.

calculate_cost is called from the OpenAI client wrapper at log time. The
result is locked into AiUsageLog.estimated_cost_usd and never recomputed —
historical costs are immune to future pricing changes (ENRCH-09).
"""

from __future__ import annotations

from decimal import Decimal

from apps.integrations.openai.models import AiPricing


def calculate_cost(
    *,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    cached_tokens: int = 0,
) -> Decimal:
    """Compute the dollar cost of a single OpenAI call.

    Token field naming uses the Chat Completions API names externally
    (prompt_tokens / completion_tokens / cached_tokens) — the Responses API
    in openai 2.x maps internally as: input_tokens -> prompt_tokens,
    output_tokens -> completion_tokens, input_tokens_details.cached_tokens
    -> cached_tokens. The client wrapper does that mapping before calling
    this function (see RESEARCH.md Pitfall 2).
    """
    pricing = AiPricing.objects.get_active(model=model)
    non_cached_input = max(0, prompt_tokens - cached_tokens)
    cost = (
        Decimal(non_cached_input) / Decimal(1_000_000) * pricing.input_token_price_per_1m
        + Decimal(cached_tokens) / Decimal(1_000_000) * pricing.cached_token_price_per_1m
        + Decimal(completion_tokens) / Decimal(1_000_000) * pricing.output_token_price_per_1m
    )
    return cost.quantize(Decimal("0.000001"))
