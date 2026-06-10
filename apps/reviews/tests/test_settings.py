"""Phase 23 — Tests for queue split settings and new knobs (QUEUE-01, D-04, D-08, D-09)."""

from __future__ import annotations

from django.conf import settings


def test_celery_queue_names_exact() -> None:
    """CELERY_QUEUE_NAMES lists exactly the five Phase 23 queues (D-09)."""
    assert settings.CELERY_QUEUE_NAMES == [
        "google-sync",
        "ai-enrichment-high",
        "ai-enrichment-low",
        "tag-merge",
        "default",
    ]


def test_no_bare_ai_enrichment_queue() -> None:
    """The old bare 'ai-enrichment' queue name must not appear anywhere."""
    assert "ai-enrichment" not in settings.CELERY_QUEUE_NAMES


def test_enrich_review_task_routes_to_ai_enrichment_low() -> None:
    """enrich_review_task uses ai-enrichment-low as conservative fallback (D-09)."""
    route = settings.CELERY_TASK_ROUTES["apps.reviews.tasks.enrich_review_task"]
    assert route["queue"] == "ai-enrichment-low"


def test_retry_failed_enrichments_task_routes_to_ai_enrichment_low() -> None:
    """retry_failed_enrichments_task uses ai-enrichment-low fallback (D-09)."""
    route = settings.CELERY_TASK_ROUTES["apps.reviews.tasks.retry_failed_enrichments_task"]
    assert route["queue"] == "ai-enrichment-low"


def test_finalize_canonical_tags_task_routes_to_tag_merge() -> None:
    """finalize_canonical_tags_task is routed to tag-merge queue (D-09)."""
    route = settings.CELERY_TASK_ROUTES["apps.reviews.tasks.finalize_canonical_tags_task"]
    assert route["queue"] == "tag-merge"


def test_seed_phase_size_default() -> None:
    """SEED_PHASE_SIZE defaults to 50 (D-04)."""
    assert settings.SEED_PHASE_SIZE == 50


def test_openai_global_rate_limit_default() -> None:
    """OPENAI_GLOBAL_RATE_LIMIT defaults to 500 (D-08)."""
    assert settings.OPENAI_GLOBAL_RATE_LIMIT == 500


def test_enrichment_rate_limit_unchanged() -> None:
    """ENRICHMENT_RATE_LIMIT secondary per-worker guard is still present."""
    assert settings.ENRICHMENT_RATE_LIMIT == "125/m"
