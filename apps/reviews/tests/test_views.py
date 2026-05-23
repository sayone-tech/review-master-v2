"""Phase 11 — ReviewViewSet API tests including REVW-14 query-count gate."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import StaffAccessScope
from apps.accounts.tests.factories import OrgAdminFactory, StaffAdminFactory
from apps.integrations.openai.exceptions import (
    ContentModeratedException,
    OpenAIPermanentError,
    OpenAITransientError,
)
from apps.organisations.tests.factories import OrganisationFactory
from apps.reviews.models import Review
from apps.reviews.tests.factories import ReviewFactory, ReviewTagFactory
from apps.shops.tests.factories import ShopFactory

pytestmark = pytest.mark.django_db

LIST_URL = "/api/v1/reviews/"
TAGS_URL = "/api/v1/reviews/tags/"
STATS_URL = "/api/v1/reviews/stats/"


@pytest.fixture
def org_admin_client():
    org = OrganisationFactory()
    user = OrgAdminFactory(organisation=org)
    client = APIClient()
    client.force_authenticate(user=user)
    return client, user, org


def test_list_reviews_accessible_to_org_admin(org_admin_client) -> None:
    client, _, org = org_admin_client
    ReviewFactory.create_batch(3, organisation=org)
    resp = client.get(LIST_URL)
    assert resp.status_code == 200
    assert "results" in resp.data
    assert resp.data["total_count"] == 3


def test_list_reviews_filters_by_rating(org_admin_client) -> None:
    client, _, org = org_admin_client
    ReviewFactory.create_batch(2, organisation=org, star_rating=5)
    ReviewFactory.create_batch(3, organisation=org, star_rating=3)
    resp = client.get(LIST_URL, {"rating": 5})
    assert resp.status_code == 200
    assert resp.data["total_count"] == 2


def test_list_reviews_filters_by_shop_and_is_replied(org_admin_client) -> None:
    client, _, org = org_admin_client
    s1 = ShopFactory(organisation=org)
    s2 = ShopFactory(organisation=org)
    ReviewFactory(organisation=org, shop=s1, is_replied=True)
    ReviewFactory(organisation=org, shop=s1, is_replied=False)
    ReviewFactory(organisation=org, shop=s2, is_replied=True)
    resp = client.get(LIST_URL, {"shop": s1.pk, "is_replied": "true"})
    assert resp.status_code == 200
    assert resp.data["total_count"] == 1


def test_list_reviews_filters_by_date_range(org_admin_client) -> None:
    client, _, org = org_admin_client
    now = timezone.now()
    ReviewFactory(organisation=org, review_create_time=now - timedelta(days=10))
    ReviewFactory(organisation=org, review_create_time=now - timedelta(days=2))
    resp = client.get(
        LIST_URL,
        {
            "from_date": (now - timedelta(days=5)).date().isoformat(),
            "to_date": now.date().isoformat(),
        },
    )
    assert resp.status_code == 200
    assert resp.data["total_count"] == 1


def test_list_reviews_default_ordering_newest_first(org_admin_client) -> None:
    client, _, org = org_admin_client
    older = ReviewFactory(organisation=org, review_create_time=timezone.now() - timedelta(days=5))
    newer = ReviewFactory(organisation=org, review_create_time=timezone.now())
    resp = client.get(LIST_URL)
    assert resp.status_code == 200
    ids = [r["id"] for r in resp.data["results"]]
    assert ids == [newer.pk, older.pk]


def test_list_reviews_page_size_param(org_admin_client) -> None:
    client, _, org = org_admin_client
    ReviewFactory.create_batch(8, organisation=org)
    resp = client.get(LIST_URL, {"page_size": 3})
    assert resp.status_code == 200
    assert len(resp.data["results"]) == 3
    assert resp.data["total_count"] == 8


def test_staff_user_sees_only_accessible_shops_reviews() -> None:
    org = OrganisationFactory()
    s1 = ShopFactory(organisation=org)
    s2 = ShopFactory(organisation=org)
    ReviewFactory.create_batch(2, organisation=org, shop=s1)
    ReviewFactory.create_batch(2, organisation=org, shop=s2)
    staff = StaffAdminFactory(organisation=org)
    StaffAccessScope.objects.create(user=staff, scope_type=StaffAccessScope.ScopeType.SHOP, shop=s1)
    client = APIClient()
    client.force_authenticate(user=staff)
    resp = client.get(LIST_URL)
    assert resp.status_code == 200
    assert resp.data["total_count"] == 2


def test_reviews_list_query_count_org_admin(org_admin_client) -> None:
    """REVW-14: <=5 SQL queries regardless of page size."""
    client, _, org = org_admin_client
    ReviewFactory.create_batch(50, organisation=org)
    with CaptureQueriesContext(connection) as ctx:
        resp = client.get(LIST_URL, {"page_size": 25})
    assert resp.status_code == 200
    assert len(resp.data["results"]) == 25
    assert len(ctx.captured_queries) <= 5, [q["sql"] for q in ctx.captured_queries]


def test_review_list_tags_shape(org_admin_client) -> None:
    """Phase 17 (TAG-02): tags in list response are [{label, polarity}] objects.

    Wave 0 shape-regression contract: ReviewTagSerializer(many=True) on the
    ReviewReadSerializer must return the same JSON shape the frontend already
    consumes from the old Review.tags JSONField — a list of dicts each with
    "label" and "polarity" keys (not the raw RelatedManager).
    """
    client, _, org = org_admin_client
    review = ReviewFactory(organisation=org)
    ReviewTagFactory(review=review, label="Cleanliness", polarity="positive")
    ReviewTagFactory(review=review, label="Long Wait", polarity="negative")

    resp = client.get(LIST_URL)
    assert resp.status_code == 200
    assert resp.data["total_count"] == 1
    first = resp.data["results"][0]
    assert "tags" in first
    assert isinstance(first["tags"], list)
    assert len(first["tags"]) == 2
    for tag in first["tags"]:
        assert set(tag.keys()) == {"label", "polarity"}
    labels = {t["label"] for t in first["tags"]}
    assert labels == {"Cleanliness", "Long Wait"}


def test_reviews_list_query_count_staff_admin() -> None:
    """REVW-14 + Staff scope: <=5 queries (allows the StaffAccessScope subquery)."""
    org = OrganisationFactory()
    s1 = ShopFactory(organisation=org)
    ReviewFactory.create_batch(40, organisation=org, shop=s1)
    staff = StaffAdminFactory(organisation=org)
    StaffAccessScope.objects.create(user=staff, scope_type=StaffAccessScope.ScopeType.SHOP, shop=s1)
    client = APIClient()
    client.force_authenticate(user=staff)
    with CaptureQueriesContext(connection) as ctx:
        resp = client.get(LIST_URL, {"page_size": 25})
    assert resp.status_code == 200
    assert len(ctx.captured_queries) <= 5, [q["sql"] for q in ctx.captured_queries]


# ---------------------------------------------------------------------------
# TAG-03: tags @action + ?tags= filter integration tests
# ---------------------------------------------------------------------------


def test_tags_action_returns_org_scoped_labels(org_admin_client) -> None:
    """GET /api/v1/reviews/tags/ returns [{label, count}] for the caller's org only."""
    client, _, org = org_admin_client
    r1 = ReviewFactory(organisation=org)
    r2 = ReviewFactory(organisation=org)
    ReviewTagFactory(review=r1, label="Cleanliness", polarity="positive")
    ReviewTagFactory(review=r2, label="Cleanliness", polarity="positive")
    ReviewTagFactory(review=r2, label="Wait Time", polarity="negative")
    resp = client.get(TAGS_URL)
    assert resp.status_code == 200
    data = resp.data
    assert isinstance(data, list)
    labels = {row["label"]: row["count"] for row in data}
    assert labels == {"Cleanliness": 2, "Wait Time": 1}
    # ordered by count desc
    assert data[0]["label"] == "Cleanliness"


