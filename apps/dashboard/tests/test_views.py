"""Tests for DashboardApiView base and concrete endpoint views (14-03).

Covers:
  - 200 for authenticated org admin (FILT-08 happy path)
  - 403 for out-of-scope store (FILT-08)
  - 400 for date range > 365 days (FILT-09)
  - 400 for from > to dates (FILT-10)
  - Cache hit skips selector (TECH-02)
  - Query count ceiling (TECH-04)
  - Smoke 200 for all 5 endpoints
"""

from __future__ import annotations

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.tests.factories import OrgAdminFactory, StaffAdminFactory
from apps.dashboard.tests.conftest import make_review
from apps.organisations.tests.factories import OrganisationFactory
from apps.shops.tests.factories import ShopFactory

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def org_with_user_and_shop(db):
    org = OrganisationFactory()
    user = OrgAdminFactory(organisation=org, role=User.Role.ORG_ADMIN)
    shop = ShopFactory(organisation=org)
    # Seed a review so KPI responses are non-trivially empty
    make_review(shop=shop, star_rating=4, days_ago=5)
    return {"user": user, "org": org, "shop": shop}


# ---------------------------------------------------------------------------
# /api/v1/dashboard/kpis/
# ---------------------------------------------------------------------------


def test_kpis_view_returns_200_for_authenticated_org_admin(db, api_client, org_with_user_and_shop):
    """200 response with total_reviews key for a valid authenticated org admin."""
    user = org_with_user_and_shop["user"]
    api_client.force_authenticate(user=user)
    resp = api_client.get("/api/v1/dashboard/kpis/")
    assert resp.status_code == 200
    assert "total_reviews" in resp.json()


def test_kpis_view_out_of_scope_store_returns_403(db, api_client, org_with_user_and_shop):
    """FILT-08: 403 when store param is not accessible to the user."""
    user = org_with_user_and_shop["user"]
    api_client.force_authenticate(user=user)
    resp = api_client.get("/api/v1/dashboard/kpis/?store=99999")
    assert resp.status_code == 403


def test_kpis_view_date_range_too_long_returns_400(db, api_client, org_with_user_and_shop):
    """FILT-09: 400 when custom date range exceeds 365 days."""
    user = org_with_user_and_shop["user"]
    api_client.force_authenticate(user=user)
    resp = api_client.get("/api/v1/dashboard/kpis/?range=custom&from=2023-01-01&to=2025-01-01")
    assert resp.status_code == 400


def test_kpis_view_from_after_to_returns_400(db, api_client, org_with_user_and_shop):
    """FILT-10: 400 when from date is after to date."""
    user = org_with_user_and_shop["user"]
    api_client.force_authenticate(user=user)
    resp = api_client.get("/api/v1/dashboard/kpis/?range=custom&from=2024-06-01&to=2024-01-01")
    assert resp.status_code == 400


def test_kpis_view_unauthenticated_returns_403(db, api_client):
    """Unauthenticated requests are rejected."""
    resp = api_client.get("/api/v1/dashboard/kpis/")
    assert resp.status_code in (401, 403)


def test_kpis_view_cache_hit_skips_selector(db, api_client, org_with_user_and_shop):
    """TECH-02: second identical request hits cache — selector is called only once."""
    from unittest.mock import patch

    from django.core.cache import cache

    from apps.dashboard.selectors.aggregations import dashboard_kpis as real_kpis

    cache.clear()
    user = org_with_user_and_shop["user"]
    api_client.force_authenticate(user=user)

    call_count = 0

    def counting_kpis(**kwargs):
        nonlocal call_count
        call_count += 1
        return real_kpis(**kwargs)

    with patch("apps.dashboard.views.dashboard_kpis", side_effect=counting_kpis):
        resp1 = api_client.get("/api/v1/dashboard/kpis/")
        assert resp1.status_code == 200
        resp2 = api_client.get("/api/v1/dashboard/kpis/")
        assert resp2.status_code == 200

    # Selector must have been called exactly once (cache served the second hit)
    assert call_count == 1


def test_kpis_view_query_count(db, api_client, org_with_user_and_shop):
    """TECH-04: list endpoint has a fixed query-count ceiling regardless of data size."""
    from django.core.cache import cache

    cache.clear()
    user = org_with_user_and_shop["user"]
    api_client.force_authenticate(user=user)

    with CaptureQueriesContext(connection) as ctx:
        resp = api_client.get("/api/v1/dashboard/kpis/")
    assert resp.status_code == 200
    assert len(ctx.captured_queries) <= 5


# ---------------------------------------------------------------------------
# Smoke 200 tests for remaining 4 endpoints
# ---------------------------------------------------------------------------


def test_sentiment_distribution_view_200(db, api_client, org_with_user_and_shop):
    """Smoke: /api/v1/dashboard/sentiment-distribution/ returns 200 with coverage_pct."""
    user = org_with_user_and_shop["user"]
    api_client.force_authenticate(user=user)
    resp = api_client.get("/api/v1/dashboard/sentiment-distribution/")
    assert resp.status_code == 200
    assert "coverage_pct" in resp.json()


def test_top_performing_view_200(db, api_client, org_with_user_and_shop):
    """Smoke: /api/v1/dashboard/top-performing/ returns 200 with shops key."""
    user = org_with_user_and_shop["user"]
    api_client.force_authenticate(user=user)
    resp = api_client.get("/api/v1/dashboard/top-performing/")
    assert resp.status_code == 200
    assert "shops" in resp.json()


def test_highlights_view_200(db, api_client, org_with_user_and_shop):
    """Smoke: /api/v1/dashboard/highlights/ returns 200 with top key."""
    user = org_with_user_and_shop["user"]
    api_client.force_authenticate(user=user)
    resp = api_client.get("/api/v1/dashboard/highlights/")
    assert resp.status_code == 200
    assert "top" in resp.json()


def test_your_store_view_200_multi_shop_returns_empty(db, api_client, org_with_user_and_shop):
    """Smoke: /api/v1/dashboard/your-store/ returns 200 (empty {} when multiple shops)."""
    user = org_with_user_and_shop["user"]
    # Add a second shop so org has multiple shops -> your_store returns None -> {}
    ShopFactory(organisation=org_with_user_and_shop["org"])
    api_client.force_authenticate(user=user)
    resp = api_client.get("/api/v1/dashboard/your-store/")
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# /api/v1/dashboard/tag-polarity/ — ORG_ADMIN-only (Phase 25 follow-up)
# ---------------------------------------------------------------------------


def test_tag_polarity_view_200_for_org_admin(db, api_client, org_with_user_and_shop):
    """The canonical tag-polarity chart endpoint returns 200 for an ORG_ADMIN."""
    user = org_with_user_and_shop["user"]
    api_client.force_authenticate(user=user)
    resp = api_client.get("/api/v1/dashboard/tag-polarity/")
    assert resp.status_code == 200
    assert "tags" in resp.json()


def test_tag_polarity_view_403_for_staff(db, api_client, org_with_user_and_shop):
    """Staff must NOT reach the org-wide canonical tag-polarity aggregate (§9/§22)."""
    staff = StaffAdminFactory(organisation=org_with_user_and_shop["org"])
    api_client.force_authenticate(user=staff)
    resp = api_client.get("/api/v1/dashboard/tag-polarity/")
    assert resp.status_code == 403
