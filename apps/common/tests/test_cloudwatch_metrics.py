"""Tests for apps.common.services.cloudwatch_metrics.

Covers:
- queue depths are read via Redis LLEN for each configured queue
- when CLOUDWATCH_METRICS_ENABLED is False, no boto3 call is made
- when enabled, a single PutMetricData call is made with the right shape
- a CloudWatch API error does not raise (logged + swallowed)
- the seeded PeriodicTask exists after migrations (idempotency check)
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError
from django.test import override_settings

from apps.common.services import cloudwatch_metrics


def _fake_redis(depths: dict[str, int]) -> MagicMock:
    """Return a MagicMock that imitates redis.Redis with deterministic LLEN."""
    client = MagicMock()
    client.llen.side_effect = lambda name: depths[name]
    return client


@override_settings(
    CELERY_QUEUE_NAMES=["google-sync", "ai-enrichment", "default"],
    CLOUDWATCH_METRICS_ENABLED=False,
)
def test_returns_depths_and_skips_publish_when_disabled() -> None:
    fake = _fake_redis({"google-sync": 3, "ai-enrichment": 7, "default": 0})

    with (
        patch("apps.common.services.cloudwatch_metrics.redis.Redis.from_url", return_value=fake),
        patch("apps.common.services.cloudwatch_metrics.boto3.client") as mock_boto,
    ):
        depths = cloudwatch_metrics.publish_celery_queue_depths()

    assert depths == {"google-sync": 3, "ai-enrichment": 7, "default": 0}
    mock_boto.assert_not_called()
    fake.close.assert_called_once()


@override_settings(
    CELERY_QUEUE_NAMES=["google-sync", "ai-enrichment", "default"],
    CLOUDWATCH_METRICS_ENABLED=True,
    AWS_REGION="ap-south-1",
)
def test_publishes_one_put_metric_data_call_per_run() -> None:
    fake = _fake_redis({"google-sync": 12, "ai-enrichment": 0, "default": 1})
    cw = MagicMock()

    with (
        patch("apps.common.services.cloudwatch_metrics.redis.Redis.from_url", return_value=fake),
        patch("apps.common.services.cloudwatch_metrics.boto3.client", return_value=cw) as mock_boto,
    ):
        depths = cloudwatch_metrics.publish_celery_queue_depths()

    assert depths == {"google-sync": 12, "ai-enrichment": 0, "default": 1}
    mock_boto.assert_called_once_with("cloudwatch", region_name="ap-south-1")
    cw.put_metric_data.assert_called_once()

    call_kwargs = cw.put_metric_data.call_args.kwargs
    assert call_kwargs["Namespace"] == "ReviewMaster/Celery"

    metric_data = call_kwargs["MetricData"]
    assert len(metric_data) == 3
    expected = {
        ("google-sync", 12.0),
        ("ai-enrichment", 0.0),
        ("default", 1.0),
    }
    actual = {(point["Dimensions"][0]["Value"], point["Value"]) for point in metric_data}
    assert actual == expected
    for point in metric_data:
        assert point["MetricName"] == "QueueDepth"
        assert point["Unit"] == "Count"
        assert point["Dimensions"][0]["Name"] == "QueueName"


@override_settings(
    CELERY_QUEUE_NAMES=["google-sync"],
    CLOUDWATCH_METRICS_ENABLED=True,
    AWS_REGION="ap-south-1",
)
def test_swallows_cloudwatch_errors() -> None:
    """A transient AWS error must not propagate — Beat must keep ticking."""
    fake = _fake_redis({"google-sync": 5})
    cw = MagicMock()
    cw.put_metric_data.side_effect = ClientError(
        error_response={"Error": {"Code": "Throttling", "Message": "Rate exceeded"}},
        operation_name="PutMetricData",
    )

    with (
        patch("apps.common.services.cloudwatch_metrics.redis.Redis.from_url", return_value=fake),
        patch("apps.common.services.cloudwatch_metrics.boto3.client", return_value=cw),
    ):
        depths = cloudwatch_metrics.publish_celery_queue_depths()

    assert depths == {"google-sync": 5}
    cw.put_metric_data.assert_called_once()


@pytest.mark.django_db
def test_periodic_task_seeded_by_migration() -> None:
    """Migration 0003 must seed the PeriodicTask with the right task path."""
    from django_celery_beat.models import IntervalSchedule, PeriodicTask

    pt = PeriodicTask.objects.get(name="publish_celery_queue_depths")
    assert pt.task == "apps.common.tasks.publish_celery_queue_depths_task"
    assert pt.queue == "default"
    assert pt.enabled is True
    assert pt.interval is not None
    assert pt.interval.every == 60
    assert pt.interval.period == IntervalSchedule.SECONDS
