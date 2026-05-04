"""Phase 11 — Review and AuditLog model constraint tests."""

from __future__ import annotations

import pytest
from django.db import IntegrityError
from django.utils import timezone

from apps.common.models import AuditLog
from apps.reviews.models import Review
from apps.reviews.tests.factories import AuditLogFactory, ReviewFactory
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
