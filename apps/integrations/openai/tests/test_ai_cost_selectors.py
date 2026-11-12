from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from rest_framework.exceptions import ValidationError

from apps.integrations.openai.cost_window import resolve_cost_window
from apps.integrations.openai.selectors.ai_cost import (
    get_cost_summary,
    get_request_type_costs,
    get_shop_request_type_costs,
    get_unattributed_costs,
    list_model_costs,
    list_org_costs,
    list_shop_costs,
)
from apps.integrations.openai.tests.factories import AiUsageLogFactory
from apps.organisations.tests.factories import OrganisationFactory
from apps.regions.tests.factories import RegionFactory
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


def test_summary_cost_keeps_eight_decimal_places(db):
    AiUsageLogFactory(estimated_cost_usd=Decimal("0.000195"), created_at=IN)
    cost = get_cost_summary(window=W)["cost"]
    assert str(cost) == "0.00019500"


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


def _log(org, shop=None, cost="1.00", **kw):
    review = ReviewFactory(organisation=org, shop=shop) if shop else None
    kw.setdefault("created_at", IN)
    return AiUsageLogFactory(
        organisation=org, review=review, estimated_cost_usd=Decimal(cost), **kw
    )


def test_shop_list_groups_by_shop_and_sorts_by_cost(db):
    org = OrganisationFactory()
    region = RegionFactory(name="North")
    a = ShopFactory(organisation=org, name="A", region=region)
    b = ShopFactory(organisation=org, name="B")
    _log(org, a, "1.00")
    _log(org, a, "0.50")
    _log(org, b, "3.00")
    rows = list(list_shop_costs(window=W, organisation_id=org.id))
    assert [r["name"] for r in rows] == ["B", "A"]
    by = {r["shop_id"]: r for r in rows}
    assert by[a.id]["calls"] == 2
    assert quantize(by[a.id]["cost"]) == Decimal("1.50")
    assert (by[a.id]["input_tokens"], by[a.id]["output_tokens"]) == (1000, 400)
    assert by[a.id]["region_name"] == "North"
    assert by[b.id]["region_name"] == b.region.name


def quantize(v):
    return Decimal(v).quantize(Decimal("0.00000001"))


def test_shop_list_scoped_to_org(db):
    org, other = OrganisationFactory(), OrganisationFactory()
    _log(org, ShopFactory(organisation=org))
    other_shop = ShopFactory(organisation=other)
    _log(other, other_shop)
    ids = [r["shop_id"] for r in list_shop_costs(window=W, organisation_id=org.id)]
    assert other_shop.id not in ids
    assert len(ids) == 1


def test_shop_list_sort_and_unknown_sort(db):
    org = OrganisationFactory()
    for n in ("Beta", "Alpha"):
        _log(org, ShopFactory(organisation=org, name=n))
    rows = list_shop_costs(window=W, organisation_id=org.id, sort="name")
    assert [r["name"] for r in rows] == ["Alpha", "Beta"]
    with pytest.raises(ValidationError):
        list_shop_costs(window=W, organisation_id=org.id, sort="-latency")


def test_shop_request_type_costs(db):
    org = OrganisationFactory()
    shop = ShopFactory(organisation=org)
    _log(org, shop, "1.20")
    _log(org, shop, "0.30", request_type="reply_generation")
    _log(org, shop, "0", request_type="reply_generation", status="FAILED")
    _log(org, None, "9.00")
    got = get_shop_request_type_costs(window=W, organisation_id=org.id, shop_ids=[shop.id])
    assert got == {shop.id: {"enrichment": Decimal("1.20"), "reply_generation": Decimal("0.30")}}


def test_unattributed_row_holds_rows_without_review(db):
    org = OrganisationFactory()
    _log(org, ShopFactory(organisation=org), "1.00")
    _log(org, None, "0.40", request_type="reply_generation")
    _log(org, None, "0", status="FAILED")
    shops = list(list_shop_costs(window=W, organisation_id=org.id))
    un = get_unattributed_costs(window=W, organisation_id=org.id)
    total = sum(quantize(r["cost"]) for r in shops) + un["cost"]
    assert total == get_cost_summary(window=W, organisation_id=org.id)["cost"]
    assert un["cost"] == Decimal("0.40")
    assert (un["calls"], un["success_calls"], un["failed_calls"]) == (2, 1, 1)
    assert un["by_request_type"] == {"reply_generation": Decimal("0.40")}


def test_unattributed_is_none_when_all_rows_have_reviews(db):
    org = OrganisationFactory()
    _log(org, ShopFactory(organisation=org))
    _log(OrganisationFactory(), None)  # other org's unattributed row is ignored
    assert get_unattributed_costs(window=W, organisation_id=org.id) is None


def test_model_costs_sum_to_org_cost(db):
    org = OrganisationFactory()
    _log(org, None, "1.00", model="m-a")
    _log(org, None, "0.50", model="m-a")
    _log(org, None, "2.00", model="m-b")
    _log(org, None, "0", model="m-c", status="FAILED")
    _log(OrganisationFactory(), None, "7.00", model="m-a")
    rows = list_model_costs(window=W, organisation_id=org.id)
    assert [r["model"] for r in rows] == ["m-b", "m-a", "m-c"]
    assert rows[1]["calls"] == 2
    assert rows[2]["cost"] == Decimal("0")
    assert (
        sum(r["cost"] for r in rows) == get_cost_summary(window=W, organisation_id=org.id)["cost"]
    )


def test_drilldown_selectors_fixed_query_counts(db, django_assert_max_num_queries):
    org = OrganisationFactory()
    shops = [ShopFactory(organisation=org) for _ in range(15)]
    for shop in shops:
        _log(org, shop)
        _log(org, shop, request_type="reply_generation")
    _log(org, None)
    with django_assert_max_num_queries(1):
        list(list_shop_costs(window=W, organisation_id=org.id))
    with django_assert_max_num_queries(1):
        get_shop_request_type_costs(
            window=W, organisation_id=org.id, shop_ids=[s.id for s in shops]
        )
    with django_assert_max_num_queries(2):
        get_unattributed_costs(window=W, organisation_id=org.id)
    with django_assert_max_num_queries(1):
        list_model_costs(window=W, organisation_id=org.id)
