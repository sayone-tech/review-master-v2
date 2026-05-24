"""CloudWatch custom-metric publishers.

Currently exposes one function — `publish_celery_queue_depths()` — invoked
every minute by a Celery Beat task (see apps.common.tasks). Reads each
queue's depth via Redis `LLEN`, batches them into one PutMetricData call.

The publisher no-ops when CLOUDWATCH_METRICS_ENABLED is False, which keeps
local dev and CI from attempting AWS calls.

Namespace: ReviewMaster/Celery
Metric:    QueueDepth
Dimension: QueueName ∈ {google-sync, ai-enrichment, default}
"""

from __future__ import annotations

import logging
from typing import Any, cast

import boto3
import redis
from botocore.exceptions import BotoCoreError, ClientError
from django.conf import settings

logger = logging.getLogger(__name__)

NAMESPACE = "ReviewMaster/Celery"
METRIC_NAME = "QueueDepth"


def _read_queue_depths(*, queue_names: list[str]) -> dict[str, int]:
    """Return {queue_name: depth} by issuing one Redis LLEN per queue.

    Celery stores queued tasks as Redis lists keyed by queue name on the
    broker DB (CELERY_BROKER_URL). LLEN is O(1).
    """
    client = redis.Redis.from_url(settings.CELERY_BROKER_URL)
    try:
        # redis-py's LLEN return type is `int | Awaitable[int]` because the
        # stubs cover both sync + async clients. Our sync client always
        # returns int.
        return {name: cast(int, client.llen(name)) for name in queue_names}
    finally:
        client.close()


def _to_metric_data(depths: dict[str, int]) -> list[dict[str, Any]]:
    return [
        {
            "MetricName": METRIC_NAME,
            "Dimensions": [{"Name": "QueueName", "Value": name}],
            "Value": float(depth),
            "Unit": "Count",
        }
        for name, depth in depths.items()
    ]


def publish_celery_queue_depths() -> dict[str, int]:
    """Read Celery queue depths and publish one CloudWatch metric per queue.

    Returns the depths dict regardless of publish outcome, so the caller
    (or tests) can assert on what was observed even when CloudWatch is off.
    Errors talking to CloudWatch are logged and swallowed — a transient
    AWS hiccup must not crash the Beat scheduler.
    """
    depths = _read_queue_depths(queue_names=settings.CELERY_QUEUE_NAMES)

    if not getattr(settings, "CLOUDWATCH_METRICS_ENABLED", False):
        logger.debug("cloudwatch_metrics.skipped reason=disabled depths=%s", depths)
        return depths

    client = boto3.client("cloudwatch", region_name=settings.AWS_REGION)
    try:
        client.put_metric_data(Namespace=NAMESPACE, MetricData=_to_metric_data(depths))
        logger.info("cloudwatch_metrics.published depths=%s", depths)
    except (BotoCoreError, ClientError) as exc:
        logger.warning("cloudwatch_metrics.publish_failed error=%s depths=%s", exc, depths)

    return depths
