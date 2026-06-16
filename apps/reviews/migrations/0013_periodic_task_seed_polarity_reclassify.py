"""Seed django-celery-beat PeriodicTask for weekly polarity reclassification.

POL-02 (D-05, CLAUDE.md §12.5): Seeds a CrontabSchedule (Sunday 03:00 UTC)
and a PeriodicTask named "reclassify_polarity_tags" on the default queue.
Reversible — remove_polarity_reclassify deletes the PeriodicTask by name.
"""

from __future__ import annotations

import json

from django.db import migrations


def seed_polarity_reclassify(apps, schema_editor) -> None:  # type: ignore[no-untyped-def]
    CrontabSchedule = apps.get_model("django_celery_beat", "CrontabSchedule")
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")

    # day_of_week="0" is Sunday in django-celery-beat (Pitfall 8).
    # Sunday 03:00 UTC per D-05 cadence.
    crontab, _ = CrontabSchedule.objects.get_or_create(
        minute="0",
        hour="3",
        day_of_week="0",
        day_of_month="*",
        month_of_year="*",
        timezone="UTC",
    )
    PeriodicTask.objects.update_or_create(
        name="reclassify_polarity_tags",
        defaults={
            "task": "apps.reviews.tasks.reclassify_polarity_task",
            "crontab": crontab,
            "interval": None,
            "enabled": True,
            "queue": "default",
            "args": json.dumps([]),
            "kwargs": json.dumps({}),
            "description": (
                "Phase 24 POL-02: weekly polarity auto-reclassification. "
                "Flips always_positive/always_negative OrgCanonicalTag rows to mixed "
                "when opposite-polarity ratio > threshold over trailing window. "
                "Sunday 03:00 UTC, default queue, no GPT, idempotent."
            ),
        },
    )


def remove_polarity_reclassify(apps, schema_editor) -> None:  # type: ignore[no-untyped-def]
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")
    PeriodicTask.objects.filter(name="reclassify_polarity_tags").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("reviews", "0012_orgcanonicaltag_polarity_reclassified_at"),
        ("django_celery_beat", "0019_alter_periodictasks_options"),
    ]

    operations = [
        migrations.RunPython(seed_polarity_reclassify, remove_polarity_reclassify),
    ]
