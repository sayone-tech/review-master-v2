from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
from django.core.cache import cache
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.tests.factories import OrgAdminFactory, StaffAdminFactory, UserFactory
from apps.integrations.openai import cost_window
from apps.integrations.openai.models import AiUsageLog
from apps.integrations.openai.tests.factories import AiUsageLogFactory
from apps.integrations.openai.views import (
    AiCostOrganisationListView,
    AiCostOrgModelsView,
    AiCostOrgShopsView,
    AiCostOrgSummaryView,
    AiCostSummaryView,
)
from apps.organisations.tests.factories import OrganisationFactory
from apps.reviews.tests.factories import ReviewFactory
from apps.shops.tests.factories import ShopFactory

SUMMARY_URL = reverse("superadmin-ai-cost-summary")
ORGS_URL = reverse("superadmin-ai-cost-orgs")


FROZEN_NOW = datetime(2026, 11, 12, 15, 34, tzinfo=UTC)
# Window ends are exclusive and bucketed down to 15:30, so rows sit just before that.
ROW_TIME = datetime(2026, 11, 12, 15, 25, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _frozen_now(monkeypatch):
    """Freeze "now" at a fixed mid-month instant, deterministic at any wall-clock time.

    Windows resolve against FROZEN_NOW and every AiUsageLog the factory creates is
    stamped ROW_TIME unless the test passes its own ``created_at``.
    """
    monkeypatch.setattr(cost_window, "timezone", SimpleNamespace(now=lambda: FROZEN_NOW))
    original = AiUsageLogFactory._create.__func__

    def _create(cls, model_class, *args, **kwargs):
        kwargs.setdefault("created_at", ROW_TIME)
        return original(cls, model_class, *args, **kwargs)

    monkeypatch.setattr(AiUsageLogFactory, "_create", classmethod(_create))


@pytest.mark.parametrize("factory", [OrgAdminFactory, StaffAdminFactory])
@pytest.mark.parametrize("url", [SUMMARY_URL, ORGS_URL])
def test_non_superadmin_gets_403(db, factory, url):
    c = APIClient()
    c.force_authenticate(factory())
    assert c.get(url).status_code == 403


@pytest.mark.parametrize("url", [SUMMARY_URL, ORGS_URL])
def test_anonymous_gets_401_or_403(db, url):
    assert APIClient().get(url).status_code in (401, 403)


def test_summary_shape_and_values(superadmin_client):
    org = OrganisationFactory()
    AiUsageLogFactory(organisation=org, estimated_cost_usd=Decimal("1"))
    AiUsageLogFactory(organisation=org, status=AiUsageLog.Status.FAILED)
    r = superadmin_client.get(SUMMARY_URL)
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"range", "generated_at", "has_any_usage", "totals"}
    assert body["range"]["key"] == "this_month"
    assert body["has_any_usage"] is True
    assert set(body["totals"]) == {
        "calls",
        "success_calls",
        "failed_calls",
        "moderated_calls",
        "input_tokens",
        "output_tokens",
        "cost",
        "org_count",
        "active_shops",
    }
    assert body["totals"]["cost"] == "1.00000000"
    assert body["totals"]["calls"] == 2
    assert body["totals"]["failed_calls"] == 1
    assert body["totals"]["org_count"] == 1


def test_summary_has_any_usage_false_when_empty(superadmin_client):
    body = superadmin_client.get(SUMMARY_URL).json()
    assert body["has_any_usage"] is False
    assert body["totals"]["cost"] == "0.00000000"


def test_bad_range_returns_400(superadmin_client):
    r = superadmin_client.get(
        SUMMARY_URL, {"range": "custom", "from": "2026-10-31", "to": "2026-10-01"}
    )
    assert r.status_code == 400


def test_bad_sort_returns_400_and_is_not_cached(superadmin_client):
    assert superadmin_client.get(ORGS_URL, {"sort": "bogus"}).status_code == 400
    assert superadmin_client.get(ORGS_URL, {"sort": "bogus"}).status_code == 400


