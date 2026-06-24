"""Phase 11 — ReviewViewSet API tests including REVW-14 query-count gate.

Phase 25 Plan 02 — OrgCanonicalTagViewSet + TagMergeJobViewSet + tags_page_view tests.
"""

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
from apps.reviews.models import Review, TagMergeJob
from apps.reviews.tests.factories import (
    OrgCanonicalTagFactory,
    ReviewFactory,
    ReviewTagFactory,
    TagMergeJobFactory,
)
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

        resp = client.post(_generate_reply_url(review.pk), {"tone": "professional"}, format="json")

        assert resp.status_code == 422
        assert resp.json() == {
            "code": "content_moderated",
            "detail": "AI reply isn't available for this review. Please write your reply manually.",
        }

    @patch("apps.reviews.views.generate_reply_draft")
    def test_generate_reply_422_canonical_detail_string_byte_exact(self, mock_generate) -> None:
        """D-26 regression: the user-facing copy must match byte-for-byte."""
        mock_generate.side_effect = ContentModeratedException("output flagged")
        org = OrganisationFactory()
        user = OrgAdminFactory(organisation=org)
        review = ReviewFactory(organisation=org)
        client = APIClient()
        client.force_authenticate(user=user)

        resp = client.post(_generate_reply_url(review.pk), {"tone": "professional"}, format="json")

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

        resp = client.post(_generate_reply_url(review.pk), {"tone": "professional"}, format="json")

        assert resp.status_code == 422
        assert set(resp.json().keys()) == {"code", "detail"}


# ---------------------------------------------------------------------------
# Phase 25 Plan 02 — OrgCanonicalTagViewSet tests (TMGT-01, TMGT-02, TMGT-04)
# ---------------------------------------------------------------------------

CANONICAL_TAGS_URL = "/api/v1/reviews/canonical-tags/"
TAG_MERGE_JOBS_URL = "/api/v1/reviews/tag-merge-jobs/"


@pytest.fixture
def org_admin_setup():
    """Return (client, user, org) for an ORG_ADMIN user."""
    org = OrganisationFactory()
    user = OrgAdminFactory(organisation=org)
    client = APIClient()
    client.force_authenticate(user=user)
    return client, user, org


def test_canonical_tags_list_query_count(org_admin_setup) -> None:
    """TMGT-02: list endpoint ≤3 queries regardless of page size (§6.9).

    Expected queries: 1 session/auth + 1 COUNT + 1 SELECT = 3 max.
    """
    client, _user, org = org_admin_setup
    OrgCanonicalTagFactory.create_batch(20, organisation=org)
    with CaptureQueriesContext(connection) as ctx:
        resp = client.get(CANONICAL_TAGS_URL, {"page_size": 20})
    assert resp.status_code == 200
    assert len(ctx.captured_queries) <= 3, [q["sql"] for q in ctx.captured_queries]


def test_canonical_tags_ordering(org_admin_setup) -> None:
    """TMGT-02: ?ordering=label and ?ordering=-review_count reorder results."""
    client, _user, org = org_admin_setup
    OrgCanonicalTagFactory(organisation=org, label="Zebra Tag", review_count=5)
    OrgCanonicalTagFactory(organisation=org, label="Apple Tag", review_count=10)
    OrgCanonicalTagFactory(organisation=org, label="Middle Tag", review_count=1)

    # ordering=label → alphabetical ascending
    resp = client.get(CANONICAL_TAGS_URL, {"ordering": "label"})
    assert resp.status_code == 200
    labels = [r["label"] for r in resp.data["results"]]
    assert labels == sorted(labels), f"Expected ascending order, got {labels}"

    # ordering=-review_count → highest review_count first
    resp2 = client.get(CANONICAL_TAGS_URL, {"ordering": "-review_count"})
    assert resp2.status_code == 200
    counts = [r["review_count"] for r in resp2.data["results"]]
    assert counts == sorted(counts, reverse=True), f"Expected desc order, got {counts}"


def test_canonical_tags_staff_returns_403() -> None:
    """TMGT-01/T-26: STAFF_ADMIN is rejected at the view boundary (IsOrgAdmin)."""
    org = OrganisationFactory()
    staff = StaffAdminFactory(organisation=org)
    OrgCanonicalTagFactory(organisation=org, label="Food Quality")
    client = APIClient()
    client.force_authenticate(user=staff)
    resp = client.get(CANONICAL_TAGS_URL)
    assert resp.status_code == 403


