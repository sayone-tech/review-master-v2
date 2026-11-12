"""Mark hand-entered prices as ``manual`` (Phase 36 data migration).

0005 was edited after the branch was pushed, so an environment may have applied an earlier
0005 that left admin-entered rows as ``source="seed"``. Re-run the backfill forward: every
``seed`` row except the one created by 0002 becomes ``manual`` so the LiteLLM sync never
overrides it. Idempotent (a second run matches nothing) and safe whether or not the old 0005
ran; the sync cannot have run before 0006/0007 existed, so no ``sync`` row is affected.
Reverse is a no-op (the original ``seed`` labels on those rows were wrong).
"""

from __future__ import annotations

from datetime import UTC, datetime

from django.db import migrations, models

# The row created by 0002_seed_aiprice_gpt4o_mini (values copied, not imported).
SEED_MODEL = "gpt-4o-mini-2024-07-18"
SEED_EFFECTIVE_FROM = datetime(2024, 7, 18, tzinfo=UTC)


def backfill_hand_entered_manual(apps, schema_editor) -> None:  # type: ignore[no-untyped-def]
    AiPricing = apps.get_model("openai", "AiPricing")
    is_0002_seed = models.Q(model=SEED_MODEL, effective_from=SEED_EFFECTIVE_FROM)
    AiPricing.objects.filter(source="seed").exclude(is_0002_seed).update(source="manual")


class Migration(migrations.Migration):
    dependencies = [("openai", "0007_beat_ai_pricing_sync")]

    operations = [
        migrations.RunPython(backfill_hand_entered_manual, migrations.RunPython.noop),
    ]
