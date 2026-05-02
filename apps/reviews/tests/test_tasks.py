"""Phase 11 — Celery task wrapper tests."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from apps.reviews import tasks
from apps.shops.models import Shop
from apps.shops.tests.factories import ShopFactory

pytestmark = pytest.mark.django_db


def test_initial_backfill_task_delegates_to_service() -> None:
    with patch.object(tasks, "run_initial_backfill", return_value={"fetched": 0}) as svc:
        result = tasks.initial_backfill_task(shop_id=42)
    svc.assert_called_once_with(shop_id=42)
    assert result == {"fetched": 0}


def test_sync_shop_reviews_task_delegates_to_service() -> None:
    with patch.object(tasks, "run_incremental_sync", return_value={"fetched": 5}) as svc:
        result = tasks.sync_shop_reviews_task(shop_id=42)
    svc.assert_called_once_with(shop_id=42)
    assert result == {"fetched": 5}


def test_enqueue_incremental_syncs_dispatches_per_connected_shop() -> None:
    s1 = ShopFactory(connection_status=Shop.ConnectionStatus.CONNECTED, is_active=True)
    s2 = ShopFactory(connection_status=Shop.ConnectionStatus.CONNECTED, is_active=True)
    ShopFactory(connection_status=Shop.ConnectionStatus.NOT_CONNECTED, is_active=True)
    ShopFactory(connection_status=Shop.ConnectionStatus.CONNECTED, is_active=False)
    ShopFactory(connection_status=Shop.ConnectionStatus.EXPIRED, is_active=True)

    with patch.object(tasks.sync_shop_reviews_task, "apply_async") as apply_async:
        count = tasks.enqueue_incremental_syncs_task()

    assert count == 2
    dispatched_args = sorted(c.kwargs["args"][0] for c in apply_async.call_args_list)
    assert dispatched_args == sorted([s1.pk, s2.pk])


def test_enqueue_incremental_syncs_countdown_within_jitter_window() -> None:
    ShopFactory(connection_status=Shop.ConnectionStatus.CONNECTED, is_active=True)
    with patch.object(tasks.sync_shop_reviews_task, "apply_async") as apply_async:
        tasks.enqueue_incremental_syncs_task()
    countdown = apply_async.call_args.kwargs["countdown"]
    assert 0.0 <= countdown <= tasks.INCREMENTAL_JITTER_SECONDS_MAX


def test_periodic_task_seeded() -> None:
    from django_celery_beat.models import PeriodicTask

    pt = PeriodicTask.objects.filter(name="enqueue_incremental_syncs").first()
    assert pt is not None
    assert pt.task == "apps.reviews.tasks.enqueue_incremental_syncs_task"
    assert pt.queue == "google-sync"
    assert pt.enabled is True


def test_initial_backfill_dispatched_to_google_sync_queue() -> None:
    """Verify Celery routing matches the requirement (SYNC-01: dispatched after OAuth)."""
    from celery import current_app

    routes = current_app.conf.task_routes
    assert routes["apps.reviews.tasks.initial_backfill_task"]["queue"] == "google-sync"
    assert routes["apps.reviews.tasks.sync_shop_reviews_task"]["queue"] == "google-sync"
