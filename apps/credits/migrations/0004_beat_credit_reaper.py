"""Seed django-celery-beat PeriodicTask for the credit reservation reaper.

CREN-03 (D-10, CLAUDE.md section 12.5): seeds a PeriodicTask named
"credits_reap_stale_reservations" that runs every 10 minutes on the default queue. The
IntervalSchedule row (every 10 minutes) is shared with recover_stuck_syncs, so the reverse step
deletes only the PeriodicTask by name and never the interval (deleting it would cascade to the
other task).
"""

from __future__ import annotations

import json

from django.db import migrations


def seed_credit_reaper(apps, schema_editor) -> None:  # type: ignore[no-untyped-def]
    IntervalSchedule = apps.get_model("django_celery_beat", "IntervalSchedule")
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")

    interval, _ = IntervalSchedule.objects.get_or_create(every=10, period="minutes")
    PeriodicTask.objects.update_or_create(
        name="credits_reap_stale_reservations",
        defaults={
            "task": "apps.credits.tasks.reap_stale_reservations_task",
            "interval": interval,
            "crontab": None,
            "enabled": True,
            "queue": "default",
            "args": json.dumps([]),
            "kwargs": json.dumps({}),
            "description": (
                "v0.9 Phase 31 CREN-03: refunds RESERVED credit reservations older than "
                "REVIEWBEE_CREDIT_RESERVATION_TTL_MINUTES, then lapses touched past-month "
                "balances."
            ),
        },
    )


def unseed_credit_reaper(apps, schema_editor) -> None:  # type: ignore[no-untyped-def]
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")
    PeriodicTask.objects.filter(name="credits_reap_stale_reservations").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("credits", "0003_beat_credit_lapse"),
        ("django_celery_beat", "0019_alter_periodictasks_options"),
    ]

    operations = [
        migrations.RunPython(seed_credit_reaper, unseed_credit_reaper),
    ]