def test_tags_action_shop_filter(org_admin_client) -> None:
    """?shop=<id> narrows tags to that shop only."""
    client, _, org = org_admin_client
    s1 = ShopFactory(organisation=org)
    s2 = ShopFactory(organisation=org)
    r1 = ReviewFactory(organisation=org, shop=s1)
    r2 = ReviewFactory(organisation=org, shop=s2)
    ReviewTagFactory(review=r1, label="Cleanliness", polarity="positive")
    ReviewTagFactory(review=r2, label="Wait Time", polarity="negative")
    resp = client.get(TAGS_URL, {"shop": s1.pk})
    assert resp.status_code == 200
    labels = {row["label"] for row in resp.data}
    assert labels == {"Cleanliness"}


def test_tags_action_staff_scoping() -> None:
    """Staff users see only tags from their accessible shops."""
    org = OrganisationFactory()
    s1 = ShopFactory(organisation=org)
    s2 = ShopFactory(organisation=org)
    r1 = ReviewFactory(organisation=org, shop=s1)
    r2 = ReviewFactory(organisation=org, shop=s2)
    ReviewTagFactory(review=r1, label="Cleanliness", polarity="positive")
    ReviewTagFactory(review=r2, label="Wait Time", polarity="negative")
    staff = StaffAdminFactory(organisation=org)
    StaffAccessScope.objects.create(user=staff, scope_type=StaffAccessScope.ScopeType.SHOP, shop=s1)
    client = APIClient()
    client.force_authenticate(user=staff)
    resp = client.get(TAGS_URL)
    assert resp.status_code == 200
    labels = {row["label"] for row in resp.data}
    assert labels == {"Cleanliness"}


