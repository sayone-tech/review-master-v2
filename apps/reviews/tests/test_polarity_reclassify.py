"""Wave-0 failing test scaffold for Phase 24 polarity auto-reclassification.

These tests import apps.reviews.services.reclassify which does NOT exist yet.
Collection/import fails at RED until Plan 02 implements the service.

Coverage areas per 24-VALIDATION.md:
  (a) flip always_positive → mixed when opposite > threshold over min-sample
  (b) no flip below MIN_REVIEWS (insufficient sample)
  (c) boundary — exactly 0.15 ratio does NOT flip (strict >, D-02)
  (d) already-mixed tags skipped; no AuditLog row written (one-way sticky, D-01)
  (e) neutral reviews count in denominator only, never numerator (D-02)
  (f) soft-deleted reviews excluded from denominator (D-02)
  (g) window by Review.review_create_time — older reviews excluded (D-03)
  (h) multi-tenant isolation — org-A flip never touches org-B tags (§9/§22)
  (i) idempotency — second run writes nothing extra (D-05)
  (j) no-N+1 query count fixed regardless of tag count (CLAUDE.md §6.9)
  (k) POL-03 AuditLog row written per flip with correct fields (D-06)
  POL-01 re-confirmation: freshly created OrgCanonicalTag has non-empty polarity_type
"""

