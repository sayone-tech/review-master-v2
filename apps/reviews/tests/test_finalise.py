"""Phase 23 — Tests for the canonical tag finalising pass service and selectors."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.reviews.models import OrgCanonicalTag, ReviewTag
from apps.reviews.selectors.canonical_tags import (
    get_duplicate_canonical_tag_groups,
    get_null_straggler_review_tags,
)
from apps.reviews.services.finalise import run_finalise_canonical_tags
from apps.reviews.tests.factories import (
    OrgCanonicalTagFactory,
    ReviewFactory,
    ReviewTagFactory,
)
from apps.shops.tests.factories import ShopFactory

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Selector tests
# ---------------------------------------------------------------------------


class TestGetDuplicateCanonicalTagGroups:
    def test_returns_lowercased_labels_with_case_insensitive_duplicates(self, db) -> None:
        """Two OrgCanonicalTag rows differing only in case are returned as a single group."""
        org_tag_1 = OrgCanonicalTagFactory(label="Food Quality", review_count=5)
        OrgCanonicalTagFactory(
            organisation=org_tag_1.organisation,
            label="food quality",
            review_count=3,
        )
        result = get_duplicate_canonical_tag_groups(organisation_id=org_tag_1.organisation_id)
        assert "food quality" in result
        assert len(result) == 1

    def test_all_unique_labels_returns_empty(self, db) -> None:
        """Org with all-distinct case-insensitive labels returns an empty list."""
        org_tag = OrgCanonicalTagFactory(label="Food Quality")
        OrgCanonicalTagFactory(organisation=org_tag.organisation, label="Service Speed")
        OrgCanonicalTagFactory(organisation=org_tag.organisation, label="Cleanliness")
        result = get_duplicate_canonical_tag_groups(organisation_id=org_tag.organisation_id)
        assert result == []

    def test_cross_org_isolation(self, db) -> None:
        """Duplicate labels in another org do not appear in the target org's results."""
        org_tag_1 = OrgCanonicalTagFactory(label="Food Quality")
        # Different org has a duplicate — should not appear
        other_tag = OrgCanonicalTagFactory(label="Food Quality")
        OrgCanonicalTagFactory(
            organisation=other_tag.organisation,
            label="food quality",
        )
        result = get_duplicate_canonical_tag_groups(organisation_id=org_tag_1.organisation_id)
        assert result == []

    def test_three_variants_returns_single_group(self, db) -> None:
        """Three variants of the same label (Food Quality, food quality, FOOD QUALITY)."""
        tag = OrgCanonicalTagFactory(label="Food Quality")
        OrgCanonicalTagFactory(organisation=tag.organisation, label="food quality")
        OrgCanonicalTagFactory(organisation=tag.organisation, label="FOOD QUALITY")
        result = get_duplicate_canonical_tag_groups(organisation_id=tag.organisation_id)
        assert result == ["food quality"]


class TestGetNullStragglerReviewTags:
    def test_returns_tags_with_null_canonical_tag_in_org(self, db) -> None:
        review = ReviewFactory()
        tag = ReviewTagFactory(review=review, canonical_tag=None)
        result = list(
            get_null_straggler_review_tags(organisation_id=review.organisation_id, limit=100)
        )
        assert tag in result

    def test_excludes_soft_deleted_reviews(self, db) -> None:
        review = ReviewFactory(deleted_at=timezone.now())
        ReviewTagFactory(review=review, canonical_tag=None)
        result = list(
            get_null_straggler_review_tags(organisation_id=review.organisation_id, limit=100)
        )
        assert result == []

    def test_excludes_already_mapped_tags(self, db) -> None:
        review = ReviewFactory()
        canonical = OrgCanonicalTagFactory(organisation=review.organisation)
        ReviewTagFactory(review=review, canonical_tag=canonical)
        result = list(
            get_null_straggler_review_tags(organisation_id=review.organisation_id, limit=100)
        )
        assert result == []

    def test_cross_org_isolation(self, db) -> None:
        review = ReviewFactory()
        ReviewTagFactory(review=review, canonical_tag=None)
        # Another org should not appear
        other_review = ReviewFactory()
        ReviewTagFactory(review=other_review, canonical_tag=None)
        result = list(
            get_null_straggler_review_tags(organisation_id=review.organisation_id, limit=100)
        )
        # Only tags from the target org
        for rt in result:
            assert rt.review.organisation_id == review.organisation_id

    def test_bounded_by_limit(self, db) -> None:
        review = ReviewFactory()
        for _ in range(10):
            ReviewTagFactory(review=review, canonical_tag=None)
        result = list(
            get_null_straggler_review_tags(organisation_id=review.organisation_id, limit=5)
        )
        assert len(result) == 5


