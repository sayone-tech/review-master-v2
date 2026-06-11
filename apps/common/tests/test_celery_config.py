"""INFRA-04: Celery configuration assertions — time limits, ack-late, eager-in-tests."""

from django.conf import settings


def test_time_limits() -> None:
    assert settings.CELERY_TASK_TIME_LIMIT == 600
    assert settings.CELERY_TASK_SOFT_TIME_LIMIT == 300


def test_default_queue() -> None:
    assert settings.CELERY_TASK_DEFAULT_QUEUE == "default"


def test_acks_late_and_prefetch() -> None:
    assert settings.CELERY_TASK_ACKS_LATE is True
    assert settings.CELERY_TASK_REJECT_ON_WORKER_LOST is True
    assert settings.CELERY_WORKER_PREFETCH_MULTIPLIER == 1


def test_eager_in_test_settings() -> None:
    assert settings.CELERY_TASK_ALWAYS_EAGER is True
    assert settings.CELERY_TASK_EAGER_PROPAGATES is True


def test_routes_present() -> None:
    """Phase 23 (D-09): enrich_review_task default route is ai-enrichment-low.
    Seed path overrides to ai-enrichment-high at call site; retry path uses ai-enrichment-low.
    """
    routes = settings.CELERY_TASK_ROUTES
    assert routes["apps.reviews.tasks.sync_shop_reviews_task"]["queue"] == "google-sync"
    assert routes["apps.reviews.tasks.initial_backfill_task"]["queue"] == "google-sync"
    # Conservative fallback queue — actual dispatch queue is set at call site via apply_async.
    assert routes["apps.reviews.tasks.enrich_review_task"]["queue"] == "ai-enrichment-low"
    assert (
        routes["apps.reviews.tasks.retry_failed_enrichments_task"]["queue"] == "ai-enrichment-low"
    )


def test_broker_uses_db_3() -> None:
    assert settings.CELERY_BROKER_URL.endswith("/3")


def test_result_backend_uses_db_4() -> None:
    assert settings.CELERY_RESULT_BACKEND.endswith("/4")