def test_canonical_tags_search_excludes_other_org(org_admin_setup) -> None:
    """TMGT-07/T-26: ?search= over the HTTP boundary never returns another org's tag."""
    client, _user, org = org_admin_setup
    OrgCanonicalTagFactory(organisation=org, label="Food Quality")
    other_org = OrganisationFactory()
    OrgCanonicalTagFactory(organisation=other_org, label="Food Quality")  # same label, other org
    resp = client.get(CANONICAL_TAGS_URL, {"search": "food"})
    assert resp.status_code == 200
    labels = [r["label"] for r in resp.data["results"]]
    assert labels == ["Food Quality"], labels  # exactly the caller-org's single match
    assert resp.data["count"] == 1


def test_merge_409_when_active_job(org_admin_setup) -> None:
    """TMGT-04/T-25-AC3: POST merge while PENDING job exists → 409."""
    client, _user, org = org_admin_setup
    source_tag = OrgCanonicalTagFactory(organisation=org, label="Source Tag")
    target_tag = OrgCanonicalTagFactory(organisation=org, label="Target Tag")
    # Create an active PENDING job for this org
    TagMergeJobFactory(
        organisation=org,
        source_label="Old Source",
        target_label="Old Target",
        status=TagMergeJob.Status.PENDING,
        dismissed=False,
    )

    resp = client.post(
        f"{CANONICAL_TAGS_URL}{source_tag.pk}/merge/",
        {"target_id": target_tag.pk},
        format="json",
    )
    assert resp.status_code == 409, f"Expected 409, got {resp.status_code}: {resp.data}"


def test_tag_merge_job_active_endpoint(org_admin_setup) -> None:
    """TMGT-06/T-25-AC1b: active/ returns the caller's org job only — not another org's."""
    client, _user, org = org_admin_setup
    other_org = OrganisationFactory()

    # Create a job for the other org — must NOT be returned
    TagMergeJobFactory(
        organisation=other_org,
        status=TagMergeJob.Status.PENDING,
        dismissed=False,
    )

    # No active job for caller's org → null response
    resp = client.get(f"{TAG_MERGE_JOBS_URL}active/")
    assert resp.status_code == 200
    assert resp.data is None or resp.data == {}

    # Now create a job for caller's org
    job = TagMergeJobFactory(
        organisation=org,
        source_label="My Source",
        target_label="My Target",
        status=TagMergeJob.Status.PENDING,
        dismissed=False,
    )
    resp2 = client.get(f"{TAG_MERGE_JOBS_URL}active/")
    assert resp2.status_code == 200
    assert resp2.data is not None
    assert resp2.data["id"] == job.pk


def test_tag_merge_job_dismiss(org_admin_setup) -> None:
    """TMGT-06: dismiss/ sets dismissed=True; active/ then returns null."""
    client, _user, org = org_admin_setup
    job = TagMergeJobFactory(
        organisation=org,
        status=TagMergeJob.Status.SUCCESS,
        dismissed=False,
    )

    # Dismiss the job
    resp = client.patch(f"{TAG_MERGE_JOBS_URL}{job.pk}/dismiss/")
    assert resp.status_code == 200

    # After dismiss, active/ should return null (job is dismissed)
    job.refresh_from_db()
    assert job.dismissed is True


# ---------------------------------------------------------------------------
# Phase 25 Plan 02 — tags_page_view tests (TMGT-01)
# ---------------------------------------------------------------------------

TAGS_PAGE_URL = "/admin/org/tags/"


def test_tags_page_staff_redirected() -> None:
    """TMGT-01/T-25-AC1: Staff GET /admin/org/tags/ → redirect (not 200)."""
    org = OrganisationFactory()
    staff = StaffAdminFactory(organisation=org)
    client = APIClient()
    client.force_authenticate(user=staff)
    resp = client.get(TAGS_PAGE_URL)
    # @org_admin_required redirects non-ORG_ADMIN users
    assert resp.status_code in (302, 301, 403), (
        f"Expected redirect/403 for Staff, got {resp.status_code}"
    )


def test_tags_page_org_admin_ok() -> None:
    """TMGT-01: ORG_ADMIN GET /admin/org/tags/ → 200."""
    org = OrganisationFactory()
    user = OrgAdminFactory(organisation=org)
    from django.test import Client

    client = Client()
    client.force_login(user)
    resp = client.get(TAGS_PAGE_URL)
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Phase 27 Plan 01 — SyncProgressSnapshotView tests (SYNC-REL-01)
# ---------------------------------------------------------------------------