def test_tags_action_staff_no_scope_empty() -> None:
    """Phase 17 WR-04: a Staff user with zero StaffAccessScope rows must see
    an empty tags list. Locks the contract so a future refactor that drops
    the shop_id__in=[] filter cannot silently leak all org tags to a
    no-scope Staff user.
    """
    org = OrganisationFactory()
    s1 = ShopFactory(organisation=org)
    r1 = ReviewFactory(organisation=org, shop=s1)
    ReviewTagFactory(review=r1, label="Cleanliness", polarity="positive")
    staff = StaffAdminFactory(organisation=org)
    # Intentionally no StaffAccessScope rows.
    client = APIClient()
    client.force_authenticate(user=staff)
    resp = client.get(TAGS_URL)
    assert resp.status_code == 200
    assert resp.data == []


def test_tags_action_invalid_shop_param_returns_400(org_admin_client) -> None:
    """Phase 17 WR-02: non-integer ?shop= must return 400, not 500."""
    client, _, _org = org_admin_client
    resp = client.get(TAGS_URL, {"shop": "abc"})
    assert resp.status_code == 400


def test_tags_action_cross_org_isolation() -> None:
    """User from Org B cannot see Org A's tags via the tags endpoint."""
    org_a = OrganisationFactory()
    org_b = OrganisationFactory()
    r_a = ReviewFactory(organisation=org_a)
    r_b = ReviewFactory(organisation=org_b)
    ReviewTagFactory(review=r_a, label="OrgA-Only", polarity="positive")
    ReviewTagFactory(review=r_b, label="OrgB-Only", polarity="negative")
    user_b = OrgAdminFactory(organisation=org_b)
    client = APIClient()
    client.force_authenticate(user=user_b)
    resp = client.get(TAGS_URL)
    assert resp.status_code == 200
    labels = {row["label"] for row in resp.data}
    assert labels == {"OrgB-Only"}
    assert "OrgA-Only" not in labels


def test_tags_action_empty_when_no_tags(org_admin_client) -> None:
    """GET /api/v1/reviews/tags/ returns [] when the org has no tags."""
    client, _, _org = org_admin_client
    resp = client.get(TAGS_URL)
    assert resp.status_code == 200
    assert resp.data == []


def test_review_filter_tags_and_semantics(org_admin_client) -> None:
    """?tags=A,B returns only reviews that have BOTH tags A AND B."""
    client, _, org = org_admin_client
    # Review 1 has both tags
    r1 = ReviewFactory(organisation=org)
    ReviewTagFactory(review=r1, label="Cleanliness", polarity="positive")
    ReviewTagFactory(review=r1, label="Wait Time", polarity="negative")
    # Review 2 has only one
    r2 = ReviewFactory(organisation=org)
    ReviewTagFactory(review=r2, label="Cleanliness", polarity="positive")
    # Review 3 has neither
    ReviewFactory(organisation=org)

    resp = client.get(LIST_URL, {"tags": "Cleanliness,Wait Time"})
    assert resp.status_code == 200
    assert resp.data["total_count"] == 1
    ids = [row["id"] for row in resp.data["results"]]
    assert ids == [r1.pk]