# ---------------------------------------------------------------------------
# Service tests: run_finalise_canonical_tags
# ---------------------------------------------------------------------------


def _mock_emit() -> MagicMock:
    return MagicMock()


@pytest.fixture
def patched_finalise():
    """Patch distributed_lock to always be acquired and emit_progress_event to a mock.

    Also patches read_progress_snapshot (returns a minimal snapshot with fetched=5,
    enriched=5) and write_progress_snapshot so tests do not require a live Redis
    connection. The snapshot values are small defaults sufficient for most tests;
    tests that need specific values can override via additional patches.
    """
    lock_cm = MagicMock()
    lock_cm.__enter__ = MagicMock(return_value=True)
    lock_cm.__exit__ = MagicMock(return_value=False)
    # CR-01 fix: _run_finalise now calls read_progress_snapshot to get accumulated
    # fetched/enriched counts for the sync.complete payload.
    _default_snap = {"fetched": 5, "enriched": 5, "status": "enriching"}
    with (
        patch(
            "apps.reviews.services.finalise.distributed_lock",
            return_value=lock_cm,
        ),
        patch(
            "apps.reviews.services.finalise.emit_progress_event",
        ) as mock_emit,
        patch(
            "apps.reviews.services.finalise.write_progress_snapshot",
        ),
        patch(
            "apps.reviews.services.finalise.read_progress_snapshot",
            return_value=_default_snap,
        ),
        # CR-02 fix: _dispatch_sync_complete_notifications is now called from
        # _run_finalise via a local import from enrichment; patch at source module so
        # all call paths are intercepted.
        patch(
            "apps.reviews.services.enrichment._dispatch_sync_complete_notifications",
        ),
    ):
        yield mock_emit


