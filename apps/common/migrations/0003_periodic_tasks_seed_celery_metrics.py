"""Seed django-celery-beat PeriodicTask for publish_celery_queue_depths_task.

Mirrors the pattern from apps/reviews/migrations/0005 — uses IntervalSchedule
+ update_or_create so the migration is idempotent across re-runs.

Runs every 60 seconds on the `default` queue. The task publishes one
CloudWatch metric per Celery queue (google-sync, ai-enrichment, default)
under namespace `ReviewMaster/Celery`, metric `QueueDepth`.

The publisher itself no-ops when CLOUDWATCH_METRICS_ENABLED is False
(default in dev/test), so this schedule is safe to seed in all environments.
"""

from __future__ import annotations

import json

from django.db import migrations


def seed_publish_celery_queue_depths(apps, schema_editor) -> None:  # type: ignore[no-untyped-def]
    IntervalSchedule = apps.get_model("django_celery_beat", "IntervalSchedule")
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")

    interval, _ = IntervalSchedule.objects.get_or_create(
        every=60,
        period="seconds",
    )
    PeriodicTask.objects.update_or_create(
        name="publish_celery_queue_depths",
        defaults={
            "task": "apps.common.tasks.publish_celery_queue_depths_task",
            "interval": interval,
            "crontab": None,
            "enabled": True,
            "queue": "default",
            "args": json.dumps([]),
            "kwargs": json.dumps({}),
            "description": (
                "Tier-0 observability: every 60s publish each Celery queue's "
                "depth (LLEN) to CloudWatch namespace ReviewMaster/Celery."
            ),
        },
    )


def remove_publish_celery_queue_depths(apps, schema_editor) -> None:  # type: ignore[no-untyped-def]
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")
    PeriodicTask.objects.filter(name="publish_celery_queue_depths").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("common", "0002_auditlog"),
        ("django_celery_beat", "0019_alter_periodictasks_options"),
    ]

    operations = [
        migrations.RunPython(
            seed_publish_celery_queue_depths,
            reverse_code=remove_publish_celery_queue_depths,
        ),
    ]
