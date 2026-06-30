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

ENRICHMENT_PROMPT_VERSION = 4

SYSTEM_PROMPT = (
    "You are an expert customer experience analyst for a multi-tenant retail "
    "platform. For every review you receive, return STRICTLY structured JSON "
    "with three keys:\n"
    "  - sentiment: one of 'positive', 'neutral', 'negative'\n"
    "  - tags: list of 1 to 5 short English tags. Each tag has a 'label' "
    "(2-4 words, lowercase, English), a 'polarity' (positive|neutral|negative), "
    "a 'canonical' label that normalises the tag into a reusable category "
    "(Title Case, at most 3 words, ALWAYS in English), and a 'polarity_type' "
    "(always_positive|always_negative|mixed) describing how that canonical "
    "category generally trends. Set 'polarity_type' ONLY when you PROPOSE a NEW "
    "canonical label; otherwise leave it null. "
    "ALWAYS write tags AND canonical labels in English regardless of the "
    "review's language.\n"
    "  - action_items: list of 0 to 5 actionable next steps. Each item has a "
    "'title' (under 200 chars, English imperative phrase), a 'scope' "
    "(use 'shop' for issues specific to the location like 'Fix broken AC'; "
    "use 'brand' for systemic patterns like 'Improve staff training across "
    "all shops'), a 'priority' ('high'|'medium'|'low'), and a 'category' chosen "
    "from these five values:\n"
    "    • 'quality' — the physical product, food, drinks, materials, packaging, "
    "freshness, ingredient quality, build quality.\n"
    "    • 'service' — anything involving people on the team: staff behaviour, "
    "friendliness, attitude, attentiveness, knowledge, communication style, "
    "responsiveness to questions, follow-up with customers, replies to inquiries, "
    "handling complaints, training.\n"
    "    • 'experience' — the overall feel of the visit: ambience, atmosphere, "
    "cleanliness, decor, music, lighting, comfort, vibe, aesthetics.\n"
    "    • 'operations' — processes and logistics: wait time, queue length, "
    "speed of service, delivery, order accuracy, billing/payment, opening hours, "
    "scheduling, internal procedures, workflow, photo/document handling "
    "processes, reservation systems, technology and tooling.\n"
    "    • 'other' — ONLY when the action item truly does not relate to any of "
    "the four categories above. This is a LAST RESORT, not a safe default. "
    "Before choosing 'other', re-read the four categories and pick the closest "
    "match — most customer-experience action items map to one of them.\n"
    "Do not invent action items when none are warranted. Tags should reflect "
    "what was actually mentioned in the review."
)


def _build_canonical_vocab_block(canonical_vocab: list[str] | None) -> str:
    """Phase 22 (CTAG-03/D-02) — the map-or-propose instruction block.

    When the org already has canonical vocabulary, GPT is told to MAP each tag
    to one existing label when it fits and only PROPOSE a new one otherwise.
    When the vocabulary is empty (cold start), GPT proposes a canonical label
    for every tag. The list is pre-capped to the top-N by the caller (D-02).
    """
    if canonical_vocab:
        joined = ", ".join(canonical_vocab)
        return (
            "Existing canonical tag vocabulary for this brand: "
            f"{joined}.\n"
            "For each tag's 'canonical' field, MAP the tag to ONE existing label "
            "above when it clearly fits (reuse the exact label, and leave "
            "'polarity_type' null). If no existing label fits, PROPOSE a new "
            "canonical label (Title Case, at most 3 words, in English) and set "
            "its 'polarity_type'."
        )
    return (
        "There is no existing canonical tag vocabulary for this brand yet. "
        "For every tag, PROPOSE a canonical label (Title Case, at most 3 words, "
        "in English) and set its 'polarity_type' "
        "(always_positive|always_negative|mixed)."
    )


def build_enrichment_messages(
    *,
    review: Any,
    canonical_vocab: list[str] | None = None,
) -> list[dict[str, str]]:
    """Build the messages list for client.responses.parse(input=messages, ...).

    `review` is a Review instance with a select_related('shop__organisation')
    queryset so .shop.name and .shop.organisation.name are available without
    extra queries.

    `canonical_vocab` (Phase 22) is the org's capped canonical vocabulary
    (top-N by review_count). It is appended as a map-or-propose instruction so
    GPT reuses existing labels where possible and only proposes new ones when
    nothing fits.
    """
    brand = review.shop.organisation.name
    shop_name = review.shop.name
    user_payload = (
        f"Brand: {brand}\n"
        f"Shop: {shop_name}\n"
        f"Star rating: {review.star_rating} of 5\n"
        f"Review text:\n{review.comment or '(no comment provided)'}\n\n"
        f"{_build_canonical_vocab_block(canonical_vocab)}"
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
    # IN-05: use str.replace (not str.format) so brand names containing
    # literal braces (e.g., "Acme {Coffee}") do not trigger KeyError.
    system_content = template.replace("{brand_name}", brand_name)
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
