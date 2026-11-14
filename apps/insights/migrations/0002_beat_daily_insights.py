"""Seed the django-celery-beat PeriodicTask for the daily insights computation (02:00 UTC).

Reversible: the reverse step deletes the PeriodicTask by name (the shared crontab is kept).
"""

from __future__ import annotations

import json

from django.db import migrations

TASK_NAME = "insights_compute_daily"


def seed(apps, schema_editor) -> None:  # type: ignore[no-untyped-def]
    CrontabSchedule = apps.get_model("django_celery_beat", "CrontabSchedule")
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")
    crontab, _ = CrontabSchedule.objects.get_or_create(
        minute="0",
        hour="2",
        day_of_week="*",
        day_of_month="*",
        month_of_year="*",
        timezone="UTC",
    )
    PeriodicTask.objects.update_or_create(
        name=TASK_NAME,
        defaults={
            "task": "apps.insights.tasks.compute_daily_insights_task",
            "crontab": crontab,
            "interval": None,
            "enabled": True,
            "queue": "default",
            "args": json.dumps([]),
            "kwargs": json.dumps({}),
            "description": "Insights Book: daily 02:00 UTC snapshot per organisation.",
        },
    )


def unseed(apps, schema_editor) -> None:  # type: ignore[no-untyped-def]
    apps.get_model("django_celery_beat", "PeriodicTask").objects.filter(name=TASK_NAME).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("insights", "0001_initial"),
        ("django_celery_beat", "0019_alter_periodictasks_options"),
    ]

    operations = [migrations.RunPython(seed, unseed)]
