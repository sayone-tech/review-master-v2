"""Seed the recover_stuck_syncs Beat schedule (every 10 minutes).

Phase 27 SYNC-REL: finalize_canonical_tags_task is dispatched only once (by the
initial backfill) as a single self-rescheduling countdown task. If that chain is
lost — e.g. a worker restart mid-sync — nothing re-triggers finalise and the sync
hangs at "finalising" forever. recover_stuck_syncs_task scans in-progress snapshots
and re-dispatches finalise for stale ones; this seeds it to run every 10 minutes.
"""

from __future__ import annotations

import json

from django.db import migrations


def seed(apps, schema_editor) -> None:  # type: ignore[no-untyped-def]
    IntervalSchedule = apps.get_model("django_celery_beat", "IntervalSchedule")
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")

    interval, _ = IntervalSchedule.objects.get_or_create(every=10, period="minutes")
    PeriodicTask.objects.update_or_create(
        name="recover_stuck_syncs",
        defaults={
            "task": "apps.reviews.tasks.recover_stuck_syncs_task",
            "interval": interval,
            "crontab": None,
            "enabled": True,
            "queue": "default",
            "args": json.dumps([]),
            "kwargs": json.dumps({}),
            "description": (
                "Phase 27 SYNC-REL: re-dispatch finalise for syncs stuck in-progress "
                "(lost finalise chain, e.g. worker restart mid-sync)."
            ),
        },
    )


def unseed(apps, schema_editor) -> None:  # type: ignore[no-untyped-def]
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")
    PeriodicTask.objects.filter(name="recover_stuck_syncs").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("reviews", "0015_beat_incremental_6h"),
        ("django_celery_beat", "0019_alter_periodictasks_options"),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
