"""INFRA-01 + INFRA-07: Smoke test verifies tasks complete on both named queues."""

import pytest

from apps.common.tasks import smoke_test_task


@pytest.mark.django_db
def test_smoke_task_google_sync_queue() -> None:
    result = smoke_test_task.apply_async(args=["ping"], queue="google-sync")
    assert result.get(timeout=30) == "ping"


@pytest.mark.django_db
def test_smoke_task_ai_enrichment_queue() -> None:
    result = smoke_test_task.apply_async(args=["ping"], queue="ai-enrichment")
    assert result.get(timeout=30) == "ping"


@pytest.mark.django_db
def test_smoke_task_default_queue_synchronous_call() -> None:
    # Direct invocation also returns the value (proves the task is registered).
    assert smoke_test_task("hello") == "hello"
