"""Phase 19 — Reply generation prompt template tests.

Covers D-04 through D-08:
  D-05 — Professional system prompt wording
  D-06 — Friendly system prompt wording
  D-08 — REPLY_GENERATION_PROMPT_VERSION = 1
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from apps.integrations.openai.prompts import (
    REPLY_GENERATION_PROMPT_VERSION,
    build_reply_generation_messages,
)


def _make_review(*, shop_name: str = "TestShop", star_rating: int = 4, comment: str = "Great!"):
    review = MagicMock()
    review.shop.name = shop_name
    review.star_rating = star_rating
    review.comment = comment
    return review


def test_prompt_version_constant_is_one() -> None:
    assert REPLY_GENERATION_PROMPT_VERSION == 1


def test_build_professional_messages_contains_locked_wording() -> None:
    review = _make_review()
    msgs = build_reply_generation_messages(review=review, tone="professional", brand_name="Acme")

    assert isinstance(msgs, list)
    assert len(msgs) == 2
    assert msgs[0]["role"] == "system"
    sys_content = msgs[0]["content"]
    # D-05 exact phrases
    assert "professional customer experience representative" in sys_content
    assert "formal, concise" in sys_content
    assert "No emojis" in sys_content
    assert "Under 150 words" in sys_content
    # Brand name interpolation
    assert "Acme" in sys_content
    assert "{brand_name}" not in sys_content


def test_build_friendly_messages_contains_locked_wording() -> None:
    review = _make_review()
    msgs = build_reply_generation_messages(review=review, tone="friendly", brand_name="Acme")

    assert msgs[0]["role"] == "system"
    sys_content = msgs[0]["content"]
    # D-06 exact phrases
    assert "warm, friendly team member" in sys_content
    assert "conversational, personable" in sys_content
    assert "One emoji maximum" in sys_content
    assert "Under 150 words" in sys_content
    assert "Acme" in sys_content


def test_user_payload_contains_brand_shop_rating_and_comment() -> None:
    review = _make_review(shop_name="MainStreet", star_rating=3, comment="Mediocre")
    msgs = build_reply_generation_messages(review=review, tone="professional", brand_name="Acme")

    assert msgs[1]["role"] == "user"
    user_content = msgs[1]["content"]
    assert "Brand: Acme" in user_content
    assert "MainStreet" in user_content
    assert "3" in user_content
    assert "Mediocre" in user_content


def test_unknown_tone_raises_value_error() -> None:
    review = _make_review()
    with pytest.raises(ValueError, match="Unknown tone"):
        build_reply_generation_messages(review=review, tone="formal", brand_name="Acme")


def test_review_without_comment_uses_placeholder() -> None:
    review = _make_review(comment="")
    msgs = build_reply_generation_messages(review=review, tone="professional", brand_name="Acme")
    assert "(no comment provided)" in msgs[1]["content"]
