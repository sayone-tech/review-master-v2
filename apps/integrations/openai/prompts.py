"""Phase 12 — Versioned prompt templates for review enrichment.

Bumping ENRICHMENT_PROMPT_VERSION should be paired with bumping
Review.enrichment_version on rows that need re-enrichment (deferred to a
future phase per CONTEXT.md Deferred Ideas).

Per CONTEXT.md locked decisions:
  - prompt context = brand + shop name + review text + star rating
  - NO shop address
  - NO reviewer name
  - tags + action item titles + sentiment label MUST be in English regardless
    of review language (model handles translation)
"""

from __future__ import annotations

from typing import Any

ENRICHMENT_PROMPT_VERSION = 1

SYSTEM_PROMPT = (
    "You are an expert customer experience analyst for a multi-tenant retail "
    "platform. For every review you receive, return STRICTLY structured JSON "
    "with three keys:\n"
    "  - sentiment: one of 'positive', 'neutral', 'negative'\n"
    "  - tags: list of 1 to 5 short English tags. Each tag has a 'label' "
    "(2-4 words, lowercase, English) and 'polarity' (positive|neutral|negative). "
    "ALWAYS write tags in English regardless of the review's language.\n"
    "  - action_items: list of 0 to 5 actionable next steps. Each item has a "
    "'title' (under 200 chars, English imperative phrase), a 'scope' "
    "(use 'shop' for issues specific to the location like 'Fix broken AC'; "
    "use 'brand' for systemic patterns like 'Improve staff training across "
    "all shops'), and a 'priority' ('high'|'medium'|'low').\n"
    "Do not invent action items when none are warranted. Tags should reflect "
    "what was actually mentioned in the review."
)


def build_enrichment_messages(*, review: Any) -> list[dict[str, str]]:
    """Build the messages list for client.responses.parse(input=messages, ...).

    `review` is a Review instance with a select_related('shop__organisation')
    queryset so .shop.name and .shop.organisation.name are available without
    extra queries.
    """
    brand = review.shop.organisation.name
    shop_name = review.shop.name
    user_payload = (
        f"Brand: {brand}\n"
        f"Shop: {shop_name}\n"
        f"Star rating: {review.star_rating} of 5\n"
        f"Review text:\n{review.comment or '(no comment provided)'}"
    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_payload},
    ]
