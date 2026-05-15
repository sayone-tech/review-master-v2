"""Phase 12 — Pydantic schemas for the structured GPT response.

The OpenAI client wrapper passes EnrichmentResult to client.responses.parse()
as text_format. Pydantic validation on response.output_parsed is the structured
output contract — if validation fails, raise EnrichmentParseError (retry once
per ENRCH-04).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, field_validator


class Tag(BaseModel):
    label: str
    polarity: Literal["positive", "negative", "neutral"]


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
