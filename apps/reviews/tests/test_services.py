"""Phase 25 — Service tests for canonical tag rename and merge.

Wave 0 RED tests: all tests in this file import from
apps.reviews.services.tag_management which is implemented in Task 3.
Running these tests before Task 3 should produce a failure (ImportError
or assertion failure) — that is the expected RED state per TDD.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from django.core.exceptions import ValidationError
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.reviews.models import OrgCanonicalTag, ReviewTag, TagMergeJob
from apps.reviews.tests.factories import (
    OrgCanonicalTagFactory,
    ReviewFactory,
    ReviewTagFactory,
    TagMergeJobFactory,
)

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Rename service tests (TMGT-03, D-03, D-04)
# ---------------------------------------------------------------------------


def test_rename_updates_canonical_tag_label(db) -> None:
    """Rename updates OrgCanonicalTag.label only (O(1)/FK-only).

    ReviewTag.label rows (the raw per-review tags) must NOT be touched — only
    OrgCanonicalTag.label is changed (D-03: FK-only rename design).
    """
    from apps.reviews.services.tag_management import rename_canonical_tag

    org_tag = OrgCanonicalTagFactory(label="Food Quality", review_count=3)
    review = ReviewFactory(organisation=org_tag.organisation)
    review_tag = ReviewTagFactory(
        review=review, label="food quality", polarity="positive", canonical_tag=org_tag
    )
    original_review_tag_label = review_tag.label

    updated = rename_canonical_tag(
        tag=org_tag,
        new_label="Cuisine Quality",
        organisation_id=org_tag.organisation_id,
    )

    # Canonical tag label updated
    org_tag.refresh_from_db()
    assert org_tag.label == "Cuisine Quality"
    assert updated.label == "Cuisine Quality"

    # ReviewTag.label rows NOT touched (D-03 FK-only)
    review_tag.refresh_from_db()
    assert review_tag.label == original_review_tag_label  # unchanged


def test_rename_rejects_iexact_duplicate(db) -> None:
    """Rename to a case-variant of an existing label raises ValidationError (D-04, Pitfall 5).

    The DB UniqueConstraint on (organisation, label) is case-sensitive; this test
    verifies the service-level case-insensitive guard via label__iexact lookup.
    """
    from apps.reviews.services.tag_management import rename_canonical_tag

    org_tag = OrgCanonicalTagFactory(label="Food Quality")
    # Different case variant already exists in the same org
    OrgCanonicalTagFactory(organisation=org_tag.organisation, label="cuisine quality")

    with pytest.raises(ValidationError) as exc_info:
        rename_canonical_tag(
            tag=org_tag,
            new_label="Cuisine Quality",  # title-case of "cuisine quality" existing tag
            organisation_id=org_tag.organisation_id,
        )

    # Verify it's the duplicate guard (never silently merges)
    errors = exc_info.value.message_dict
    assert "label" in errors


def test_rename_title_case(db) -> None:
    """Rename normalizes the label to Title Case (D-04 server-side normalization).

    Input "food quality" must persist as "Food Quality".
    """
    from apps.reviews.services.tag_management import rename_canonical_tag

    org_tag = OrgCanonicalTagFactory(label="Old Label")

    updated = rename_canonical_tag(
        tag=org_tag,
        new_label="food quality",
        organisation_id=org_tag.organisation_id,
    )

    org_tag.refresh_from_db()
    assert org_tag.label == "Food Quality"
    assert updated.label == "Food Quality"


# ---------------------------------------------------------------------------
# Merge service tests (TMGT-05, D-06, D-07, T-25-AC1, T-25-AC3)
# ---------------------------------------------------------------------------


def test_merge_bulk_update_no_n_plus_one(db) -> None:
    """FK re-point is a single bulk UPDATE — no per-row N+1 loop (§6.10, D-06).

    CaptureQueriesContext verifies the number of queries is bounded regardless
    of the number of ReviewTag rows being re-pointed.
    """
    from apps.reviews.services.tag_management import merge_canonical_tags

    org_tag_source = OrgCanonicalTagFactory(label="Source Tag", review_count=5)
    org_tag_target = OrgCanonicalTagFactory(
        organisation=org_tag_source.organisation, label="Target Tag", review_count=2
    )
    # Create 5 ReviewTag rows pointing to source — each on a distinct review to
    # avoid the UniqueConstraint on (review, label, polarity).
    for _ in range(5):
        r = ReviewFactory(organisation=org_tag_source.organisation)
        ReviewTagFactory(
            review=r, label="source tag", polarity="positive", canonical_tag=org_tag_source
        )

    job = TagMergeJobFactory(
        organisation=org_tag_source.organisation,
        source_tag=org_tag_source,
        source_label=org_tag_source.label,
        target_tag=org_tag_target,
        target_label=org_tag_target.label,
        status=TagMergeJob.Status.PENDING,
    )

    # Patch distributed_lock to force acquired=True (no Redis in tests)
    with (
        patch("apps.reviews.services.tag_management.distributed_lock") as mock_lock,
        patch("apps.reviews.services.tag_management.dispatch_notification"),
    ):
        mock_lock.return_value.__enter__ = lambda s: True
        mock_lock.return_value.__exit__ = lambda s, *a: False

        with CaptureQueriesContext(connection) as ctx:
            merge_canonical_tags(job_id=job.pk)

    # Verify all ReviewTag rows re-pointed to target
    assert not ReviewTag.objects.filter(canonical_tag=org_tag_source).exists()
    assert ReviewTag.objects.filter(canonical_tag=org_tag_target).count() == 5

    # The FK re-point must be a single bulk UPDATE (not one UPDATE per row).
    # Django's on_delete=SET_NULL cascade generates a second SET_NULL statement
    # during source.delete() — that's expected and constant regardless of row count.
    # What we must NOT have is 5 individual per-row updates.
    update_queries = [q for q in ctx.captured_queries if "UPDATE" in q["sql"].upper()]
    reviewtag_updates = [q for q in update_queries if "reviews_reviewtag" in q["sql"].lower()]
    # Must be ≤ 2 statements: 1 bulk re-point + 1 SET NULL cascade (constant, not proportional to 5)
    assert len(reviewtag_updates) <= 2, (
        f"Expected ≤2 UPDATE statements for ReviewTag FK re-point (1 bulk + 1 cascade SET_NULL), "
        f"got {len(reviewtag_updates)}: {[q['sql'] for q in reviewtag_updates]}"
    )
    # The re-point statement must target all rows at once (SET canonical_tag_id = target)
    repoint_updates = [
        q for q in reviewtag_updates if "set" in q["sql"].lower() and "null" not in q["sql"].lower()
    ]
    assert len(repoint_updates) == 1, (
        f"Expected exactly 1 non-null bulk UPDATE for ReviewTag re-point, "
        f"got {len(repoint_updates)}: {[q['sql'] for q in repoint_updates]}"
    )


def test_merge_rollback_on_error(db) -> None:
    """Merge rolls back entirely if an error is raised mid-merge (transaction.atomic).

    After a mid-merge exception: source still exists, no FKs re-pointed.
    """
    from apps.reviews.services.tag_management import merge_canonical_tags

    org_tag_source = OrgCanonicalTagFactory(label="Source Tag", review_count=3)
    org_tag_target = OrgCanonicalTagFactory(
        organisation=org_tag_source.organisation, label="Target Tag", review_count=1
    )
    review = ReviewFactory(organisation=org_tag_source.organisation)
    ReviewTagFactory(
        review=review, label="source tag", polarity="positive", canonical_tag=org_tag_source
    )
    ReviewTagFactory(
        review=review, label="source tag", polarity="negative", canonical_tag=org_tag_source
    )

    job = TagMergeJobFactory(
        organisation=org_tag_source.organisation,
        source_tag=org_tag_source,
        source_label=org_tag_source.label,
        target_tag=org_tag_target,
        target_label=org_tag_target.label,
        status=TagMergeJob.Status.PENDING,
    )

    # Force an error after FK re-point by making _refresh_review_counts raise
    with (
        patch("apps.reviews.services.tag_management.distributed_lock") as mock_lock,
        patch(
            "apps.reviews.services.tag_management._refresh_review_counts",
            side_effect=RuntimeError("Simulated failure"),
        ),
    ):
        mock_lock.return_value.__enter__ = lambda s: True
        mock_lock.return_value.__exit__ = lambda s, *a: False

        with pytest.raises(RuntimeError, match="Simulated failure"):
            merge_canonical_tags(job_id=job.pk)

    # Transaction must have rolled back: source tag still exists
    assert OrgCanonicalTag.objects.filter(pk=org_tag_source.pk).exists(), (
        "Source tag should still exist after rollback"
    )
    # No ReviewTag rows should have been re-pointed (all rolled back)
    assert ReviewTag.objects.filter(canonical_tag=org_tag_source).count() == 2, (
        "ReviewTag FK re-points should be rolled back"
    )
    assert ReviewTag.objects.filter(canonical_tag=org_tag_target).count() == 0, (
        "No rows should point to target after rollback"
    )


def test_merge_cross_org_blocked(db) -> None:
    """A merge job whose source/target belong to org B cannot be executed against org A.

    T-25-AC1: service fetches source/target with organisation_id filter — a
    wrong-org id raises OrgCanonicalTag.DoesNotExist (→ caller maps to 404).
    """
    from apps.reviews.services.tag_management import merge_canonical_tags

    # Org A tags
    org_a_source = OrgCanonicalTagFactory(label="Org A Source", review_count=2)
    org_a_target = OrgCanonicalTagFactory(
        organisation=org_a_source.organisation, label="Org A Target", review_count=1
    )

    # Org B tags — a job that claims org_a_source as source but belongs to org B
    org_b_source = OrgCanonicalTagFactory(label="Org B Source", review_count=5)
    # Create job with org_b's organisation but org_a's source/target FKs (injection attempt)
    job = TagMergeJobFactory(
        organisation=org_b_source.organisation,  # belongs to org B
        source_tag=org_a_source,  # org A's source FK (cross-org attack)
        source_label=org_a_source.label,
        target_tag=org_a_target,  # org A's target FK (cross-org attack)
        target_label=org_a_target.label,
        status=TagMergeJob.Status.PENDING,
    )

    with (
        patch("apps.reviews.services.tag_management.distributed_lock") as mock_lock,
    ):
        mock_lock.return_value.__enter__ = lambda s: True
        mock_lock.return_value.__exit__ = lambda s, *a: False

        # Should raise DoesNotExist because org A's tags don't belong to org B
        with pytest.raises(OrgCanonicalTag.DoesNotExist):
            merge_canonical_tags(job_id=job.pk)

    # Verify org A's source tag was never touched
    assert OrgCanonicalTag.objects.filter(pk=org_a_source.pk).exists()


def test_merge_dispatches_notification(db) -> None:
    """dispatch_notification is called exactly once with tag_merge_complete on SUCCESS (D-07)."""
    from apps.reviews.services.tag_management import merge_canonical_tags

    org_tag_source = OrgCanonicalTagFactory(label="Source Tag", review_count=2)
    org_tag_target = OrgCanonicalTagFactory(
        organisation=org_tag_source.organisation, label="Target Tag", review_count=1
    )

    job = TagMergeJobFactory(
        organisation=org_tag_source.organisation,
        source_tag=org_tag_source,
        source_label=org_tag_source.label,
        target_tag=org_tag_target,
        target_label=org_tag_target.label,
        status=TagMergeJob.Status.PENDING,
    )

    with (
        patch("apps.reviews.services.tag_management.distributed_lock") as mock_lock,
        patch("apps.reviews.services.tag_management.dispatch_notification") as mock_notify,
    ):
        mock_lock.return_value.__enter__ = lambda s: True
        mock_lock.return_value.__exit__ = lambda s, *a: False

        merge_canonical_tags(job_id=job.pk)

    # Notification dispatched exactly once
    mock_notify.assert_called_once()
    call_kwargs = mock_notify.call_args.kwargs
    assert call_kwargs["notification_type"] == "tag_merge_complete"
    assert call_kwargs["org_admins_only"] is True
    assert call_kwargs["organisation_id"] == org_tag_source.organisation_id
