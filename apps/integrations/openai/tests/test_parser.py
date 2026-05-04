"""Phase 12 — Pydantic schema validation tests for EnrichmentResult."""

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


def test_truncates_tags_over_five() -> None:
    payload = {
        "sentiment": "negative",
        "tags": [{"label": f"tag-{i}", "polarity": "neutral"} for i in range(8)],
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