def test_review_filter_tags_single_label(org_admin_client) -> None:
    """?tags=Cleanliness returns only reviews with that tag (no duplicates)."""
    client, _, org = org_admin_client
    r1 = ReviewFactory(organisation=org)
    # Multiple tags on same review — ensure .distinct() prevents row multiplication
    ReviewTagFactory(review=r1, label="Cleanliness", polarity="positive")
    ReviewTagFactory(review=r1, label="Friendly", polarity="positive")
    r2 = ReviewFactory(organisation=org)
    ReviewTagFactory(review=r2, label="Other", polarity="negative")

    resp = client.get(LIST_URL, {"tags": "Cleanliness"})
    assert resp.status_code == 200
    assert resp.data["total_count"] == 1
    ids = [row["id"] for row in resp.data["results"]]
    assert ids == [r1.pk]


def test_review_filter_tags_excludes(org_admin_client) -> None:
    """?tags=Nonexistent returns empty results list."""
    client, _, org = org_admin_client
    r = ReviewFactory(organisation=org)
    ReviewTagFactory(review=r, label="Cleanliness", polarity="positive")
    resp = client.get(LIST_URL, {"tags": "Nonexistent"})
    assert resp.status_code == 200
    assert resp.data["total_count"] == 0
    assert resp.data["results"] == []


def test_stats_with_tag_filter(org_admin_client) -> None:
    """Stats endpoint with ?tags= filter returns correct counts (no double-count)."""
    client, _, org = org_admin_client
    r1 = ReviewFactory(organisation=org, star_rating=5)
    # Two tags on r1 — would inflate stats without .distinct()
    ReviewTagFactory(review=r1, label="Cleanliness", polarity="positive")
    ReviewTagFactory(review=r1, label="Friendly", polarity="positive")
    r2 = ReviewFactory(organisation=org, star_rating=3)
    ReviewTagFactory(review=r2, label="Cleanliness", polarity="positive")
    # r3 has no Cleanliness tag — excluded
    ReviewFactory(organisation=org, star_rating=1)

    resp = client.get(STATS_URL, {"tags": "Cleanliness"})
    assert resp.status_code == 200
    # Only r1 and r2 match; total_count must be 2 (not inflated to 3 by tag rows on r1)
    assert resp.data["total_count"] == 2


def test_stats_with_tag_filter_avg_rating_not_inflated(org_admin_client) -> None:
    """Phase 17 CR-01/WR-06 regression: Avg/Count aggregates must not be inflated
    by JOINs to ReviewTag when ?tags= is applied. r1 has three tag rows; the
    pre-fix JOIN-based filter caused Avg(star_rating) to weight r1 three times.
    With the Exists()-based filter, Avg must equal the true unweighted mean.
    """
    client, _, org = org_admin_client
    r1 = ReviewFactory(
        organisation=org,
        star_rating=5,
        sentiment="positive",
        enrichment_status=Review.EnrichmentStatus.SUCCESS,
    )
    # Three tag rows on r1 — would inflate Avg/Count by a factor of 3
    ReviewTagFactory(review=r1, label="Cleanliness", polarity="positive")
    ReviewTagFactory(review=r1, label="Friendly", polarity="positive")
    ReviewTagFactory(review=r1, label="Fast", polarity="positive")
    r2 = ReviewFactory(
        organisation=org,
        star_rating=1,
        sentiment="negative",
        enrichment_status=Review.EnrichmentStatus.SUCCESS,
    )
    ReviewTagFactory(review=r2, label="Cleanliness", polarity="positive")

    resp = client.get(STATS_URL, {"tags": "Cleanliness"})
    assert resp.status_code == 200
    assert resp.data["total_count"] == 2
    # True unweighted mean of {5, 1} is 3.0. With the buggy JOIN the average
    # would have been (5+5+5+1)/4 = 4.0.
    assert resp.data["avg_rating"] == 3.0
    # Both enriched, one positive → 50%. Buggy JOIN would have yielded 75%.
    assert resp.data["positive_sentiment_pct"] == 50


# ---------------------------------------------------------------------------
# Phase 19 Plan 02: TestGenerateReplyEndpoint
# ---------------------------------------------------------------------------