def test_org_list_includes_request_type_badges_and_paginates(superadmin_client):
    for _ in range(30):
        AiUsageLogFactory(organisation=OrganisationFactory())
    big = OrganisationFactory(name="Big Org")
    AiUsageLogFactory(organisation=big, estimated_cost_usd=Decimal("5"))
    AiUsageLogFactory(organisation=big, request_type="reply", estimated_cost_usd=Decimal("2.5"))

    r = superadmin_client.get(ORGS_URL)
    body = r.json()
    assert body["count"] == 31
    assert len(body["results"]) == 25
    assert body["next"] is not None
    assert "generated_at" in body
    first = body["results"][0]
    assert first["name"] == "Big Org"
    assert first["cost"] == "7.50000000"
    assert first["by_request_type"] == {"enrichment": "5.00000000", "reply": "2.50000000"}
    assert set(first) == {
        "organisation_id",
        "name",
        "org_type",
        "active_shops",
        "calls",
        "input_tokens",
        "output_tokens",
        "cost",
        "by_request_type",
    }

    assert len(superadmin_client.get(ORGS_URL, {"page_size": 10}).json()["results"]) == 10


def _count_queries(client, url):
    cache.clear()
    with CaptureQueriesContext(connection) as ctx:
        assert client.get(url).status_code == 200
    return ctx


def _add_review_linked_orgs(n):
    for _ in range(n):
        org = OrganisationFactory()
        shop = ShopFactory(organisation=org)
        for _ in range(2):
            AiUsageLogFactory(organisation=org, review=ReviewFactory(organisation=org, shop=shop))
        AiUsageLogFactory(organisation=org, status=AiUsageLog.Status.FAILED)


def test_org_list_query_count_is_constant(superadmin_client, assert_query_ceiling):
    counts = []
    for n in (5, 35):  # second pass: 40 orgs, spills onto page 2
        _add_review_linked_orgs(n)
        ctx = _count_queries(superadmin_client, ORGS_URL)
        assert_query_ceiling(ctx, max_queries=3)  # rows + badges (2) + 1
        counts.append(len(ctx.captured_queries))
    assert counts[0] == counts[1]


def test_second_call_is_served_from_cache(superadmin_client, django_assert_max_num_queries):
    AiUsageLogFactory()
    first = superadmin_client.get(ORGS_URL).json()
    with django_assert_max_num_queries(2):
        second = superadmin_client.get(ORGS_URL).json()
    assert second == first


def test_views_are_throttled():
    assert AiCostSummaryView.throttle_scope == "superadmin_ai_cost_read"
    assert AiCostOrganisationListView.throttle_scope == "superadmin_ai_cost_read"


def test_summary_query_count_is_constant(superadmin_client, assert_query_ceiling):
    counts = []
    for n in (5, 35):
        _add_review_linked_orgs(n)
        ctx = _count_queries(superadmin_client, SUMMARY_URL)
        assert_query_ceiling(ctx, max_queries=3)  # aggregate + exists (2) + 1
        counts.append(len(ctx.captured_queries))
    assert counts[0] == counts[1]


# --- Organisation drill-down (Task 5) ---------------------------------------------------------


def org_summary_url(org_id):
    return reverse("superadmin-ai-cost-org-summary", args=[org_id])


def org_shops_url(org_id):
    return reverse("superadmin-ai-cost-org-shops", args=[org_id])


def org_models_url(org_id):
    return reverse("superadmin-ai-cost-org-models", args=[org_id])


DRILLDOWN_URLS = [org_summary_url, org_shops_url, org_models_url]


def _shop_log(org, shop, **kw):
    review = ReviewFactory(organisation=org, shop=shop)
    return AiUsageLogFactory(organisation=org, review=review, **kw)


@pytest.mark.parametrize("url_for", DRILLDOWN_URLS)
def test_unknown_org_returns_404_on_all_drilldown_endpoints(superadmin_client, url_for):
    for _ in range(2):  # second hit proves the 404 is not cached
        r = superadmin_client.get(url_for(999999))
        assert r.status_code == 404
        assert r.json() == {"code": "organisation_not_found", "detail": "Organisation not found."}


def test_existing_org_without_activity_returns_zeros(superadmin_client):
    org = OrganisationFactory()
    r = superadmin_client.get(org_summary_url(org.id))
    assert r.status_code == 200
    assert r.json()["totals"]["calls"] == 0
    assert superadmin_client.get(org_shops_url(org.id)).json()["results"] == []
    assert superadmin_client.get(org_models_url(org.id)).json()["results"] == []


