"""Seed gpt-4o-mini-2024-07-18 pricing row.

Per RESEARCH.md verified 2026-05-02:
  - Input: $0.150 per 1M tokens
  - Output: $0.600 per 1M tokens
  - Cached: $0.075 per 1M tokens

Stored as Decimal to avoid floating-point drift. effective_from is the model
release date (2024-07-18); effective_to is NULL until a price change.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from django.db import migrations

GPT4O_MINI_MODEL = "gpt-4o-mini-2024-07-18"
EFFECTIVE_FROM = datetime(2024, 7, 18, tzinfo=timezone.utc)


def seed_pricing(apps, schema_editor) -> None:  # type: ignore[no-untyped-def]
    AiPricing = apps.get_model("openai", "AiPricing")
    AiPricing.objects.create(
        model=GPT4O_MINI_MODEL,
        input_token_price_per_1m=Decimal("0.150000"),
        output_token_price_per_1m=Decimal("0.600000"),
        cached_token_price_per_1m=Decimal("0.075000"),
        effective_from=EFFECTIVE_FROM,
        effective_to=None,
    )


def unseed_pricing(apps, schema_editor) -> None:  # type: ignore[no-untyped-def]
    AiPricing = apps.get_model("openai", "AiPricing")
    AiPricing.objects.filter(
        model=GPT4O_MINI_MODEL,
        effective_from=EFFECTIVE_FROM,
    ).delete()


class Migration(migrations.Migration):
    dependencies = [("openai", "0001_initial")]
    operations = [migrations.RunPython(seed_pricing, unseed_pricing)]
