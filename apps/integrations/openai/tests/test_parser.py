"""Phase 12/22 — Pydantic schema validation tests for EnrichmentResult.

Phase 22 adds canonical + polarity_type to Tag (CTAG-04, D-01, D-05).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from apps.integrations.openai.parser import (
    ActionItem,
    EnrichmentResult,
    Tag,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures"


def test_parses_known_good_fixture() -> None:
    payload = json.loads((FIXTURE_DIR / "enrichment_success.json").read_text())
    result = EnrichmentResult.model_validate(payload)
    assert result.sentiment == "positive"
    assert len(result.tags) == 3
    assert all(isinstance(t, Tag) for t in result.tags)
    assert len(result.action_items) == 2
    assert all(isinstance(a, ActionItem) for a in result.action_items)


def _make_tag(
    *,
    label: str = "great coffee",
    polarity: str = "positive",
    canonical: str = "Food Quality",
    polarity_type: str | None = "always_positive",
) -> dict[str, object]:
    return {
        "label": label,
        "polarity": polarity,
        "canonical": canonical,
        "polarity_type": polarity_type,
    }


def test_truncates_tags_over_five() -> None:
    payload = {
        "sentiment": "negative",
        "tags": [
            _make_tag(label=f"tag-{i}", polarity="neutral", canonical=f"Tag {i}") for i in range(8)
        ],
        "action_items": [],
    }
    result = EnrichmentResult.model_validate(payload)
    assert len(result.tags) == 5


def test_rejects_invalid_sentiment() -> None:
    payload = {"sentiment": "ecstatic", "tags": [], "action_items": []}
    with pytest.raises(ValidationError):
        EnrichmentResult.model_validate(payload)


def test_rejects_invalid_scope() -> None:
    payload = {
        "sentiment": "neutral",
        "tags": [],
        "action_items": [{"title": "x", "scope": "regional", "priority": "high"}],
    }
    with pytest.raises(ValidationError):
        EnrichmentResult.model_validate(payload)


def test_rejects_invalid_priority() -> None:
    payload = {
        "sentiment": "neutral",
        "tags": [],
        "action_items": [{"title": "x", "scope": "shop", "priority": "urgent"}],
    }
    with pytest.raises(ValidationError):
        EnrichmentResult.model_validate(payload)


# ---------------------------------------------------------------------------
# Phase 22 — canonical + polarity_type parse cases (CTAG-04, D-01, D-05)
# ---------------------------------------------------------------------------


def test_canonical_normalized_to_title_case() -> None:
    """D-05: canonical field is normalized to Title Case server-side."""
    tag = Tag.model_validate(_make_tag(canonical="food quality", polarity_type="always_positive"))
    assert tag.canonical == "Food Quality"


def test_canonical_truncated_to_three_words() -> None:
    """D-05: canonical with >3 words is truncated to at most 3 words after normalization."""
    tag = Tag.model_validate(
        _make_tag(canonical="very good food quality here", polarity_type="always_positive")
    )
    words = tag.canonical.split()
    assert len(words) <= 3
    assert tag.canonical == "Very Good Food"


def test_canonical_single_word_normalized() -> None:
    """D-05: single-word canonical is normalized to Title Case."""
    tag = Tag.model_validate(_make_tag(canonical="service", polarity_type="always_positive"))
    assert tag.canonical == "Service"


def test_polarity_type_none_parses_successfully() -> None:
    """CTAG-04: polarity_type=null is valid for existing-tag mapping case."""
    tag = Tag.model_validate(_make_tag(canonical="Food Quality", polarity_type=None))
    assert tag.polarity_type is None


def test_polarity_type_always_positive_parses() -> None:
    """CTAG-04: polarity_type always_positive literal accepted."""
    tag = Tag.model_validate(_make_tag(polarity_type="always_positive"))
    assert tag.polarity_type == "always_positive"


def test_polarity_type_always_negative_parses() -> None:
    """CTAG-04: polarity_type always_negative literal accepted."""
    tag = Tag.model_validate(_make_tag(polarity_type="always_negative"))
    assert tag.polarity_type == "always_negative"


def test_polarity_type_mixed_parses() -> None:
    """CTAG-04: polarity_type mixed literal accepted."""
    tag = Tag.model_validate(_make_tag(polarity_type="mixed"))
    assert tag.polarity_type == "mixed"


def test_polarity_type_invalid_value_rejected() -> None:
    """polarity_type must be one of the three allowed literals or null."""
    with pytest.raises(ValidationError):
        Tag.model_validate(_make_tag(polarity_type="positive"))


def test_enrichment_result_with_mixed_polarity_types() -> None:
    """CTAG-04: EnrichmentResult with one polarity_type set and one null parses without error."""
    payload = {
        "sentiment": "positive",
        "tags": [
            _make_tag(
                label="fast service",
                canonical="Service Speed",
                polarity_type="always_positive",
            ),
            _make_tag(
                label="limited menu",
                canonical="Menu Options",
                polarity_type=None,
            ),
        ],
        "action_items": [],
    }
    result = EnrichmentResult.model_validate(payload)
    assert len(result.tags) == 2
    assert result.tags[0].polarity_type == "always_positive"
    assert result.tags[1].polarity_type is None
