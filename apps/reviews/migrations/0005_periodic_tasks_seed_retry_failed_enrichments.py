"""Phase 12 ENRCH-06 — Seed django-celery-beat PeriodicTask for retry_failed_enrichments_task.

Mirrors the pattern from apps/reviews/migrations/0002_periodic_tasks_seed.py
which seeds the hourly enqueue_incremental_syncs task. This Beat entry runs
retry_failed_enrichments_task every 6 hours on the ai-enrichment queue,
re-attempting FAILED reviews with enrichment_version < 3.
"""

from __future__ import annotations

import json

from django.db import migrations


def seed_retry_failed_enrichments(apps, schema_editor) -> None:  # type: ignore[no-untyped-def]
    IntervalSchedule = apps.get_model("django_celery_beat", "IntervalSchedule")
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")

    interval, _ = IntervalSchedule.objects.get_or_create(
        every=6,
        period="hours",
    )
    PeriodicTask.objects.update_or_create(
        name="retry_failed_enrichments",
        defaults={
            "task": "apps.reviews.tasks.retry_failed_enrichments_task",
            "interval": interval,
            "crontab": None,
            "enabled": True,
            "queue": "ai-enrichment",
            "args": json.dumps([]),
            "kwargs": json.dumps({}),
            "description": (
                "Phase 12 ENRCH-06: every 6h re-attempt FAILED enrichments "
                "where enrichment_version < 3."
            ),
        },
    )


def remove_retry_failed_enrichments(apps, schema_editor) -> None:  # type: ignore[no-untyped-def]
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")
    PeriodicTask.objects.filter(name="retry_failed_enrichments").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("reviews", "0004_review_extracted_action_items"),
        ("django_celery_beat", "0019_alter_periodictasks_options"),
    ]

    operations = [
        migrations.RunPython(seed_retry_failed_enrichments, remove_retry_failed_enrichments),
    ]
