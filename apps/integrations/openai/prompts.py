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

ENRICHMENT_PROMPT_VERSION = 2

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
    "all shops'), a 'priority' ('high'|'medium'|'low'), and a 'category': "
    "classify as 'quality' (product/food standard), 'service' (staff behaviour, "
    "responsiveness), 'experience' (ambience, atmosphere, overall feel), "
    "'operations' (wait time, delivery, logistics, processes), or 'other' when "
    "none fit.\n"
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


# ---------------------------------------------------------------------------
# Phase 19 — AI reply generation prompts (D-04 through D-08).
#
# Two tones only: "professional" and "friendly". Both system prompts are
# locked verbatim per CONTEXT.md D-05/D-06. Bump REPLY_GENERATION_PROMPT_VERSION
# when wording changes so AiUsageLog can be filtered by prompt version.
# ---------------------------------------------------------------------------

REPLY_GENERATION_PROMPT_VERSION = 1

# WR-03: single source of truth for valid reply tones. Imported by the
# serializer (input validation) and the service (defensive check) so adding
# a new tone here propagates to all layers automatically.
ALLOWED_REPLY_TONES: tuple[str, ...] = ("professional", "friendly")

PROFESSIONAL_REPLY_SYSTEM_PROMPT = (
    "You are a professional customer experience representative replying to a "
    "Google Business review on behalf of {brand_name}. Write a formal, concise "
    "response that thanks the reviewer, acknowledges their experience, and "
    "invites them back. Under 150 words. No emojis. Do not invent facts."
)

FRIENDLY_REPLY_SYSTEM_PROMPT = (
    "You are a warm, friendly team member replying to a Google Business review "
    "on behalf of {brand_name}. Write a conversational, personable response "
    "that thanks the reviewer, acknowledges their experience, and feels "
    "genuinely human. Under 150 words. One emoji maximum. Do not invent facts."
)

_REPLY_PROMPTS_BY_TONE: dict[str, str] = {
    "professional": PROFESSIONAL_REPLY_SYSTEM_PROMPT,
    "friendly": FRIENDLY_REPLY_SYSTEM_PROMPT,
}

# WR-03: keep ALLOWED_REPLY_TONES and the prompt map in lock-step at import time.
if set(_REPLY_PROMPTS_BY_TONE.keys()) != set(ALLOWED_REPLY_TONES):
    raise RuntimeError(
        "ALLOWED_REPLY_TONES drifted from _REPLY_PROMPTS_BY_TONE — "
        "update both when adding a new tone."
    )


def build_reply_generation_messages(
    *,
    review: Any,
    tone: str,
    brand_name: str,
) -> list[dict[str, str]]:
    """Build the messages list for client.chat.completions.create.

    D-07: response is plain text (not structured JSON) — caller passes
    response_format={"type": "text"} on the API call.

    `review` is expected to expose .shop.name, .star_rating, .comment.
    Brand name is supplied separately so the caller (the service layer)
    does the Organisation lookup once.

    Raises ValueError for unknown tones (only "professional" and "friendly"
    are valid; serializer also validates at the API boundary).
    """
    template = _REPLY_PROMPTS_BY_TONE.get(tone)
    if template is None:
        raise ValueError(f"Unknown tone: {tone!r}")
    system_content = template.format(brand_name=brand_name)
    shop_name = review.shop.name
    user_payload = (
        f"Brand: {brand_name}\n"
        f"Shop: {shop_name}\n"
        f"Star rating: {review.star_rating} of 5\n"
        f"Review text:\n{review.comment or '(no comment provided)'}"
    )
    return [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_payload},
    ]
