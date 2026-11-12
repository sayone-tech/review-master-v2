from __future__ import annotations

from decimal import Decimal

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.tests.factories import OrgAdminFactory, StaffAdminFactory
from apps.integrations.openai.models import AiUsageLog
from apps.integrations.openai.tests.factories import AiUsageLogFactory
from apps.integrations.openai.views import AiCostOrganisationListView, AiCostSummaryView
from apps.organisations.tests.factories import OrganisationFactory

SUMMARY_URL = reverse("superadmin-ai-cost-summary")
ORGS_URL = reverse("superadmin-ai-cost-orgs")


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
    assert body["totals"]["cost"] == "1.000000"
    assert body["totals"]["calls"] == 2
    assert body["totals"]["failed_calls"] == 1
    assert body["totals"]["org_count"] == 1


def test_summary_has_any_usage_false_when_empty(superadmin_client):
    body = superadmin_client.get(SUMMARY_URL).json()
    assert body["has_any_usage"] is False
    assert body["totals"]["cost"] == "0.000000"


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
    assert first["cost"] == "7.500000"
    assert first["by_request_type"] == {"enrichment": "5.000000", "reply": "2.500000"}
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


def test_org_list_query_ceiling(superadmin_client, assert_query_ceiling):
    for _ in range(40):
        org = OrganisationFactory()
        for _ in range(3):
            AiUsageLogFactory(organisation=org)
    with CaptureQueriesContext(connection) as ctx:
        assert superadmin_client.get(ORGS_URL).status_code == 200
    assert_query_ceiling(ctx, max_queries=6)


def test_second_call_is_served_from_cache(superadmin_client, django_assert_max_num_queries):
    AiUsageLogFactory()
    first = superadmin_client.get(ORGS_URL).json()
    with django_assert_max_num_queries(2):
        second = superadmin_client.get(ORGS_URL).json()
    assert second == first


def test_views_are_throttled():
    assert AiCostSummaryView.throttle_scope == "superadmin_ai_cost_read"
    assert AiCostOrganisationListView.throttle_scope == "superadmin_ai_cost_read"
