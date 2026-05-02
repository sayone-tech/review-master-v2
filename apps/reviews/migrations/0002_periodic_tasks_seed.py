"""Seed django-celery-beat PeriodicTask for enqueue_incremental_syncs_task."""
from __future__ import annotations

import json

from django.db import migrations


def seed_periodic_tasks(apps, schema_editor) -> None:  # type: ignore[no-untyped-def]
    IntervalSchedule = apps.get_model("django_celery_beat", "IntervalSchedule")
    CrontabSchedule = apps.get_model("django_celery_beat", "CrontabSchedule")
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")

    crontab, _ = CrontabSchedule.objects.get_or_create(
        minute="0",
        hour="*",
        day_of_week="*",
        day_of_month="*",
        month_of_year="*",
        timezone="UTC",
    )
    PeriodicTask.objects.update_or_create(
        name="enqueue_incremental_syncs",
        defaults={
            "task": "apps.reviews.tasks.enqueue_incremental_syncs_task",
            "crontab": crontab,
            "interval": None,
            "enabled": True,
            "queue": "google-sync",
            "args": json.dumps([]),
            "kwargs": json.dumps({}),
            "description": "Phase 11 SYNC-02: hourly fan-out, jitter applied per-shop.",
        },
    )


def remove_periodic_tasks(apps, schema_editor) -> None:  # type: ignore[no-untyped-def]
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")
    PeriodicTask.objects.filter(name="enqueue_incremental_syncs").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("reviews", "0001_initial"),
        ("django_celery_beat", "0019_alter_periodictasks_options"),
    ]

    operations = [
        migrations.RunPython(seed_periodic_tasks, remove_periodic_tasks),
    ]