def test_org_summary_shape_and_shop_count(superadmin_client):
    org = OrganisationFactory(name="Acme")
    shop = ShopFactory(organisation=org)
    ShopFactory(organisation=org, is_active=False)
    ShopFactory()  # other org, must not count
    _shop_log(org, shop, estimated_cost_usd=Decimal("2"))
    AiUsageLogFactory(organisation=OrganisationFactory(), estimated_cost_usd=Decimal("9"))
    body = superadmin_client.get(org_summary_url(org.id)).json()
    assert set(body) == {"organisation", "range", "generated_at", "totals"}
    assert body["organisation"] == {
        "id": org.id,
        "name": "Acme",
        "org_type": org.org_type,
        "shop_count": 2,
    }
    assert body["range"]["key"] == "this_month"
    assert body["generated_at"].endswith("Z")
    assert body["totals"]["cost"] == "2.00000000"
    assert body["totals"]["calls"] == 1
    assert body["totals"]["active_shops"] == 1


def test_shops_endpoint_returns_unattributed_block(superadmin_client):
    org = OrganisationFactory()
    shop = ShopFactory(organisation=org, name="High St")
    _shop_log(org, shop, estimated_cost_usd=Decimal("3"))
    _shop_log(org, shop, request_type="reply", estimated_cost_usd=Decimal("1"))
    AiUsageLogFactory(organisation=org, review=None, estimated_cost_usd=Decimal("0.5"))
    body = superadmin_client.get(org_shops_url(org.id)).json()
    assert body["count"] == 1
    assert "generated_at" in body
    row = body["results"][0]
    assert set(row) == {
        "shop_id",
        "name",
        "region_name",
        "calls",
        "input_tokens",
        "output_tokens",
        "cost",
        "by_request_type",
    }
    assert row["shop_id"] == shop.id
    assert row["name"] == "High St"
    assert row["cost"] == "4.00000000"
    assert row["by_request_type"] == {"enrichment": "3.00000000", "reply": "1.00000000"}
    un = body["unattributed"]
    assert set(un) == {"calls", "input_tokens", "output_tokens", "cost", "by_request_type"}
    assert un["calls"] == 1
    assert un["cost"] == "0.50000000"
    assert un["by_request_type"] == {"enrichment": "0.50000000"}


def test_shops_endpoint_unattributed_null_when_none_and_bad_sort_400(superadmin_client):
    org = OrganisationFactory()
    _shop_log(org, ShopFactory(organisation=org))
    assert superadmin_client.get(org_shops_url(org.id)).json()["unattributed"] is None
    for _ in range(2):
        assert superadmin_client.get(org_shops_url(org.id), {"sort": "bogus"}).status_code == 400


def test_shops_endpoint_sorts_and_paginates(superadmin_client):
    org = OrganisationFactory()
    for i in range(1, 4):
        _shop_log(org, ShopFactory(organisation=org), estimated_cost_usd=Decimal(i))
    body = superadmin_client.get(org_shops_url(org.id), {"page_size": 10}).json()
    assert [r["cost"] for r in body["results"]] == ["3.00000000", "2.00000000", "1.00000000"]
    asc = superadmin_client.get(org_shops_url(org.id), {"sort": "cost", "page_size": 10}).json()
    assert asc["results"][0]["cost"] == "1.00000000"


def test_models_endpoint_sorted_by_cost(superadmin_client):
    org = OrganisationFactory()
    AiUsageLogFactory(organisation=org, model="small", estimated_cost_usd=Decimal("1"))
    AiUsageLogFactory(organisation=org, model="big", estimated_cost_usd=Decimal("4"))
    AiUsageLogFactory(organisation=OrganisationFactory(), model="other")
    body = superadmin_client.get(org_models_url(org.id)).json()
    assert set(body) == {"results", "generated_at"}
    assert [r["model"] for r in body["results"]] == ["big", "small"]
    assert set(body["results"][0]) == {"model", "calls", "input_tokens", "output_tokens", "cost"}
    assert body["results"][0]["cost"] == "4.00000000"


