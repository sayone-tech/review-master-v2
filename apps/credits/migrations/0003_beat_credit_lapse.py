"""Seed django-celery-beat PeriodicTask for the daily credit lapse sweep.

CREN-01 (D-04, CLAUDE.md section 12.5): seeds a CrontabSchedule (00:05 UTC every day) and a
PeriodicTask named "credits_lapse_expired_balances" on the default queue. Reversible:
the reverse step deletes the PeriodicTask by name (the shared crontab row is left alone).
"""

from __future__ import annotations

import json

from django.db import migrations


def seed_credit_lapse(apps, schema_editor) -> None:  # type: ignore[no-untyped-def]
    CrontabSchedule = apps.get_model("django_celery_beat", "CrontabSchedule")
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")

    crontab, _ = CrontabSchedule.objects.get_or_create(
        minute="5",
        hour="0",
        day_of_week="*",
        day_of_month="*",
        month_of_year="*",
        timezone="UTC",
    )
    PeriodicTask.objects.update_or_create(
        name="credits_lapse_expired_balances",
        defaults={
            "task": "apps.credits.tasks.lapse_expired_credit_balances_task",
            "crontab": crontab,
            "interval": None,
            "enabled": True,
            "queue": "default",
            "args": json.dumps([]),
            "kwargs": json.dumps({}),
            "description": (
                "v0.9 Phase 31 CREN-01: daily 00:05 UTC idempotent catch-up lapse of unused "
                "credits for past-month balances (the spec's 1st-of-month run is the same job)."
            ),
        },
    )


def unseed_credit_lapse(apps, schema_editor) -> None:  # type: ignore[no-untyped-def]
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")
    PeriodicTask.objects.filter(name="credits_lapse_expired_balances").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("credits", "0002_shopcreditbalance_lapsed_at"),
        ("django_celery_beat", "0019_alter_periodictasks_options"),
    ]

    operations = [
        migrations.RunPython(seed_credit_lapse, unseed_credit_lapse),
    ]