from __future__ import annotations

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.common.models import AuditLog
from apps.organisations.tests.factories import OrganisationFactory
from apps.reviews.models import OrgCanonicalTag
from apps.reviews.services.reclassify import (
    run_polarity_reclassification,  # RED: does not exist yet
)
from apps.reviews.tests.factories import (
    OrgCanonicalTagFactory,
    ReviewFactory,
    ReviewTagFactory,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_always_positive_tag(org, *, label: str | None = None) -> OrgCanonicalTag:
    return OrgCanonicalTagFactory(
        organisation=org,
        polarity_type=OrgCanonicalTag.PolarityType.ALWAYS_POSITIVE,
        label=label or "service",
    )


def _make_always_negative_tag(org, *, label: str | None = None) -> OrgCanonicalTag:
    return OrgCanonicalTagFactory(
        organisation=org,
        polarity_type=OrgCanonicalTag.PolarityType.ALWAYS_NEGATIVE,
        label=label or "staff",
    )


def _attach_review_tag(org, canonical_tag, *, polarity: str, days_ago: int = 5) -> None:
    """Create a Review + ReviewTag linked to canonical_tag within the window."""
    create_time = timezone.now() - timezone.timedelta(days=days_ago)
    review = ReviewFactory(organisation=org, review_create_time=create_time)
    ReviewTagFactory(review=review, canonical_tag=canonical_tag, polarity=polarity)


# ---------------------------------------------------------------------------
# (a) flip always_positive → mixed when opposite > threshold over min-sample
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_flip_always_positive_to_mixed_when_threshold_exceeded() -> None:
    """A tag flips to mixed when negative/total > 0.15 and denominator >= 10."""
    org = OrganisationFactory()
    tag = _make_always_positive_tag(org)

    # 11 reviews: 2 negative, 9 positive → ratio = 2/11 ≈ 0.18 > 0.15
    for _ in range(2):
        _attach_review_tag(org, tag, polarity="negative")
    for _ in range(9):
        _attach_review_tag(org, tag, polarity="positive")

    run_polarity_reclassification()

    tag.refresh_from_db()
    assert tag.polarity_type == OrgCanonicalTag.PolarityType.MIXED


@pytest.mark.django_db
def test_flip_always_negative_to_mixed_when_threshold_exceeded() -> None:
    """An always_negative tag flips to mixed when positive/total > 0.15."""
    org = OrganisationFactory()
    tag = _make_always_negative_tag(org)

    # 11 reviews: 2 positive, 9 negative → ratio = 2/11 ≈ 0.18 > 0.15
    for _ in range(2):
        _attach_review_tag(org, tag, polarity="positive")
    for _ in range(9):
        _attach_review_tag(org, tag, polarity="negative")

    run_polarity_reclassification()

    tag.refresh_from_db()
    assert tag.polarity_type == OrgCanonicalTag.PolarityType.MIXED


# ---------------------------------------------------------------------------
# (b) no flip below MIN_REVIEWS (insufficient sample)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_no_flip_below_min_reviews() -> None:
    """Tags with fewer than 10 reviews in the window are NOT flipped (D-02)."""
    org = OrganisationFactory()
    tag = _make_always_positive_tag(org)

    # 4 reviews: 1 negative, 3 positive → ratio = 0.25 > threshold,
    # but denominator=4 < MIN_REVIEWS=10 → no flip
    _attach_review_tag(org, tag, polarity="negative")
    for _ in range(3):
        _attach_review_tag(org, tag, polarity="positive")

    run_polarity_reclassification()

    tag.refresh_from_db()
    assert tag.polarity_type == OrgCanonicalTag.PolarityType.ALWAYS_POSITIVE


# ---------------------------------------------------------------------------
# (c) boundary — exactly 0.15 ratio does NOT flip (strict >, D-02)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_boundary_exactly_threshold_does_not_flip() -> None:
    """Exactly 0.15 ratio (15% opposite) does NOT flip; flip is strict > (D-02)."""
    org = OrganisationFactory()
    tag = _make_always_positive_tag(org)

    # 20 reviews: 3 negative, 17 positive → 3/20 = 0.15 exactly
    for _ in range(3):
        _attach_review_tag(org, tag, polarity="negative")
    for _ in range(17):
        _attach_review_tag(org, tag, polarity="positive")

    run_polarity_reclassification()

    tag.refresh_from_db()
    assert tag.polarity_type == OrgCanonicalTag.PolarityType.ALWAYS_POSITIVE


# ---------------------------------------------------------------------------
# (d) already-mixed tags skipped; no AuditLog written (D-01, one-way sticky)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_mixed_tags_are_skipped_no_audit_log() -> None:
    """Mixed tags are not evaluated and produce no AuditLog row (D-01)."""
    org = OrganisationFactory()
    tag = OrgCanonicalTagFactory(organisation=org, polarity_type=OrgCanonicalTag.PolarityType.MIXED)

    # Even with heavily opposite reviews, mixed stays mixed
    for _ in range(20):
        _attach_review_tag(org, tag, polarity="negative")

    run_polarity_reclassification()

    tag.refresh_from_db()
    assert tag.polarity_type == OrgCanonicalTag.PolarityType.MIXED
    assert (
        AuditLog.objects.filter(action="polarity_reclassified", entity_id=str(tag.pk)).count() == 0
    )


# ---------------------------------------------------------------------------
# (e) neutral reviews count in denominator only, never numerator (D-02)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_neutral_reviews_in_denominator_only() -> None:
    """Neutral reviews dilute the ratio but are never the trigger (D-02)."""
    org = OrganisationFactory()
    tag = _make_always_positive_tag(org)

    # 20 reviews: 2 negative, 8 neutral, 10 positive
    # opposite (negative) = 2; denominator = 20; ratio = 2/20 = 0.10 < 0.15
    # → should NOT flip
    for _ in range(2):
        _attach_review_tag(org, tag, polarity="negative")
    for _ in range(8):
        _attach_review_tag(org, tag, polarity="neutral")
    for _ in range(10):
        _attach_review_tag(org, tag, polarity="positive")

    run_polarity_reclassification()

    tag.refresh_from_db()
    assert tag.polarity_type == OrgCanonicalTag.PolarityType.ALWAYS_POSITIVE


@pytest.mark.django_db
def test_neutral_reviews_never_trigger_flip_even_when_majority() -> None:
    """A tag with mostly neutral reviews is NOT flipped by neutrals (D-02)."""
    org = OrganisationFactory()
    tag = _make_always_positive_tag(org)

    # 20 reviews: 0 negative (opposite), 18 neutral, 2 positive
    # opposite ratio = 0/20 = 0 → no flip
    for _ in range(18):
        _attach_review_tag(org, tag, polarity="neutral")
    for _ in range(2):
        _attach_review_tag(org, tag, polarity="positive")

    run_polarity_reclassification()

    tag.refresh_from_db()
    assert tag.polarity_type == OrgCanonicalTag.PolarityType.ALWAYS_POSITIVE


# ---------------------------------------------------------------------------
# (f) soft-deleted reviews excluded from denominator (D-02)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_soft_deleted_reviews_excluded() -> None:
    """Soft-deleted (Review.deleted_at set) reviews are excluded from the window (D-02)."""
    org = OrganisationFactory()
    tag = _make_always_positive_tag(org)

    # 10 active reviews: 0 negative → ratio = 0 → no flip
    for _ in range(10):
        _attach_review_tag(org, tag, polarity="positive")

    # 20 soft-deleted reviews that are negative; if included these would flip
    create_time = timezone.now() - timezone.timedelta(days=2)
    for _ in range(20):
        review = ReviewFactory(
            organisation=org,
            review_create_time=create_time,
            deleted_at=timezone.now(),
        )
        ReviewTagFactory(review=review, canonical_tag=tag, polarity="negative")

    run_polarity_reclassification()

    tag.refresh_from_db()
    assert tag.polarity_type == OrgCanonicalTag.PolarityType.ALWAYS_POSITIVE


# ---------------------------------------------------------------------------
# (g) window by Review.review_create_time — older reviews excluded (D-03)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_reviews_older_than_window_excluded() -> None:
    """Reviews older than POLARITY_RECLASSIFY_WINDOW_DAYS are excluded (D-03)."""
    org = OrganisationFactory()
    tag = _make_always_positive_tag(org)

    # 20 in-window positive reviews → denominator = 20, numerator = 0 → no flip
    for _ in range(20):
        _attach_review_tag(org, tag, polarity="positive", days_ago=5)

    # 50 out-of-window negative reviews (31 days ago) — should be excluded
    old_time = timezone.now() - timezone.timedelta(days=31)
    for _ in range(50):
        review = ReviewFactory(organisation=org, review_create_time=old_time)
        ReviewTagFactory(review=review, canonical_tag=tag, polarity="negative")

    run_polarity_reclassification()

    tag.refresh_from_db()
    assert tag.polarity_type == OrgCanonicalTag.PolarityType.ALWAYS_POSITIVE


# ---------------------------------------------------------------------------
# (h) multi-tenant isolation — org-A flip never touches org-B tags (§9/§22)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_multi_tenant_isolation() -> None:
    """An org-A reclassification never reads or writes org-B tags (§9, §22)."""
    org_a = OrganisationFactory()
    org_b = OrganisationFactory()

    # org_a: qualifying flip scenario (ratio > 0.15, denominator >= 10)
    tag_a = _make_always_positive_tag(org_a, label="service")
    for _ in range(2):
        _attach_review_tag(org_a, tag_a, polarity="negative")
    for _ in range(9):
        _attach_review_tag(org_a, tag_a, polarity="positive")

    # org_b: tag that should NOT flip (no matching reviews)
    tag_b = _make_always_positive_tag(org_b, label="service")
    for _ in range(10):
        _attach_review_tag(org_b, tag_b, polarity="positive")

    run_polarity_reclassification()

    tag_a.refresh_from_db()
    tag_b.refresh_from_db()

    assert tag_a.polarity_type == OrgCanonicalTag.PolarityType.MIXED, "org_a tag should flip"
    assert tag_b.polarity_type == OrgCanonicalTag.PolarityType.ALWAYS_POSITIVE, (
        "org_b tag must not be affected by org_a's reviews"
    )
    assert (
        AuditLog.objects.filter(action="polarity_reclassified", organisation=org_b).count() == 0
    ), "no audit log written for org_b"


# ---------------------------------------------------------------------------
# (i) idempotency — second run writes nothing extra (D-05)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_idempotency_second_run_changes_nothing() -> None:
    """Running reclassification twice produces the same result and same log count (D-05)."""
    org = OrganisationFactory()
    tag = _make_always_positive_tag(org)

    for _ in range(2):
        _attach_review_tag(org, tag, polarity="negative")
    for _ in range(9):
        _attach_review_tag(org, tag, polarity="positive")

    run_polarity_reclassification()
    audit_count_after_first = AuditLog.objects.filter(action="polarity_reclassified").count()

    run_polarity_reclassification()
    audit_count_after_second = AuditLog.objects.filter(action="polarity_reclassified").count()

    tag.refresh_from_db()
    assert tag.polarity_type == OrgCanonicalTag.PolarityType.MIXED
    assert audit_count_after_second == audit_count_after_first, (
        "second run must not produce additional AuditLog rows"
    )


# ---------------------------------------------------------------------------
# (j) no-N+1 query count fixed regardless of tag count (CLAUDE.md §6.9)
# ---------------------------------------------------------------------------


def _query_count_for_n_always_positive_tags(n: int) -> int:
    """Helper: create n always_positive tags with qualifying data, return query count."""
    org = OrganisationFactory()
    for i in range(n):
        tag = OrgCanonicalTagFactory(
            organisation=org,
            polarity_type=OrgCanonicalTag.PolarityType.ALWAYS_POSITIVE,
            label=f"tag-{i}",
        )
        # Ensure threshold is met: 2 negative + 9 positive = 11 reviews, ratio ≈ 0.18
        for _ in range(2):
            _attach_review_tag(org, tag, polarity="negative")
        for _ in range(9):
            _attach_review_tag(org, tag, polarity="positive")

    with CaptureQueriesContext(connection) as ctx:
        run_polarity_reclassification()
    return len(ctx.captured_queries)


@pytest.mark.django_db
def test_query_count_is_fixed_regardless_of_tag_count() -> None:
    """Service executes a fixed number of DB queries regardless of tag volume (§6.9)."""
    count_for_two = _query_count_for_n_always_positive_tags(2)
    count_for_five = _query_count_for_n_always_positive_tags(5)

    assert count_for_two == count_for_five, (
        f"Query count grew from {count_for_two} (2 tags) to {count_for_five} (5 tags) — N+1"
    )
    assert count_for_five <= 10, f"Expected <= 10 queries but got {count_for_five}"


# ---------------------------------------------------------------------------
# (k) POL-03 AuditLog row written per flip with correct fields (D-06)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_audit_log_written_on_flip() -> None:
    """Each reclassification writes one AuditLog row with the mandated fields (D-06)."""
    org = OrganisationFactory()
    tag = _make_always_positive_tag(org)

    # 2 negative / 9 positive = 11 total; ratio ≈ 0.18 > 0.15
    for _ in range(2):
        _attach_review_tag(org, tag, polarity="negative")
    for _ in range(9):
        _attach_review_tag(org, tag, polarity="positive")

    run_polarity_reclassification()

    log = AuditLog.objects.get(
        action="polarity_reclassified",
        entity_type="canonical_tag",
        entity_id=str(tag.pk),
    )
    assert log.organisation_id == org.pk
    assert log.actor is None, "system event must have null actor (D-06)"
    assert log.before_data == {"polarity_type": "always_positive"}
    assert log.after_data["polarity_type"] == "mixed"
    assert "opposite_ratio" in log.after_data
    assert "window_days" in log.after_data
    assert "reviews_in_window" in log.after_data
    assert log.after_data["opposite_ratio"] > 0.15
    assert log.after_data["window_days"] == 30
    assert log.after_data["reviews_in_window"] == 11


# ---------------------------------------------------------------------------
# POL-01 re-confirmation: polarity_type is assigned at creation (Phase 22)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_pol01_reconfirm_new_tag_has_non_empty_polarity_type() -> None:
    """POL-01 re-confirmation: a freshly created OrgCanonicalTag has a non-empty
    polarity_type drawn from PolarityType.values.

    This is a regression guard only — Phase 22 owns the prompt/parser that
    sets polarity_type. This phase does NOT re-implement that logic.
    No import of apps.integrations.openai is needed or permitted here.
    """
    org = OrganisationFactory()
    tag = OrgCanonicalTagFactory(
        organisation=org,
        polarity_type=OrgCanonicalTag.PolarityType.ALWAYS_POSITIVE,
    )
    tag.refresh_from_db()

    assert tag.polarity_type in OrgCanonicalTag.PolarityType.values, (
        f"polarity_type '{tag.polarity_type}' is not in PolarityType.values"
    )
    assert tag.polarity_type != "", "polarity_type must not be empty"
