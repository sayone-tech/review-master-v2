from __future__ import annotations

import importlib
import json
from unittest.mock import patch

import pytest
from django.apps import apps as django_apps
from django.conf import settings
from django_celery_beat.models import PeriodicTask

from apps.integrations.openai.services.pricing_sync import SyncOutcome, SyncSummary
from apps.integrations.openai.tasks import sync_ai_pricing_from_litellm_task

TASK_PATH = "apps.integrations.openai.tasks.sync_ai_pricing_from_litellm_task"
TASK_NAME = "ai_pricing_sync_from_litellm"
migration = importlib.import_module("apps.integrations.openai.migrations.0007_beat_ai_pricing_sync")


@pytest.mark.django_db
def test_task_skips_when_sync_disabled() -> None:
    result = sync_ai_pricing_from_litellm_task.delay().get()
    assert result["outcome"] == "skipped_disabled"


def test_task_passes_force_to_service() -> None:
    with patch(
        "apps.integrations.openai.services.pricing_sync.run_pricing_sync",
        return_value=SyncSummary(outcome=SyncOutcome.COMPLETED),
    ) as run:
        result = sync_ai_pricing_from_litellm_task(force=True)
    run.assert_called_once_with(force=True)
    assert result["outcome"] == "completed"


def test_task_is_routed_to_default_queue_and_registered() -> None:
    from config.celery import app

    assert settings.CELERY_TASK_ROUTES[TASK_PATH] == {"queue": "default"}
    assert TASK_PATH in app.tasks


@pytest.mark.django_db
def test_beat_seed_creates_one_weekly_task_and_is_idempotent() -> None:
    PeriodicTask.objects.filter(name=TASK_NAME).delete()
    migration.seed_ai_pricing_sync(django_apps, None)
    migration.seed_ai_pricing_sync(django_apps, None)

    task = PeriodicTask.objects.get(name=TASK_NAME)
    assert task.task == TASK_PATH
    assert task.queue == "default"
    assert task.enabled is True
    assert json.loads(task.kwargs) == {}
    cron = task.crontab
    assert (cron.minute, cron.hour, cron.day_of_week) == ("0", "9", "1")
    assert (cron.day_of_month, cron.month_of_year) == ("*", "*")
    assert str(cron.timezone) == "UTC"


@pytest.mark.django_db
def test_beat_seed_reverse_removes_task() -> None:
    migration.seed_ai_pricing_sync(django_apps, None)
    migration.unseed_ai_pricing_sync(django_apps, None)
    assert not PeriodicTask.objects.filter(name=TASK_NAME).exists()