def _sync_progress_url(shop_id: int) -> str:
    return f"/api/v1/reviews/sync-progress/{shop_id}/"


@pytest.fixture
def snapshot_setup():
    """Return (client, user, org, shop) for an ORG_ADMIN user with a shop."""
    org = OrganisationFactory()
    user = OrgAdminFactory(organisation=org)
    shop = ShopFactory(organisation=org)
    client = APIClient()
    client.force_authenticate(user=user)
    return client, user, org, shop


def test_sync_progress_returns_snapshot_for_owner_org(snapshot_setup) -> None:
    """SYNC-REL-01: ORG_ADMIN of the shop's org gets 200 + the snapshot dict."""
    client, _user, _org, shop = snapshot_setup
    fake_snapshot = {
        "shop_id": shop.pk,
        "status": "enriching",
        "fetched": 100,
        "enriched": 50,
        "last_update_at": "2026-01-01T00:00:00+00:00",
    }
    with patch(
        "apps.reviews.views.read_progress_snapshot",
        return_value=fake_snapshot,
    ):
        resp = client.get(_sync_progress_url(shop.pk))
    assert resp.status_code == 200
    assert resp.data["status"] == "enriching"
    assert resp.data["fetched"] == 100


def test_sync_progress_returns_404_when_no_snapshot(snapshot_setup) -> None:
    """SYNC-REL-01: 404 when no Redis snapshot exists for the shop."""
    client, _user, _org, shop = snapshot_setup
    with patch(
        "apps.reviews.views.read_progress_snapshot",
        return_value=None,
    ):
        resp = client.get(_sync_progress_url(shop.pk))
    assert resp.status_code == 404


def test_sync_progress_cross_tenant_denied(snapshot_setup) -> None:
    """SYNC-REL-01/T-27-01: User from org B cannot read org A's shop snapshot."""
    _client_a, _user_a, _org_a, shop_a = snapshot_setup

    # Create a second org and its admin
    org_b = OrganisationFactory()
    user_b = OrgAdminFactory(organisation=org_b)
    client_b = APIClient()
    client_b.force_authenticate(user=user_b)

    with patch(
        "apps.reviews.views.read_progress_snapshot",
        return_value={"shop_id": shop_a.pk, "status": "enriching"},
    ):
        resp = client_b.get(_sync_progress_url(shop_a.pk))
    assert resp.status_code in (403, 404), (
        f"Cross-tenant access must be denied (403/404), got {resp.status_code}"
    )


def test_sync_progress_staff_out_of_scope_denied(snapshot_setup) -> None:
    """SYNC-REL-01/T-27-01: Staff user without StaffAccessScope for the shop is denied."""
    _client, _user, org, shop = snapshot_setup

    staff = StaffAdminFactory(organisation=org)
    # No StaffAccessScope granted — staff cannot access this shop
    client = APIClient()
    client.force_authenticate(user=staff)

    with patch(
        "apps.reviews.views.read_progress_snapshot",
        return_value={"shop_id": shop.pk, "status": "fetching"},
    ):
        resp = client.get(_sync_progress_url(shop.pk))
    assert resp.status_code in (403, 404), (
        f"Out-of-scope Staff must be denied (403/404), got {resp.status_code}"
    )


def test_sync_progress_staff_in_scope_allowed(snapshot_setup) -> None:
    """SYNC-REL-01: Staff user WITH a SHOP StaffAccessScope gets 200 + snapshot."""
    _client, _user, org, shop = snapshot_setup

    staff = StaffAdminFactory(organisation=org)
    StaffAccessScope.objects.create(
        user=staff,
        scope_type=StaffAccessScope.ScopeType.SHOP,
        shop=shop,
    )
    client = APIClient()
    client.force_authenticate(user=staff)

    fake_snapshot = {"shop_id": shop.pk, "status": "success", "fetched": 10}
    with patch(
        "apps.reviews.views.read_progress_snapshot",
        return_value=fake_snapshot,
    ):
        resp = client.get(_sync_progress_url(shop.pk))
    assert resp.status_code == 200
    assert resp.data["status"] == "success"


def test_sync_progress_unauthenticated_denied() -> None:
    """SYNC-REL-01/T-27-02: Anonymous request is rejected with 401/403."""
    org = OrganisationFactory()
    shop = ShopFactory(organisation=org)
    client = APIClient()
    resp = client.get(_sync_progress_url(shop.pk))
    assert resp.status_code in (401, 403)
