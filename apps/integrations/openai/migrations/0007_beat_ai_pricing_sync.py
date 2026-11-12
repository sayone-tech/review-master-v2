"""Seed django-celery-beat PeriodicTask for the weekly LiteLLM AI pricing sync.

Phase 36 (CLAUDE.md section 12.5): seeds a CrontabSchedule (Monday 09:00 UTC) and a
PeriodicTask named "ai_pricing_sync_from_litellm" on the default queue. Reversible: the
reverse step deletes the PeriodicTask by name (the shared crontab row is left alone).
"""

from __future__ import annotations

import json

from django.db import migrations

TASK_NAME = "ai_pricing_sync_from_litellm"


def seed_ai_pricing_sync(apps, schema_editor) -> None:  # type: ignore[no-untyped-def]
    CrontabSchedule = apps.get_model("django_celery_beat", "CrontabSchedule")
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")

    crontab, _ = CrontabSchedule.objects.get_or_create(
        minute="0",
        hour="9",
        day_of_week="1",
        day_of_month="*",
        month_of_year="*",
        timezone="UTC",
    )
    PeriodicTask.objects.update_or_create(
        name=TASK_NAME,
        defaults={
            "task": "apps.integrations.openai.tasks.sync_ai_pricing_from_litellm_task",
            "crontab": crontab,
            "interval": None,
            "enabled": True,
            "queue": "default",
            "args": json.dumps([]),
            "kwargs": json.dumps({}),
            "description": (
                "Phase 36: weekly Monday 09:00 UTC LiteLLM price sync. A no-op while the "
                "superadmin sync switch (AiPricingSyncConfig.enabled) is off."
            ),
        },
    )


def unseed_ai_pricing_sync(apps, schema_editor) -> None:  # type: ignore[no-untyped-def]
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")
    PeriodicTask.objects.filter(name=TASK_NAME).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("openai", "0006_ai_pricing_sync_config"),
        ("django_celery_beat", "0019_alter_periodictasks_options"),
    ]

    operations = [
        migrations.RunPython(seed_ai_pricing_sync, unseed_ai_pricing_sync),
    ]