class TestRunFinaliseCanonicalTags:
    def test_dedup_merge_winner_higher_review_count(self, db, patched_finalise) -> None:
        """Winner is the row with the higher review_count."""
        tag_high = OrgCanonicalTagFactory(label="Food Quality", review_count=10)
        tag_low = OrgCanonicalTagFactory(
            organisation=tag_high.organisation,
            label="food quality",
            review_count=3,
        )
        run_finalise_canonical_tags(
            organisation_id=tag_high.organisation_id,
            shop_id=1,
        )
        assert OrgCanonicalTag.objects.filter(pk=tag_high.pk).exists()
        assert not OrgCanonicalTag.objects.filter(pk=tag_low.pk).exists()

    def test_dedup_tie_winner_is_earliest_created(self, db, patched_finalise) -> None:
        """On tie in review_count, the earliest created_at row wins."""
        earlier = OrgCanonicalTagFactory(
            label="Food Quality",
            review_count=5,
        )
        later = OrgCanonicalTagFactory(
            organisation=earlier.organisation,
            label="food quality",
            review_count=5,
        )
        # Ensure earlier was actually created earlier
        earlier.created_at = timezone.now() - timezone.timedelta(days=1)
        earlier.save(update_fields=["created_at"])

        run_finalise_canonical_tags(
            organisation_id=earlier.organisation_id,
            shop_id=1,
        )
        assert OrgCanonicalTag.objects.filter(pk=earlier.pk).exists()
        assert not OrgCanonicalTag.objects.filter(pk=later.pk).exists()

    def test_fk_repointed_to_winner(self, db, patched_finalise) -> None:
        """After merge, loser's ReviewTag FKs point to the winner."""
        review = ReviewFactory()
        winner = OrgCanonicalTagFactory(
            organisation=review.organisation, label="Food Quality", review_count=10
        )
        loser = OrgCanonicalTagFactory(
            organisation=review.organisation, label="food quality", review_count=2
        )
        rt = ReviewTagFactory(review=review, canonical_tag=loser)

        run_finalise_canonical_tags(
            organisation_id=review.organisation_id,
            shop_id=1,
        )
        rt.refresh_from_db()
        assert rt.canonical_tag_id == winner.pk
        assert not OrgCanonicalTag.objects.filter(pk=loser.pk).exists()

    def test_loser_deleted(self, db, patched_finalise) -> None:
        """The loser OrgCanonicalTag row is hard-deleted after merge."""
        tag_a = OrgCanonicalTagFactory(label="Food Quality", review_count=7)
        OrgCanonicalTagFactory(
            organisation=tag_a.organisation, label="FOOD QUALITY", review_count=2
        )
        run_finalise_canonical_tags(
            organisation_id=tag_a.organisation_id,
            shop_id=1,
        )
        surviving = OrgCanonicalTag.objects.filter(
            organisation_id=tag_a.organisation_id,
            label__iexact="food quality",
        )
        assert surviving.count() == 1

    def test_transitive_collapse_three_variants(self, db, patched_finalise) -> None:
        """Food Quality / food quality / FOOD QUALITY all collapse to one winner."""
        tag_a = OrgCanonicalTagFactory(label="Food Quality", review_count=10)
        OrgCanonicalTagFactory(
            organisation=tag_a.organisation, label="food quality", review_count=3
        )
        OrgCanonicalTagFactory(
            organisation=tag_a.organisation, label="FOOD QUALITY", review_count=1
        )
        run_finalise_canonical_tags(
            organisation_id=tag_a.organisation_id,
            shop_id=1,
        )
        assert OrgCanonicalTag.objects.filter(organisation_id=tag_a.organisation_id).count() == 1
        assert OrgCanonicalTag.objects.filter(pk=tag_a.pk).exists()

    def test_backfill_null_straggler_by_case_insensitive_match(self, db, patched_finalise) -> None:
        """Null-canonical_tag ReviewTag is assigned to matching OrgCanonicalTag by label."""
        review = ReviewFactory()
        canonical = OrgCanonicalTagFactory(organisation=review.organisation, label="Food Quality")
        rt = ReviewTagFactory(review=review, label="food quality", canonical_tag=None)

        run_finalise_canonical_tags(
            organisation_id=review.organisation_id,
            shop_id=1,
        )
        rt.refresh_from_db()
        assert rt.canonical_tag_id == canonical.pk

    def test_review_count_refreshed_from_aggregate(self, db, patched_finalise) -> None:
        """review_count on OrgCanonicalTag matches the aggregate ReviewTag count after pass."""
        review1 = ReviewFactory()
        review2 = ReviewFactory(
            organisation=review1.organisation,
            shop=review1.shop,
        )
        canonical = OrgCanonicalTagFactory(organisation=review1.organisation, review_count=0)
        ReviewTagFactory(review=review1, canonical_tag=canonical)
        ReviewTagFactory(review=review2, canonical_tag=canonical)

        run_finalise_canonical_tags(
            organisation_id=review1.organisation_id,
            shop_id=1,
        )
        canonical.refresh_from_db()
        # review_count must equal the aggregate count, not 0 or an inline increment
        aggregate_count = ReviewTag.objects.filter(canonical_tag=canonical).count()
        assert canonical.review_count == aggregate_count == 2

    def test_no_op_when_no_duplicates_and_no_stragglers(self, db, patched_finalise) -> None:
        """Running the pass with no duplicates and no stragglers makes no destructive changes."""
        tag_a = OrgCanonicalTagFactory(label="Food Quality")
        tag_b = OrgCanonicalTagFactory(organisation=tag_a.organisation, label="Service Speed")
        run_finalise_canonical_tags(
            organisation_id=tag_a.organisation_id,
            shop_id=1,
        )
        assert OrgCanonicalTag.objects.filter(pk=tag_a.pk).exists()
        assert OrgCanonicalTag.objects.filter(pk=tag_b.pk).exists()

    def test_fk_repoint_no_n_plus_one(self, db, patched_finalise) -> None:
        """FK re-point UPDATE count does not scale with the number of ReviewTags."""
        review = ReviewFactory()
        OrgCanonicalTagFactory(
            organisation=review.organisation, label="Food Quality", review_count=10
        )
        loser = OrgCanonicalTagFactory(
            organisation=review.organisation, label="food quality", review_count=2
        )
        # Create many ReviewTags pointing to the loser. Each needs a distinct
        # label so the (review_id, label, polarity) unique constraint never
        # collides — factory-default Faker("word") labels can repeat depending
        # on the global Faker sequence position (which shifts as other test
        # modules are added to the suite), making this test order-fragile.
        for i in range(20):
            ReviewTagFactory(
                review=review, canonical_tag=loser, label=f"finalise tag {i}", polarity="positive"
            )

        with CaptureQueriesContext(connection) as ctx:
            run_finalise_canonical_tags(
                organisation_id=review.organisation_id,
                shop_id=1,
            )
        update_queries = [q for q in ctx.captured_queries if "UPDATE" in q["sql"].upper()]
        # FK re-point must be 1 UPDATE regardless of ReviewTag count (CLAUDE.md §6.10).
        # Bounded ceiling covers:
        #   - 1 UPDATE ReviewTag to re-point FKs to winner (never N UPDATEs for N tags)
        #   - 1 UPDATE from Django SET_NULL cascade on loser delete
        #   - 1 bulk_update for review_count refresh
        # If this grows beyond 7, something is N+1 — investigate immediately.
        assert len(update_queries) <= 7, (
            f"Expected at most 7 UPDATE queries, got {len(update_queries)}: "
            + str([q["sql"][:100] for q in update_queries])
        )

    def test_straggler_backfill_no_n_plus_one(self, db, patched_finalise) -> None:
        """Straggler backfill issues O(distinct canonical_tag_ids) UPDATEs, not O(stragglers) (CR-03).

        Creates multiple reviews so each can carry one ReviewTag per label (unique per review).
        Verifies the UPDATE count does not scale with the number of straggler rows.
        """
        # Need one Review per ReviewTag (unique constraint: review_id + label + polarity).
        shop = ShopFactory()
        org = shop.organisation
        canonical_a = OrgCanonicalTagFactory(organisation=org, label="Food Quality")
        canonical_b = OrgCanonicalTagFactory(organisation=org, label="Service Speed")

        # 5 stragglers mapping to canonical_a (one per review to avoid UNIQUE violation)
        reviews_a = [ReviewFactory(shop=shop, organisation=org) for _ in range(5)]
        for r in reviews_a:
            ReviewTagFactory(review=r, label="food quality", canonical_tag=None)

        # 5 stragglers mapping to canonical_b
        reviews_b = [ReviewFactory(shop=shop, organisation=org) for _ in range(5)]
        for r in reviews_b:
            ReviewTagFactory(review=r, label="service speed", canonical_tag=None)

        with CaptureQueriesContext(connection) as ctx:
            run_finalise_canonical_tags(
                organisation_id=shop.organisation_id,
                shop_id=shop.pk,
            )
        update_queries = [q for q in ctx.captured_queries if "UPDATE" in q["sql"].upper()]
        # With 10 stragglers across 2 canonical tags: must be 2 batch UPDATEs (one per group),
        # not 10 individual UPDATEs. Overall ceiling of 10 covers straggler UPDATEs +
        # bulk_update for review_count and any cascade updates.
        assert len(update_queries) <= 10, (
            f"Expected at most 10 UPDATE queries (O(groups) not O(stragglers)), "
            f"got {len(update_queries)}: " + str([q["sql"][:100] for q in update_queries])
        )
        # Verify both canonical tags got the FK assigned
        assert ReviewTag.objects.filter(canonical_tag=canonical_a).count() == 5
        assert ReviewTag.objects.filter(canonical_tag=canonical_b).count() == 5

    def test_early_return_when_lock_not_acquired(self, db) -> None:
        """Service returns immediately (skipped) when distributed lock is not acquired."""
        lock_cm = MagicMock()
        lock_cm.__enter__ = MagicMock(return_value=False)
        lock_cm.__exit__ = MagicMock(return_value=False)
        tag = OrgCanonicalTagFactory(label="Food Quality", review_count=5)
        OrgCanonicalTagFactory(organisation=tag.organisation, label="food quality", review_count=2)
        with patch(
            "apps.reviews.services.finalise.distributed_lock",
            return_value=lock_cm,
        ):
            result = run_finalise_canonical_tags(
                organisation_id=tag.organisation_id,
                shop_id=1,
            )
        assert result.get("skipped") is True
        # Both rows should still exist (no merge happened)
        assert OrgCanonicalTag.objects.filter(organisation_id=tag.organisation_id).count() == 2

    def test_cross_org_isolation(self, db, patched_finalise) -> None:
        """Finalising pass only touches OrgCanonicalTag/ReviewTag rows for the given org."""
        # Target org: has duplicates
        tag_a = OrgCanonicalTagFactory(label="Food Quality", review_count=5)
        OrgCanonicalTagFactory(
            organisation=tag_a.organisation, label="food quality", review_count=2
        )
        # Other org: also has duplicates — should be untouched
        other_tag = OrgCanonicalTagFactory(label="Service Speed", review_count=3)
        other_dup = OrgCanonicalTagFactory(
            organisation=other_tag.organisation, label="service speed", review_count=1
        )

        run_finalise_canonical_tags(
            organisation_id=tag_a.organisation_id,
            shop_id=1,
        )
        # Target org: merged
        assert OrgCanonicalTag.objects.filter(organisation_id=tag_a.organisation_id).count() == 1
        # Other org: untouched
        assert OrgCanonicalTag.objects.filter(pk=other_tag.pk).exists()
        assert OrgCanonicalTag.objects.filter(pk=other_dup.pk).exists()

    def test_progress_events_emitted_after_commit(self, db) -> None:
        """sync.finalising.progress and sync.complete events are emitted by the service."""
        lock_cm = MagicMock()
        lock_cm.__enter__ = MagicMock(return_value=True)
        lock_cm.__exit__ = MagicMock(return_value=False)
        tag = OrgCanonicalTagFactory(label="Food Quality")
        with (
            patch(
                "apps.reviews.services.finalise.distributed_lock",
                return_value=lock_cm,
            ),
            patch(
                "apps.reviews.services.finalise.emit_progress_event",
            ) as mock_emit,
            patch("apps.reviews.services.finalise.write_progress_snapshot"),
            # CR-01: read_progress_snapshot is now called in _run_finalise
            patch(
                "apps.reviews.services.finalise.read_progress_snapshot",
                return_value={"fetched": 3, "enriched": 3, "status": "enriching"},
            ),
            # CR-02: notifications are now dispatched from _run_finalise
            patch("apps.reviews.services.enrichment._dispatch_sync_complete_notifications"),
        ):
            run_finalise_canonical_tags(
                organisation_id=tag.organisation_id,
                shop_id=42,
            )
        event_types = [call.kwargs["payload"]["type"] for call in mock_emit.call_args_list]
        assert "sync.finalising.progress" in event_types
        assert "sync.complete" in event_types

    def test_sync_complete_payload_includes_required_fields(self, db, patched_finalise) -> None:
        """sync.complete payload must contain total_fetched, total_enriched, duration_seconds (CR-01)."""
        tag = OrgCanonicalTagFactory(label="Food Quality")
        run_finalise_canonical_tags(
            organisation_id=tag.organisation_id,
            shop_id=99,
        )
        # patched_finalise yields mock_emit; find the sync.complete call
        complete_calls = [
            call
            for call in patched_finalise.call_args_list
            if call.kwargs.get("payload", {}).get("type") == "sync.complete"
        ]
        assert len(complete_calls) == 1, "Expected exactly one sync.complete event"
        payload = complete_calls[0].kwargs["payload"]
        assert "total_fetched" in payload, "sync.complete must include total_fetched"
        assert "total_enriched" in payload, "sync.complete must include total_enriched"
        assert "duration_seconds" in payload, "sync.complete must include duration_seconds"
        # Values must be drawn from the snapshot (patched to fetched=5, enriched=5)
        assert payload["total_fetched"] == 5
        assert payload["total_enriched"] == 5
        assert isinstance(payload["duration_seconds"], float)

    def test_notifications_dispatched_when_total_fetched_nonzero(self, db) -> None:
        """_dispatch_sync_complete_notifications is called when total_fetched > 0 (CR-02)."""
        lock_cm = MagicMock()
        lock_cm.__enter__ = MagicMock(return_value=True)
        lock_cm.__exit__ = MagicMock(return_value=False)
        tag = OrgCanonicalTagFactory(label="Food Quality")
        with (
            patch("apps.reviews.services.finalise.distributed_lock", return_value=lock_cm),
            patch("apps.reviews.services.finalise.emit_progress_event"),
            patch("apps.reviews.services.finalise.write_progress_snapshot"),
            patch(
                "apps.reviews.services.finalise.read_progress_snapshot",
                return_value={"fetched": 10, "enriched": 10, "status": "enriching"},
            ),
            patch(
                "apps.reviews.services.enrichment._dispatch_sync_complete_notifications",
            ) as mock_notify,
        ):
            run_finalise_canonical_tags(
                organisation_id=tag.organisation_id,
                shop_id=7,
            )
        mock_notify.assert_called_once_with(
            shop_id=7,
            organisation_id=tag.organisation_id,
            total_fetched=10,
        )

    def test_notifications_not_dispatched_when_total_fetched_zero(self, db) -> None:
        """_dispatch_sync_complete_notifications is NOT called when fetched=0 (no reviews)."""
        lock_cm = MagicMock()
        lock_cm.__enter__ = MagicMock(return_value=True)
        lock_cm.__exit__ = MagicMock(return_value=False)
        tag = OrgCanonicalTagFactory(label="Food Quality")
        with (
            patch("apps.reviews.services.finalise.distributed_lock", return_value=lock_cm),
            patch("apps.reviews.services.finalise.emit_progress_event"),
            patch("apps.reviews.services.finalise.write_progress_snapshot"),
            patch(
                "apps.reviews.services.finalise.read_progress_snapshot",
                return_value={"fetched": 0, "enriched": 0, "status": "enriching"},
            ),
            patch(
                "apps.reviews.services.enrichment._dispatch_sync_complete_notifications",
            ) as mock_notify,
        ):
            run_finalise_canonical_tags(
                organisation_id=tag.organisation_id,
                shop_id=7,
            )
        mock_notify.assert_not_called()


