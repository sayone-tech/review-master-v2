"""Phase 12/22 — Pydantic schemas for the structured GPT response.

The OpenAI client wrapper passes EnrichmentResult to client.responses.parse()
as text_format. Pydantic validation on response.output_parsed is the structured
output contract — if validation fails, raise EnrichmentParseError (retry once
per ENRCH-04).

Phase 22 extends Tag with:
  - canonical: str  (required; normalized to Title Case <=3 words — D-05)
  - polarity_type: Literal["always_positive", "always_negative", "mixed"] | None
    (nullable union with NO default — Structured Outputs strict mode, Pitfall 1)
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, field_validator


class Tag(BaseModel):
    label: str
    polarity: Literal["positive", "negative", "neutral"]
    canonical: str
    polarity_type: Literal["always_positive", "always_negative", "mixed"] | None  # NO `= None`

    @field_validator("canonical")
    @classmethod
    def normalize_canonical(cls, v: str) -> str:
        """D-05: Title Case, <=3 words, server-side.

        Mirrors the max_five_tags mutating-validator idiom (EnrichmentResult).
        Never a pattern/constr/Field(...) constraint — the SDK strips/rejects
        schema-level constraints in Structured Outputs strict mode (Pitfall 7).
        """
        words = v.strip().split()
        if not words:
            return v.strip().title()
        return " ".join(word.title() for word in words[:3])


class ActionItem(BaseModel):
    title: str
    scope: Literal["shop", "brand"]
    priority: Literal["high", "medium", "low"]
    category: Literal["quality", "service", "experience", "operations", "other"]


class EnrichmentResult(BaseModel):
    sentiment: Literal["positive", "neutral", "negative"]
    tags: list[Tag]
    action_items: list[ActionItem]

    @field_validator("tags")
    @classmethod
    def max_five_tags(cls, v: list[Tag]) -> list[Tag]:
        # Defensive: prompt enforces <=5, validator guarantees it server-side.
        return v[:5]