def _generate_reply_url(review_pk: int) -> str:
    return f"/api/v1/reviews/{review_pk}/generate-reply/"


class TestGenerateReplyEndpoint:
    """Phase 19 Plan 02: POST /api/v1/reviews/{id}/generate-reply/.

    Covers D-09 through D-13 and D-17/D-18.
    """

    @patch("apps.reviews.views.generate_reply_draft")
    def test_success_returns_draft(self, mock_generate) -> None:
        mock_generate.return_value = "Great reply!"
        org = OrganisationFactory()
        user = OrgAdminFactory(organisation=org)
        review = ReviewFactory(organisation=org)
        client = APIClient()
        client.force_authenticate(user=user)

        resp = client.post(_generate_reply_url(review.pk), {"tone": "professional"}, format="json")

        assert resp.status_code == 200
        assert resp.data == {"draft": "Great reply!"}
        mock_generate.assert_called_once()
        kwargs = mock_generate.call_args.kwargs
        assert kwargs["tone"] == "professional"
        assert kwargs["review"].pk == review.pk

    def test_invalid_tone_returns_400(self) -> None:
        org = OrganisationFactory()
        user = OrgAdminFactory(organisation=org)
        review = ReviewFactory(organisation=org)
        client = APIClient()
        client.force_authenticate(user=user)

        resp = client.post(_generate_reply_url(review.pk), {"tone": "formal"}, format="json")

        assert resp.status_code == 400

    def test_unauthenticated_returns_403(self) -> None:
        org = OrganisationFactory()
        review = ReviewFactory(organisation=org)
        client = APIClient()

        resp = client.post(_generate_reply_url(review.pk), {"tone": "professional"}, format="json")

        assert resp.status_code == 403

    @patch("apps.reviews.views.generate_reply_draft")
    def test_transient_error_returns_502(self, mock_generate) -> None:
        mock_generate.side_effect = OpenAITransientError("boom")
        org = OrganisationFactory()
        user = OrgAdminFactory(organisation=org)
        review = ReviewFactory(organisation=org)
        client = APIClient()
        client.force_authenticate(user=user)

        resp = client.post(_generate_reply_url(review.pk), {"tone": "professional"}, format="json")

        assert resp.status_code == 502
        assert resp.data["code"] == "ai_unavailable"
        assert "AI generation failed" in resp.data["detail"]

    @patch("apps.reviews.views.generate_reply_draft")
    def test_permanent_error_returns_502(self, mock_generate) -> None:
        mock_generate.side_effect = OpenAIPermanentError("nope")
        org = OrganisationFactory()
        user = OrgAdminFactory(organisation=org)
        review = ReviewFactory(organisation=org)
        client = APIClient()
        client.force_authenticate(user=user)

        resp = client.post(_generate_reply_url(review.pk), {"tone": "friendly"}, format="json")

        assert resp.status_code == 502
        assert resp.data["code"] == "ai_unavailable"
        assert "AI generation failed" in resp.data["detail"]

    @patch("apps.reviews.views.generate_reply_draft")
    def test_generic_exception_returns_502(self, mock_generate) -> None:
        mock_generate.side_effect = ValueError("unexpected")
        org = OrganisationFactory()
        user = OrgAdminFactory(organisation=org)
        review = ReviewFactory(organisation=org)
        client = APIClient()
        client.force_authenticate(user=user)

        resp = client.post(_generate_reply_url(review.pk), {"tone": "professional"}, format="json")

        assert resp.status_code == 502
        assert resp.data["code"] == "ai_unavailable"

    @patch("apps.reviews.views.generate_reply_draft")
    def test_staff_admin_accessible_shop(self, mock_generate) -> None:
        mock_generate.return_value = "Reply draft."
        org = OrganisationFactory()
        shop = ShopFactory(organisation=org)
        review = ReviewFactory(organisation=org, shop=shop)
        staff = StaffAdminFactory(organisation=org)
        StaffAccessScope.objects.create(
            user=staff, scope_type=StaffAccessScope.ScopeType.SHOP, shop=shop
        )
        client = APIClient()
        client.force_authenticate(user=staff)

        resp = client.post(_generate_reply_url(review.pk), {"tone": "professional"}, format="json")

        assert resp.status_code == 200
        assert resp.data == {"draft": "Reply draft."}

    @patch("apps.reviews.views.generate_reply_draft")
    def test_staff_admin_inaccessible_shop_returns_404(self, mock_generate) -> None:
        org = OrganisationFactory()
        s1 = ShopFactory(organisation=org)
        s2 = ShopFactory(organisation=org)
        review = ReviewFactory(organisation=org, shop=s2)
        staff = StaffAdminFactory(organisation=org)
        StaffAccessScope.objects.create(
            user=staff, scope_type=StaffAccessScope.ScopeType.SHOP, shop=s1
        )
        client = APIClient()
        client.force_authenticate(user=staff)

        resp = client.post(_generate_reply_url(review.pk), {"tone": "professional"}, format="json")

        assert resp.status_code == 404
        mock_generate.assert_not_called()

    @patch("apps.reviews.views.generate_reply_draft")
    def test_generate_reply_query_count(self, mock_generate) -> None:
        """N+1 guard: ≤4 queries on the generate_reply path.

        Verifies select_related("shop__organisation") so the service can read
        review.shop.organisation.name without an extra query.
        """
        # Clear throttle cache so an earlier-test bucket can't push this request
        # into 429 (Redis throttle cache survives the DB-transaction rollback).
        from django.core.cache import caches

        caches["throttle"].clear()
        mock_generate.return_value = "draft"
        org = OrganisationFactory()
        user = OrgAdminFactory(organisation=org)
        review = ReviewFactory(organisation=org)
        client = APIClient()
        client.force_authenticate(user=user)

        with CaptureQueriesContext(connection) as ctx:
            resp = client.post(
                _generate_reply_url(review.pk),
                {"tone": "professional"},
                format="json",
            )

        assert resp.status_code == 200
        assert len(ctx.captured_queries) <= 4, [q["sql"] for q in ctx.captured_queries]

    # ------------------------------------------------------------------
    # Plan 20-07: ContentModeratedException -> HTTP 422 with canonical body
    # ------------------------------------------------------------------

    @patch("apps.reviews.views.generate_reply_draft")
    def test_generate_reply_returns_422_on_content_moderated(self, mock_generate) -> None:
        """D-16/D-26/D-32: moderation block maps to HTTP 422 with canonical body."""
        mock_generate.side_effect = ContentModeratedException("input flagged")
        org = OrganisationFactory()
        user = OrgAdminFactory(organisation=org)
        review = ReviewFactory(organisation=org)
        client = APIClient()
        client.force_authenticate(user=user)

        resp = client.post(
            _generate_reply_url(review.pk), {"tone": "professional"}, format="json"
        )

        assert resp.status_code == 422
        assert resp.json() == {
            "code": "content_moderated",
            "detail": "AI reply isn't available for this review. Please write your reply manually.",
        }

    @patch("apps.reviews.views.generate_reply_draft")
    def test_generate_reply_422_canonical_detail_string_byte_exact(
        self, mock_generate
    ) -> None:
        """D-26 regression: the user-facing copy must match byte-for-byte."""
        mock_generate.side_effect = ContentModeratedException("output flagged")
        org = OrganisationFactory()
        user = OrgAdminFactory(organisation=org)
        review = ReviewFactory(organisation=org)
        client = APIClient()
        client.force_authenticate(user=user)

        resp = client.post(
            _generate_reply_url(review.pk), {"tone": "professional"}, format="json"
        )

        assert resp.status_code == 422
        assert (
            resp.json()["detail"]
            == "AI reply isn't available for this review. Please write your reply manually."
        )

    @patch("apps.reviews.views.generate_reply_draft")
    def test_generate_reply_422_does_not_leak_categories_or_review_text(
        self, mock_generate
    ) -> None:
        """T-20-LK: 422 body must contain only ``code`` and ``detail`` keys."""
        mock_generate.side_effect = ContentModeratedException("input flagged")
        org = OrganisationFactory()
        user = OrgAdminFactory(organisation=org)
        review = ReviewFactory(organisation=org)
        client = APIClient()
        client.force_authenticate(user=user)

        resp = client.post(
            _generate_reply_url(review.pk), {"tone": "professional"}, format="json"
        )

        assert resp.status_code == 422
        assert set(resp.json().keys()) == {"code", "detail"}