@pytest.mark.parametrize("factory", [OrgAdminFactory, StaffAdminFactory])
@pytest.mark.parametrize("url_for", DRILLDOWN_URLS)
def test_drilldown_forbidden_for_tenants(db, factory, url_for):
    org = OrganisationFactory()
    c = APIClient()
    c.force_authenticate(factory(organisation=org))
    assert c.get(url_for(org.id)).status_code == 403  # their OWN org too


def test_drilldown_views_are_throttled():
    for view in (AiCostOrgSummaryView, AiCostOrgShopsView, AiCostOrgModelsView):
        assert view.throttle_scope == "superadmin_ai_cost_read"


@pytest.mark.parametrize(
    ("url_for", "ceiling"),
    [
        (org_summary_url, 3),  # header + aggregate (2) + 1
        (org_shops_url, 6),  # header, rows, badges, unattributed + its by-type (5) + 1
        (org_models_url, 3),  # header + aggregate (2) + 1
    ],
)
def test_drilldown_query_count_is_constant(
    superadmin_client, assert_query_ceiling, url_for, ceiling
):
    org = OrganisationFactory()
    AiUsageLogFactory(organisation=org, review=None)
    counts = []
    for n in (3, 30):  # second pass: 33 shops, spills onto page 2
        for _ in range(n):
            shop = ShopFactory(organisation=org)
            for _ in range(2):
                _shop_log(org, shop)
        ctx = _count_queries(superadmin_client, url_for(org.id))
        assert_query_ceiling(ctx, max_queries=ceiling)
        counts.append(len(ctx.captured_queries))
    assert counts[0] == counts[1]


# --- Tenant isolation & cache keying (Task 9 audit) ---------------------------------------

PAYLOAD_KEYS = {"totals", "results", "organisation", "count", "generated_at", "unattributed"}


@pytest.mark.parametrize("url_for", DRILLDOWN_URLS)
def test_anonymous_gets_401_or_403_on_drilldown(db, url_for):
    org = OrganisationFactory()
    assert APIClient().get(url_for(org.id)).status_code in (401, 403)


@pytest.mark.parametrize("factory", [OrgAdminFactory, StaffAdminFactory])
def test_warm_cache_is_never_served_to_tenants(superadmin_client, factory):
    org = OrganisationFactory()
    _shop_log(org, ShopFactory(organisation=org), estimated_cost_usd=Decimal("2"))
    urls = [ORGS_URL, SUMMARY_URL, *(u(org.id) for u in DRILLDOWN_URLS)]
    for url in urls:  # warm every cache entry as the superadmin
        assert superadmin_client.get(url).status_code == 200

    tenant = APIClient()
    tenant.force_authenticate(factory(organisation=org))
    for url in urls:
        r = tenant.get(url)
        assert r.status_code == 403
        assert not PAYLOAD_KEYS & set(r.json())


def test_drilldown_cache_is_keyed_per_org(superadmin_client):
    org_a, org_b = OrganisationFactory(), OrganisationFactory()
    _shop_log(org_a, ShopFactory(organisation=org_a), estimated_cost_usd=Decimal("1"))
    _shop_log(org_b, ShopFactory(organisation=org_b), estimated_cost_usd=Decimal("7"))
    AiUsageLogFactory(organisation=org_b, model="other", estimated_cost_usd=Decimal("3"))
    for _ in range(2):  # second round is served from cache
        a = superadmin_client.get(org_summary_url(org_a.id)).json()
        b = superadmin_client.get(org_summary_url(org_b.id)).json()
        assert (a["organisation"]["id"], a["totals"]["cost"]) == (org_a.id, "1.00000000")
        assert (b["organisation"]["id"], b["totals"]["cost"]) == (org_b.id, "10.00000000")
        shops_a = superadmin_client.get(org_shops_url(org_a.id)).json()["results"]
        shops_b = superadmin_client.get(org_shops_url(org_b.id)).json()["results"]
        assert [r["cost"] for r in shops_a] == ["1.00000000"]
        assert [r["cost"] for r in shops_b] == ["7.00000000"]
        models_a = superadmin_client.get(org_models_url(org_a.id)).json()["results"]
        models_b = superadmin_client.get(org_models_url(org_b.id)).json()["results"]
        assert [m["cost"] for m in models_a] == ["1.00000000"]
        assert [m["cost"] for m in models_b] == ["7.00000000", "3.00000000"]


