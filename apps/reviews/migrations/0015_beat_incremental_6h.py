"""Update enqueue_incremental_syncs Beat schedule to 6-hourly and re-enable it.

Phase 26 SEED-06/D-06: resolves the hourly-vs-6h doc/impl drift (the beat was
set to `0 * * * *` (hourly) in migration 0002, while INCREMENTAL_SYNC_INTERVAL_HOURS=6
and CLAUDE.md §12.5 document every-6h cadence). Re-enables the task after it was
disabled as a UAT mitigation for the SEED-06 clobber bug; the trigger gate in
fetch_and_persist_reviews (Phase 26 Plan 01) makes re-enabling safe.

Note: CLAUDE.md §12.5 beat-schedule table shows enqueue_incremental_syncs as
"Every hour at minute 0" — this migration aligns the beat to the 6-h cadence that
§12.1 (INCREMENTAL_SYNC_INTERVAL_HOURS=6) already documents as the intent.
The discrepancy between §12.5 (hourly) and §12.1 (6h) is a doc drift resolved by D-06.
"""

from __future__ import annotations

import json

from django.db import migrations


def set_6hourly_and_enable(apps, schema_editor) -> None:  # type: ignore[no-untyped-def]
    """Forward: set enqueue_incremental_syncs to 0 */6 * * * UTC, enabled=True."""
    CrontabSchedule = apps.get_model("django_celery_beat", "CrontabSchedule")
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")

    crontab, _ = CrontabSchedule.objects.get_or_create(
        minute="0",
        hour="*/6",
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
            "description": (
                "Phase 26 SEED-06/D-06: 6-hourly fan-out (was hourly). "
                "Re-enabled after SEED-06 trigger gate fix. "
                "Aligns with INCREMENTAL_SYNC_INTERVAL_HOURS=6 setting."
            ),
        },
    )


def revert_to_hourly_disabled(apps, schema_editor) -> None:  # type: ignore[no-untyped-def]
    """Reverse: restore hourly crontab and disable the task (pre-Phase-26 state)."""
    CrontabSchedule = apps.get_model("django_celery_beat", "CrontabSchedule")
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")

    # Re-create (or retrieve) the hourly schedule from migration 0002
    crontab, _ = CrontabSchedule.objects.get_or_create(
        minute="0",
        hour="*",
        day_of_week="*",
        day_of_month="*",
        month_of_year="*",
        timezone="UTC",
    )
    PeriodicTask.objects.filter(name="enqueue_incremental_syncs").update(
        crontab=crontab,
        enabled=False,
    )


class Migration(migrations.Migration):
    dependencies = [
        ("reviews", "0014_tagmergejob"),
        ("django_celery_beat", "0019_alter_periodictasks_options"),
    ]

    operations = [
        migrations.RunPython(set_6hourly_and_enable, revert_to_hourly_disabled),
    ]
