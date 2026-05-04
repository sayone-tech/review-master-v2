"""Phase 12 — Tests for apps.reviews.management.commands.enrich_existing_reviews.

Covers ENRCH-13 (one-time backfill of Phase 11 reviews).

Patch path discipline (RESEARCH.md Pitfall 5): we patch the symbol AS BOUND
inside the command module — apps.reviews.management.commands.enrich_existing_reviews
.enrich_review_task.delay — not apps.reviews.tasks.enrich_review_task.delay.
The command module imports enrich_review_task at the top of the file, which
creates a separate reference in its own namespace.
"""

from __future__ import annotations

from io import StringIO
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.utils import timezone as dj_timezone

from apps.reviews.models import Review
from apps.reviews.tests.factories import ReviewFactory

PATCH_TARGET = "apps.reviews.management.commands.enrich_existing_reviews.enrich_review_task.delay"


@pytest.mark.django_db
def test_enrich_existing_enqueues_pending_reviews_only() -> None:
    pending = ReviewFactory.create_batch(3, enrichment_status=Review.EnrichmentStatus.PENDING)
    ReviewFactory(enrichment_status=Review.EnrichmentStatus.SUCCESS)
    ReviewFactory(enrichment_status=Review.EnrichmentStatus.FAILED)
    ReviewFactory(enrichment_status=Review.EnrichmentStatus.IN_PROGRESS)

    with patch(PATCH_TARGET) as mock_delay:
        out = StringIO()
        call_command("enrich_existing_reviews", stdout=out)

    assert mock_delay.call_count == 3
    enqueued_ids = {call.args[0] for call in mock_delay.call_args_list}
    assert enqueued_ids == {r.id for r in pending}
    assert "Enqueued 3 reviews for enrichment." in out.getvalue()


@pytest.mark.django_db
def test_enrich_existing_skips_soft_deleted_pending_reviews() -> None:
    live = ReviewFactory.create_batch(2, enrichment_status=Review.EnrichmentStatus.PENDING)
    ReviewFactory(
        enrichment_status=Review.EnrichmentStatus.PENDING,
        deleted_at=dj_timezone.now(),
    )

    with patch(PATCH_TARGET) as mock_delay:
        out = StringIO()
        call_command("enrich_existing_reviews", stdout=out)

    assert mock_delay.call_count == 2
    enqueued_ids = {call.args[0] for call in mock_delay.call_args_list}
    assert enqueued_ids == {r.id for r in live}
    assert "Enqueued 2 reviews for enrichment." in out.getvalue()


@pytest.mark.django_db
def test_enrich_existing_dry_run_prints_count_without_dispatching() -> None:
    ReviewFactory.create_batch(4, enrichment_status=Review.EnrichmentStatus.PENDING)

    with patch(PATCH_TARGET) as mock_delay:
        out = StringIO()
        call_command("enrich_existing_reviews", "--dry-run", stdout=out)

    assert mock_delay.call_count == 0
    assert "[dry-run] Enqueued 4 reviews for enrichment." in out.getvalue()


@pytest.mark.django_db
def test_enrich_existing_limit_caps_enqueue_count() -> None:
    ReviewFactory.create_batch(5, enrichment_status=Review.EnrichmentStatus.PENDING)

    with patch(PATCH_TARGET) as mock_delay:
        out = StringIO()
        call_command("enrich_existing_reviews", "--limit", "2", stdout=out)

    assert mock_delay.call_count == 2
    assert "Enqueued 2 reviews for enrichment." in out.getvalue()


@pytest.mark.django_db
def test_enrich_existing_empty_queue_prints_zero() -> None:
    ReviewFactory(enrichment_status=Review.EnrichmentStatus.SUCCESS)

    with patch(PATCH_TARGET) as mock_delay:
        out = StringIO()
        call_command("enrich_existing_reviews", stdout=out)

    assert mock_delay.call_count == 0
    assert "Enqueued 0 reviews for enrichment." in out.getvalue()