def test_list_cache_is_keyed_per_page(superadmin_client):
    for i in (1, 2):
        AiUsageLogFactory(organisation=OrganisationFactory(), estimated_cost_usd=Decimal(i))
    org = OrganisationFactory()
    for i in (1, 2):
        _shop_log(org, ShopFactory(organisation=org), estimated_cost_usd=Decimal(i))
    for url in (ORGS_URL, org_shops_url(org.id)):
        for _ in range(2):  # second round is served from cache
            p1 = superadmin_client.get(url, {"page_size": 1, "page": 1}).json()["results"]
            p2 = superadmin_client.get(url, {"page_size": 1, "page": 2}).json()["results"]
            assert len(p1) == len(p2) == 1
            assert p1 != p2


def test_cache_is_keyed_per_range(superadmin_client):
    org = OrganisationFactory()
    _shop_log(org, ShopFactory(organisation=org), estimated_cost_usd=Decimal("1"))
    _shop_log(
        org,
        ShopFactory(organisation=org),
        estimated_cost_usd=Decimal("4"),
        created_at=ROW_TIME - timedelta(days=20),
    )
    for _ in range(2):  # second round is served from cache
        for url in (SUMMARY_URL, org_summary_url(org.id)):
            week = superadmin_client.get(url, {"range": "7d"}).json()["totals"]["cost"]
            month = superadmin_client.get(url, {"range": "30d"}).json()["totals"]["cost"]
            assert (week, month) == ("1.00000000", "5.00000000")
        orgs_7 = superadmin_client.get(ORGS_URL, {"range": "7d"}).json()["results"]
        orgs_30 = superadmin_client.get(ORGS_URL, {"range": "30d"}).json()["results"]
        assert [r["cost"] for r in orgs_7] == ["1.00000000"]
        assert [r["cost"] for r in orgs_30] == ["5.00000000"]
        shops_7 = superadmin_client.get(org_shops_url(org.id), {"range": "7d"}).json()
        shops_30 = superadmin_client.get(org_shops_url(org.id), {"range": "30d"}).json()
        assert shops_7["count"] == 1
        assert shops_30["count"] == 2


# --- Page shell (Task 6) ---


def _superadmin_client(client):
    client.force_login(UserFactory(role=User.Role.SUPERADMIN))
    return client


def test_page_renders_for_superadmin(client, db):
    _superadmin_client(client)
    resp = client.get("/admin/ai-cost/")
    assert resp.status_code == 200
    assert b'id="ai-cost-root"' in resp.content
    org = OrganisationFactory()
    resp = client.get(f"/admin/ai-cost/organisations/{org.pk}/")
    assert resp.status_code == 200
    assert b'id="ai-cost-root"' in resp.content


def test_org_detail_page_passes_org_id(client, db):
    _superadmin_client(client)
    org = OrganisationFactory()
    resp = client.get(reverse("ai_cost_org_detail", args=[org.pk]))
    assert f'data-org-id="{org.pk}"'.encode() in resp.content
    assert b'data-org-id=""' in client.get(reverse("ai_cost_explorer")).content


@pytest.mark.parametrize("factory", [OrgAdminFactory, StaffAdminFactory])
def test_page_forbidden_for_tenants(client, db, factory):
    client.force_login(factory())
    assert client.get("/admin/ai-cost/").status_code == 403
    assert client.get("/admin/ai-cost/organisations/1/").status_code == 403


def test_page_redirects_anonymous(client, db):
    resp = client.get("/admin/ai-cost/")
    assert resp.status_code == 302


def test_sidebar_shows_ai_cost_only_for_superadmin(client, db):
    _superadmin_client(client)
    assert b'href="/admin/ai-cost/"' in client.get("/admin/ai-cost/").content
    client.logout()
    org_admin = OrgAdminFactory(organisation=OrganisationFactory())
    client.force_login(org_admin)
    resp = client.get("/admin/org/shops/")
    assert resp.status_code == 200
    assert b"/admin/ai-cost/" not in resp.content
    client.logout()
    client.force_login(StaffAdminFactory(organisation=OrganisationFactory()))
    resp = client.get("/admin/org/reviews/")
    assert resp.status_code == 200
    assert b"/admin/ai-cost/" not in resp.content
