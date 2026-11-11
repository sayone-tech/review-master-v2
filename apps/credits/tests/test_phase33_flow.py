"""Phase 33 whole-phase walk-through (CVIS-01..05, SCOPE-01).

One organisation, three roles: the Org Admin lists shops with credits, a Superadmin tops a shop up,
an in-scope Staff user spends credits, and every surface (Shops list, credits GET, Activity Log)
must agree. The out-of-scope shop and the credit audit rows stay hidden from Staff.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from django.core.cache import caches
from rest_framework.test import APIClient

from apps.accounts.models import StaffAccessScope
from apps.accounts.tests.factories import OrgAdminFactory, StaffAdminFactory, UserFactory
from apps.credits.services.periods import current_period
from apps.organisations.tests.factories import OrganisationFactory
from apps.reviews.tests.factories import ReviewFactory
from apps.shops.tests.factories import ShopFactory

pytestmark = pytest.mark.django_db

GENERATE_SEAM = "apps.reviews.services.reply_generation._generate_reply_draft_with_log"
BONUS = 10


def _client(user) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _rows(resp) -> list[dict]:
    data = resp.json()
    return data["results"] if isinstance(data, dict) else data


def test_phase33_credit_visibility_walkthrough_when_org_admin_staff_and_superadmin_interact():
    caches["throttle"].clear()
    org = OrganisationFactory(monthly_credit_allocation=50)
    shop_a = ShopFactory(organisation=org)
    shop_b = ShopFactory(organisation=org)
    review = ReviewFactory(organisation=org, shop=shop_a, comment="x" * 150)
    staff = StaffAdminFactory(organisation=org)
    StaffAccessScope.objects.create(
        user=staff, scope_type=StaffAccessScope.ScopeType.SHOP, shop=shop_a
    )
    org_admin_client = _client(OrgAdminFactory(organisation=org))
    superadmin_client = _client(UserFactory())
    staff_client = _client(staff)
    period = current_period()

    # 1. Org Admin sees both shops with their credits (CVIS-02).
    shops = {row["id"]: row for row in _rows(org_admin_client.get("/api/v1/shops/"))}
    assert set(shops) == {shop_a.pk, shop_b.pk}
    assert shops[shop_a.pk]["credits_remaining"] == 50
    assert shops[shop_b.pk]["credits_remaining"] == 50

    # 2. Superadmin tops up shop A (Phase 32 endpoint).
    bonus_resp = superadmin_client.post(
        f"/api/v1/superadmin/shops/{shop_a.pk}/credits/bonus/",
        {
            "amount": BONUS,
            "reason": "Goodwill",
            "period_year": period.year,
            "period_month": period.month,
        },
        format="json",
    )
    assert bonus_resp.status_code == 201

    # 3. Org Admin credits GET and a fresh Shops list agree on the new remaining (CVIS-01/02).
    credits = org_admin_client.get(f"/api/v1/shops/{shop_a.pk}/credits/")
    assert credits.status_code == 200
    body = credits.json()
    assert (body["remaining"], body["total"], body["bonus"]) == (50 + BONUS, 50 + BONUS, BONUS)
    fresh = {row["id"]: row for row in _rows(org_admin_client.get("/api/v1/shops/"))}
    assert fresh[shop_a.pk]["credits_remaining"] == body["remaining"]
    assert fresh[shop_a.pk]["credits_total"] == body["total"]
    assert fresh[shop_a.pk]["credits_bonus"] == body["bonus"]

    # 4. In-scope Staff generates a reply; remaining drops by the server cost (CVIS-03).
    cost = staff_client.get(f"/api/v1/reviews/{review.pk}/credit-cost/").json()["cost"]
    assert cost >= 1
    with patch(GENERATE_SEAM, return_value=("Thanks for the feedback!", None)) as seam:
        gen = staff_client.post(
            f"/api/v1/reviews/{review.pk}/generate-reply/", {"tone": "professional"}, format="json"
        )
    assert gen.status_code == 200
    assert seam.call_count == 1
    assert gen.json()["credits_remaining"] == 50 + BONUS - cost

    # 5. The Org Admin's credits GET reflects the spend.
    after = org_admin_client.get(f"/api/v1/shops/{shop_a.pk}/credits/").json()
    assert after["remaining"] == 50 + BONUS - cost
    assert after["consumed"] == cost

    # 6. The Org Admin Activity Log shows the bonus and the consumption with the shop name (CVIS-05).
    audit = _rows(org_admin_client.get("/api/v1/audit-logs/"))
    by_action = {
        row["action"]: row
        for row in audit
        if row["action"] in {"shop.credits.bonus_allocated", "shop.credits.consumed"}
    }
    assert set(by_action) == {"shop.credits.bonus_allocated", "shop.credits.consumed"}
    for row in by_action.values():
        assert row["entity_id"] == str(shop_a.pk)
        assert row["shop_name"] == shop_a.name

    # 7. Staff sees only the in-scope shop, 404 for the other shop's credits, no credit audit rows
    #    (SCOPE-01).
    staff_shops = _rows(staff_client.get("/api/v1/shops/"))
    assert [row["id"] for row in staff_shops] == [shop_a.pk]
    assert staff_client.get(f"/api/v1/shops/{shop_b.pk}/credits/").status_code == 404
    staff_audit = staff_client.get("/api/v1/audit-logs/")
    assert staff_audit.status_code == 200
    assert not [row for row in _rows(staff_audit) if row["entity_type"] in {"shop", "organisation"}]
