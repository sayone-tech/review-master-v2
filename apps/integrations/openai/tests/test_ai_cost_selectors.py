from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from rest_framework.exceptions import ValidationError

from apps.integrations.openai.cost_window import resolve_cost_window
from apps.integrations.openai.selectors.ai_cost import (
    get_cost_summary,
    get_request_type_costs,
    list_org_costs,
)
from apps.integrations.openai.tests.factories import AiUsageLogFactory
from apps.organisations.tests.factories import OrganisationFactory
from apps.reviews.tests.factories import ReviewFactory
from apps.shops.tests.factories import ShopFactory

NOW = datetime(2026, 11, 20, 12, 0, tzinfo=UTC)
W = resolve_cost_window(params={}, now=NOW)
IN = NOW - timedelta(days=2)


def test_summary_counts_all_statuses_but_costs_success_only(db):
    org = OrganisationFactory()
    AiUsageLogFactory(
        organisation=org,
        estimated_cost_usd=Decimal("1.00"),
        prompt_tokens=100,
        completion_tokens=10,
        created_at=IN,
    )
    AiUsageLogFactory(
        organisation=org,
        status="FAILED",
        estimated_cost_usd=Decimal("0"),
        prompt_tokens=None,
        completion_tokens=None,
        created_at=IN,
    )
    AiUsageLogFactory(
        organisation=org,
        status="MODERATED",
        estimated_cost_usd=Decimal("0.50"),
        prompt_tokens=50,
        completion_tokens=5,
        created_at=IN,
    )
    s = get_cost_summary(window=W)
    assert (s["calls"], s["success_calls"], s["failed_calls"], s["moderated_calls"]) == (3, 1, 1, 1)
    assert s["cost"] == Decimal("1.00")
    assert (s["input_tokens"], s["output_tokens"]) == (100, 10)
    assert s["org_count"] == 1


def test_summary_excludes_rows_outside_window(db):
    AiUsageLogFactory(created_at=W.start - timedelta(seconds=1))
    AiUsageLogFactory(created_at=W.end)
    assert get_cost_summary(window=W)["calls"] == 0


def test_null_tokens_sum_to_zero_not_none(db):
    AiUsageLogFactory(status="FAILED", prompt_tokens=None, completion_tokens=None, created_at=IN)
    s = get_cost_summary(window=W)
    assert (s["input_tokens"], s["output_tokens"], s["cost"]) == (0, 0, Decimal("0"))


def test_empty_window_returns_zeros(db):
    assert get_cost_summary(window=W) == {
        "calls": 0,
        "success_calls": 0,
        "failed_calls": 0,
        "moderated_calls": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "cost": Decimal("0"),
        "org_count": 0,
        "active_shops": 0,
    }


def test_org_scoped_summary_ignores_other_orgs(db):
    org, other = OrganisationFactory(), OrganisationFactory()
    AiUsageLogFactory(organisation=org, estimated_cost_usd=Decimal("2.00"), created_at=IN)
    AiUsageLogFactory(organisation=other, estimated_cost_usd=Decimal("9.00"), created_at=IN)
    s = get_cost_summary(window=W, organisation_id=org.id)
    assert (s["calls"], s["cost"], s["org_count"]) == (1, Decimal("2.00"), 1)


def test_summary_cost_is_quantized(db):
    AiUsageLogFactory(estimated_cost_usd=Decimal("0.1"), created_at=IN)
    AiUsageLogFactory(estimated_cost_usd=Decimal("0.2"), created_at=IN)
    assert get_cost_summary(window=W)["cost"] == Decimal("0.300000")


def test_org_list_excludes_inactive_orgs_and_sorts_by_cost_desc(db):
    org_a, org_b, org_c = OrganisationFactory(), OrganisationFactory(), OrganisationFactory()
    AiUsageLogFactory(organisation=org_a, estimated_cost_usd=Decimal("2.00"), created_at=IN)
    AiUsageLogFactory(organisation=org_b, estimated_cost_usd=Decimal("5.00"), created_at=IN)
    AiUsageLogFactory(organisation=org_c, created_at=W.start - timedelta(days=1))
    rows = list(list_org_costs(window=W))
    assert [r["organisation_id"] for r in rows] == [org_b.id, org_a.id]
    assert set(rows[0]) == {
        "organisation_id",
        "name",
        "org_type",
        "active_shops",
        "calls",
        "input_tokens",
        "output_tokens",
        "cost",
    }


def test_org_with_only_failed_calls_is_listed_with_zero_cost(db):
    org = OrganisationFactory()
    for _ in range(2):
        AiUsageLogFactory(
            organisation=org, status="FAILED", prompt_tokens=None, completion_tokens=None,
            estimated_cost_usd=Decimal("0"), created_at=IN,
        )  # fmt: skip
    rows = list(list_org_costs(window=W))
    assert (rows[0]["calls"], rows[0]["cost"], rows[0]["input_tokens"]) == (2, Decimal("0"), 0)


def test_active_shops_counts_distinct_shops_with_success(db):
    org = OrganisationFactory()
    shops = [ShopFactory(organisation=org) for _ in range(3)]
    for shop in (shops[0], shops[0], shops[1]):
        AiUsageLogFactory(
            organisation=org, review=ReviewFactory(organisation=org, shop=shop), created_at=IN
        )
    AiUsageLogFactory(
        organisation=org,
        status="FAILED",
        review=ReviewFactory(organisation=org, shop=shops[2]),
        created_at=IN,
    )
    assert next(iter(list_org_costs(window=W)))["active_shops"] == 2
    assert get_cost_summary(window=W)["active_shops"] == 2


def test_org_list_sort_by_name_ascending(db):
    for name in ("Beta", "Alpha"):
        AiUsageLogFactory(organisation=OrganisationFactory(name=name), created_at=IN)
    assert [r["name"] for r in list_org_costs(window=W, sort="name")] == ["Alpha", "Beta"]


def test_org_list_unknown_sort_raises(db):
    with pytest.raises(ValidationError):
        list_org_costs(window=W, sort="-latency")


def test_request_type_costs_sum_to_org_cost(db):
    org = OrganisationFactory()
    AiUsageLogFactory(organisation=org, estimated_cost_usd=Decimal("1.20"), created_at=IN)
    AiUsageLogFactory(
        organisation=org, request_type="reply_generation",
        estimated_cost_usd=Decimal("0.30"), created_at=IN,
    )  # fmt: skip
    AiUsageLogFactory(
        organisation=org, request_type="reply_generation", status="FAILED",
        estimated_cost_usd=Decimal("0"), created_at=IN,
    )  # fmt: skip
    by_type = get_request_type_costs(window=W, organisation_ids=[org.id])
    assert by_type == {org.id: {"enrichment": Decimal("1.20"), "reply_generation": Decimal("0.30")}}


def test_selectors_use_fixed_query_counts(db, django_assert_max_num_queries):
    orgs = [OrganisationFactory() for _ in range(20)]
    for org in orgs:
        for _ in range(3):
            AiUsageLogFactory(organisation=org, created_at=IN)
    ids = [o.id for o in orgs]
    with django_assert_max_num_queries(1):
        get_cost_summary(window=W)
    with django_assert_max_num_queries(1):
        list(list_org_costs(window=W))
    with django_assert_max_num_queries(1):
        get_request_type_costs(window=W, organisation_ids=ids)
