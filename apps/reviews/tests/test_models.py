"""Phase 11 — Review and AuditLog model constraint tests."""

from __future__ import annotations

import pytest
from django.db import IntegrityError
from django.utils import timezone

from apps.common.models import AuditLog
from apps.reviews.models import Review, ReviewTag
from apps.reviews.tests.factories import (
    AuditLogFactory,
    ReviewFactory,
    ReviewTagFactory,
)
from apps.shops.tests.factories import ShopFactory

pytestmark = pytest.mark.django_db


def test_review_unique_per_shop_constraint() -> None:
    shop = ShopFactory()
    ReviewFactory(shop=shop, organisation=shop.organisation, google_review_id="dup-1")
    with pytest.raises(IntegrityError):
        ReviewFactory(shop=shop, organisation=shop.organisation, google_review_id="dup-1")


def test_review_default_enrichment_status_is_pending() -> None:
    r = ReviewFactory()
    assert r.enrichment_status == Review.EnrichmentStatus.PENDING


def test_review_active_excludes_soft_deleted() -> None:
    r1 = ReviewFactory()
    r2 = ReviewFactory(deleted_at=timezone.now())
    active_ids = list(Review.objects.active().values_list("id", flat=True))
    assert r1.pk in active_ids
    assert r2.pk not in active_ids


def test_review_for_organisation_filters_by_org() -> None:
    r1 = ReviewFactory()
    r2 = ReviewFactory()
    assert r2.organisation_id != r1.organisation_id  # sanity
    qs = Review.objects.for_organisation(r1.organisation_id)
    assert r1 in qs
    assert r2 not in qs


def test_audit_log_can_be_created() -> None:
    log = AuditLogFactory(entity_type="review", action="reply_posted")
    fetched = AuditLog.objects.get(pk=log.pk)
    assert fetched.entity_type == "review"
    assert fetched.action == "reply_posted"
    assert fetched.after_data == {"reply_text": "ok"}


def test_review_str_representation() -> None:
    r = ReviewFactory(star_rating=4)
    assert "stars=4" in str(r)


def test_review_meta_indexes() -> None:
    """TECH-03: three new composite indexes for dashboard query plans must exist."""
    index_names = {idx.name for idx in Review._meta.indexes}
    assert "review_org_time_sent_idx" in index_names
    assert "review_shop_time_idx" in index_names
    assert "review_org_time_status_idx" in index_names


class TestReviewTagModel:
    """Phase 17 — ReviewTag relational model tests."""

    def test_str_representation(self) -> None:
        review = ReviewFactory()
        tag = ReviewTagFactory(review=review, label="Service", polarity="positive")
        assert str(tag) == f"ReviewTag({review.pk}, Service, positive)"

    def test_db_table_name(self) -> None:
        assert ReviewTag._meta.db_table == "reviews_reviewtag"

    def test_composite_index_exists(self) -> None:
        index_names = {idx.name for idx in ReviewTag._meta.indexes}
        assert "reviewtag_review_label_idx" in index_names
        idx = next(i for i in ReviewTag._meta.indexes if i.name == "reviewtag_review_label_idx")
        assert idx.fields == ["review", "label"]

    def test_label_field_is_indexed(self) -> None:
        label_field = ReviewTag._meta.get_field("label")
        assert label_field.db_index is True

    def test_polarity_choices(self) -> None:
        assert ReviewTag.Polarity.POSITIVE == "positive"
        assert ReviewTag.Polarity.NEUTRAL == "neutral"
        assert ReviewTag.Polarity.NEGATIVE == "negative"

    def test_cascade_delete_when_review_deleted(self) -> None:
        review = ReviewFactory()
        ReviewTagFactory(review=review)
        ReviewTagFactory(review=review)
        assert ReviewTag.objects.filter(review=review).count() == 2
        review.delete()
        assert ReviewTag.objects.count() == 0

    def test_review_tags_related_manager(self) -> None:
        """related_name='tags' exposes a RelatedManager on Review instances."""
        review = ReviewFactory()
        ReviewTagFactory(review=review, label="A", polarity="positive")
        ReviewTagFactory(review=review, label="B", polarity="negative")
        labels = set(review.tags.values_list("label", flat=True))
        assert labels == {"A", "B"}