# ---------------------------------------------------------------------------
# Task thin-wrapper test
# ---------------------------------------------------------------------------


class TestFinaliseCanonicalTagsTask:
    def test_task_import_and_routes_to_service(self, db) -> None:
        """finalize_canonical_tags_task is importable and calls the service."""
        from apps.reviews.tasks import finalize_canonical_tags_task

        lock_cm = MagicMock()
        lock_cm.__enter__ = MagicMock(return_value=True)
        lock_cm.__exit__ = MagicMock(return_value=False)
        tag = OrgCanonicalTagFactory(label="No Dupes")
        with (
            patch(
                "apps.reviews.services.finalise.distributed_lock",
                return_value=lock_cm,
            ),
            patch("apps.reviews.services.finalise.emit_progress_event"),
            patch("apps.reviews.services.finalise.write_progress_snapshot"),
            # CR-01: read_progress_snapshot is now called in _run_finalise
            patch(
                "apps.reviews.services.finalise.read_progress_snapshot",
                return_value={"fetched": 0, "enriched": 0, "status": "enriching"},
            ),
            # CR-02: notifications dispatched from _run_finalise
            patch("apps.reviews.services.enrichment._dispatch_sync_complete_notifications"),
        ):
            result = finalize_canonical_tags_task(organisation_id=tag.organisation_id, shop_id=1)
        assert isinstance(result, dict)
