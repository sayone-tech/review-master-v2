"""SCOPE-01 negative sweep: every credit route, the reviews credit endpoints and the Shops API.

One table-driven test proves each protected endpoint refuses (or hides) what a caller must not
reach and writes nothing. A guard test fails when a route is added to
``apps/credits/api_urls.py`` without a sweep row.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from unittest.mock import patch

import pytest
from django.core.cache import caches
from django.urls import reverse
from rest_framework.response import Response
from rest_framework.test import APIClient

from apps.accounts.models import StaffAccessScope
from apps.accounts.tests.factories import OrgAdminFactory, StaffAdminFactory, UserFactory
from apps.common.models import AuditLog
from apps.credits import api_urls
from apps.credits.models import CreditTransaction, ShopCreditBalance
from apps.credits.services.periods import current_period
from apps.organisations.tests.factories import OrganisationFactory
from apps.reviews.tests.factories import ReviewFactory
from apps.shops.tests.factories import ShopFactory

pytestmark = pytest.mark.django_db

GENERATE_SEAM = "apps.reviews.services.reply_generation._generate_reply_draft_with_log"


@pytest.fixture(autouse=True)
def _clear_throttle_cache():
    caches["throttle"].clear()
    yield
    caches["throttle"].clear()


@dataclass
class World:
    shop_in: Any
    shop_out: Any
    review_out: Any
    callers: dict[str, Any]  # caller label -> user (None = anonymous)


@pytest.fixture
def world() -> World:
    org = OrganisationFactory(monthly_credit_allocation=10)
    shop_in = ShopFactory(organisation=org)
    shop_out = ShopFactory(organisation=org)
    review_out = ReviewFactory(organisation=org, shop=shop_out, comment="x" * 150)
    staff = StaffAdminFactory(organisation=org)
    StaffAccessScope.objects.create(
        user=staff, scope_type=StaffAccessScope.ScopeType.SHOP, shop=shop_in
    )
    return World(
        shop_in=shop_in,
        shop_out=shop_out,
        review_out=review_out,
        callers={
            "org_admin": OrgAdminFactory(organisation=org),
            "staff_in_scope": staff,
            "staff_no_scope": StaffAdminFactory(organisation=org),
            "other_org_admin": OrgAdminFactory(organisation=OrganisationFactory()),
            "superadmin": UserFactory(),
            "anonymous": None,
        },
    )


@dataclass(frozen=True)
class Row:
    """One sweep case. ``route`` is the url name for credit routes, else a label."""

    route: str
    method: str
    caller: str
    expected: frozenset[int]
    url: Callable[[World], str]
    body: Callable[[World], dict[str, Any]] | None = None
    check: Callable[[Response, World], None] | None = None


REFUSED = frozenset({401, 403})
NOT_FOUND = frozenset({404})
FORBIDDEN = frozenset({403})


def _bonus_body(_: World) -> dict[str, Any]:
    period = current_period()
    return {
        "amount": 5,
        "reason": "",
        "period_year": period.year,
        "period_month": period.month,
    }


def _superadmin_list_url(w: World) -> str:
    return reverse("superadmin-credit-shops", kwargs={"org_id": w.shop_in.organisation_id})


def _superadmin_bonus_url(w: World) -> str:
    return reverse("superadmin-credit-bonus", kwargs={"shop_id": w.shop_in.pk})


def _shop_credits_out_url(w: World) -> str:
    return reverse("shop-credits", kwargs={"shop_id": w.shop_out.pk})


def _credit_cost_url(w: World) -> str:
    return f"/api/v1/reviews/{w.review_out.pk}/credit-cost/"


def _generate_url(w: World) -> str:
    return f"/api/v1/reviews/{w.review_out.pk}/generate-reply/"


def _check_shops_list_omits_out_of_scope(resp: Response, w: World) -> None:
    data = resp.json()
    rows = data["results"] if isinstance(data, dict) else data
    ids = {row["id"] for row in rows}
    assert w.shop_in.pk in ids
    assert w.shop_out.pk not in ids


ROWS: list[Row] = [
    # Superadmin endpoints: tenant roles and anonymous are refused.
    *[
        Row("superadmin-credit-shops", "get", caller, REFUSED, _superadmin_list_url)
        for caller in ("org_admin", "staff_in_scope", "anonymous")
    ],
    *[
        Row(
            "superadmin-credit-bonus",
            "post",
            caller,
            REFUSED,
            _superadmin_bonus_url,
            body=_bonus_body,
        )
        for caller in ("org_admin", "staff_in_scope", "anonymous")
    ],
    # Tenant shop-credits read.
    Row("shop-credits", "get", "staff_in_scope", NOT_FOUND, _shop_credits_out_url),
    Row("shop-credits", "get", "staff_no_scope", NOT_FOUND, _shop_credits_out_url),
    Row("shop-credits", "get", "other_org_admin", NOT_FOUND, _shop_credits_out_url),
    Row("shop-credits", "get", "superadmin", FORBIDDEN, _shop_credits_out_url),
    Row("shop-credits", "get", "anonymous", REFUSED, _shop_credits_out_url),
    # Reviews credit endpoints for a review of an out-of-scope shop.
    Row("reviews-credit-cost", "get", "staff_in_scope", NOT_FOUND, _credit_cost_url),
    Row("reviews-credit-cost", "get", "other_org_admin", NOT_FOUND, _credit_cost_url),
    Row(
        "reviews-generate-reply",
        "post",
        "staff_in_scope",
        NOT_FOUND,
        _generate_url,
        body=lambda _: {"tone": "professional"},
    ),
    Row(
        "reviews-generate-reply",
        "post",
        "other_org_admin",
        NOT_FOUND,
        _generate_url,
        body=lambda _: {"tone": "professional"},
    ),
    # Shops API as Staff.
    Row(
        "shops-list",
        "get",
        "staff_in_scope",
        frozenset({200}),
        lambda _: reverse("shop-list"),
        check=_check_shops_list_omits_out_of_scope,
    ),
    Row(
        "shops-retrieve",
        "get",
        "staff_in_scope",
        NOT_FOUND,
        lambda w: reverse("shop-detail", kwargs={"pk": w.shop_out.pk}),
    ),
]


def _row_id(row: Row) -> str:
    return f"{row.route}-{row.method}-{row.caller}"


def _write_counts() -> tuple[int, int, int]:
    return (
        ShopCreditBalance.objects.count(),
        CreditTransaction.objects.count(),
        AuditLog.objects.count(),
    )


@pytest.mark.parametrize("row", ROWS, ids=_row_id)
def test_sweep_refuses_caller_and_writes_nothing(row: Row, world: World) -> None:
    user = world.callers[row.caller]
    client = APIClient()
    if user is not None:
        client.force_authenticate(user=user)
    before = _write_counts()

    with patch(GENERATE_SEAM) as generate_mock:
        kwargs: dict[str, Any] = {"format": "json"} if row.body else {}
        if row.body:
            kwargs["data"] = row.body(world)
        resp = getattr(client, row.method)(row.url(world), **kwargs)

    assert resp.status_code in row.expected, resp.content
    generate_mock.assert_not_called()
    assert _write_counts() == before
    if row.check is not None:
        row.check(resp, world)


# --- route coverage guard -------------------------------------------------------------------


def _uncovered_route_names(route_names: set[str]) -> set[str]:
    """Route names that have no row in the sweep table."""
    return route_names - {row.route for row in ROWS}


def _credit_route_names() -> set[str]:
    return {p.name for p in api_urls.urlpatterns if getattr(p, "name", None)}


def test_every_credit_route_has_a_sweep_row() -> None:
    assert _uncovered_route_names(_credit_route_names()) == set()


def test_guard_detects_a_route_without_a_sweep_row() -> None:
    assert _uncovered_route_names(_credit_route_names() | {"extra-route"}) == {"extra-route"}
