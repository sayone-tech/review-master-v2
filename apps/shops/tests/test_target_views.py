from __future__ import annotations

import datetime
from unittest.mock import patch

import pytest
from rest_framework.test import APIClient

from apps.accounts.tests.factories import UserFactory
from apps.organisations.tests.factories import OrganisationFactory
from apps.shops.models import ReviewTarget
from apps.shops.tests.factories import ReviewTargetFactory, ShopFactory


@pytest.fixture
def org_admin_client(db):
    org = OrganisationFactory()
    admin = UserFactory(role="ORG_ADMIN", organisation=org)
    client = APIClient()
    client.force_authenticate(user=admin)
    return org, admin, client


@pytest.fixture
def staff_client(db):
    org = OrganisationFactory()
    staff = UserFactory(role="STAFF_ADMIN", organisation=org)
    client = APIClient()
    client.force_authenticate(user=staff)
    return org, staff, client


@pytest.fixture
def bypass_session_auth():
    with patch("apps.common.permissions.RequiresSessionAuth.has_permission", return_value=True):
        yield


@pytest.mark.django_db
class TestTargetList:
    def test_org_admin_can_list(self, org_admin_client):
        org, _admin, client = org_admin_client
        shop = ShopFactory(organisation=org)
        ReviewTargetFactory(shop=shop, organisation=org)
        resp = client.get(f"/api/v1/shops/{shop.pk}/targets/")
        assert resp.status_code == 200
        assert len(resp.data) == 1
        row = resp.data[0]
        assert "period_type" in row
        assert "received_count" in row
        assert "pct" in row
        assert "days_remaining" in row

    def test_staff_can_list_own_shop(self, staff_client):
        org, _staff, client = staff_client
        shop = ShopFactory(organisation=org)
        ReviewTargetFactory(shop=shop, organisation=org)
        resp = client.get(f"/api/v1/shops/{shop.pk}/targets/")
        assert resp.status_code == 200

    def test_unauthenticated_returns_403(self, db):
        shop = ShopFactory()
        client = APIClient()
        resp = client.get(f"/api/v1/shops/{shop.pk}/targets/")
        assert resp.status_code in (401, 403)

    def test_cannot_list_other_orgs_shop(self, org_admin_client):
        _org, _admin, client = org_admin_client
        other_shop = ShopFactory()  # different org
        resp = client.get(f"/api/v1/shops/{other_shop.pk}/targets/")
        assert resp.status_code in (403, 404)


@pytest.mark.django_db
class TestTargetCreate:
    def test_org_admin_creates_target(self, org_admin_client, bypass_session_auth):
        org, _admin, client = org_admin_client
        shop = ShopFactory(organisation=org)
        payload = {
            "period_type": "MONTH",
            "period_start": "2026-05-01",
            "target_count": 200,
        }
        resp = client.post(f"/api/v1/shops/{shop.pk}/targets/", payload, format="json")
        assert resp.status_code == 201
        assert ReviewTarget.objects.filter(shop=shop, target_count=200).exists()

    def test_normalises_period_start(self, org_admin_client, bypass_session_auth):
        org, _admin, client = org_admin_client
        shop = ShopFactory(organisation=org)
        payload = {
            "period_type": "MONTH",
            "period_start": "2026-05-15",  # mid-month
            "target_count": 100,
        }
        resp = client.post(f"/api/v1/shops/{shop.pk}/targets/", payload, format="json")
        assert resp.status_code == 201
        t = ReviewTarget.objects.get(shop=shop)
        assert t.period_start == datetime.date(2026, 5, 1)

    def test_staff_cannot_create(self, staff_client, bypass_session_auth):
        org, _staff, client = staff_client
        shop = ShopFactory(organisation=org)
        payload = {
            "period_type": "MONTH",
            "period_start": "2026-05-01",
            "target_count": 50,
        }
        resp = client.post(f"/api/v1/shops/{shop.pk}/targets/", payload, format="json")
        assert resp.status_code == 403

    def test_past_period_returns_400(self, org_admin_client, bypass_session_auth):
        org, _admin, client = org_admin_client
        shop = ShopFactory(organisation=org)
        payload = {
            "period_type": "MONTH",
            "period_start": "2026-04-01",  # past
            "target_count": 100,
        }
        resp = client.post(f"/api/v1/shops/{shop.pk}/targets/", payload, format="json")
        assert resp.status_code == 400

    def test_duplicate_returns_400(self, org_admin_client, bypass_session_auth):
        org, _admin, client = org_admin_client
        shop = ShopFactory(organisation=org)
        ReviewTargetFactory(
            shop=shop,
            organisation=org,
            period_type=ReviewTarget.PeriodType.MONTH,
            period_start=datetime.date(2026, 5, 1),
        )
        payload = {"period_type": "MONTH", "period_start": "2026-05-01", "target_count": 999}
        resp = client.post(f"/api/v1/shops/{shop.pk}/targets/", payload, format="json")
        assert resp.status_code == 400

    def test_target_count_zero_returns_400(self, org_admin_client, bypass_session_auth):
        org, _admin, client = org_admin_client
        shop = ShopFactory(organisation=org)
        payload = {"period_type": "MONTH", "period_start": "2026-06-01", "target_count": 0}
        resp = client.post(f"/api/v1/shops/{shop.pk}/targets/", payload, format="json")
        assert resp.status_code == 400


@pytest.mark.django_db
class TestTargetUpdate:
    def test_org_admin_updates_count(self, org_admin_client, bypass_session_auth):
        org, _admin, client = org_admin_client
        shop = ShopFactory(organisation=org)
        t = ReviewTargetFactory(shop=shop, organisation=org, target_count=100)
        resp = client.patch(
            f"/api/v1/shops/{shop.pk}/targets/{t.pk}/",
            {"target_count": 300},
            format="json",
        )
        assert resp.status_code == 200
        t.refresh_from_db()
        assert t.target_count == 300

    def test_staff_cannot_update(self, staff_client, bypass_session_auth):
        org, _staff, client = staff_client
        shop = ShopFactory(organisation=org)
        t = ReviewTargetFactory(shop=shop, organisation=org)
        resp = client.patch(
            f"/api/v1/shops/{shop.pk}/targets/{t.pk}/",
            {"target_count": 999},
            format="json",
        )
        assert resp.status_code == 403

    def test_org_isolation(self, org_admin_client, bypass_session_auth):
        _org, _admin, client = org_admin_client
        other_shop = ShopFactory()
        t = ReviewTargetFactory(shop=other_shop, organisation=other_shop.organisation)
        resp = client.patch(
            f"/api/v1/shops/{other_shop.pk}/targets/{t.pk}/",
            {"target_count": 999},
            format="json",
        )
        assert resp.status_code in (403, 404)


@pytest.mark.django_db
class TestTargetDelete:
    def test_org_admin_deletes(self, org_admin_client, bypass_session_auth):
        org, _admin, client = org_admin_client
        shop = ShopFactory(organisation=org)
        t = ReviewTargetFactory(shop=shop, organisation=org)
        resp = client.delete(f"/api/v1/shops/{shop.pk}/targets/{t.pk}/")
        assert resp.status_code == 204
        assert not ReviewTarget.objects.filter(pk=t.pk).exists()

    def test_staff_cannot_delete(self, staff_client, bypass_session_auth):
        org, _staff, client = staff_client
        shop = ShopFactory(organisation=org)
        t = ReviewTargetFactory(shop=shop, organisation=org)
        resp = client.delete(f"/api/v1/shops/{shop.pk}/targets/{t.pk}/")
        assert resp.status_code == 403
