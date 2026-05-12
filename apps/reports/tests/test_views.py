"""Tests for apps.reports API view."""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.tests.factories import OrgAdminFactory, StaffAdminFactory
from apps.dashboard.tests.conftest import make_review
from apps.organisations.tests.factories import OrganisationFactory
from apps.reviews.models import Review
from apps.shops.tests.factories import ShopFactory

SUCCESS = Review.EnrichmentStatus.SUCCESS


@pytest.fixture
def org():
    return OrganisationFactory()


@pytest.fixture
def org_admin(org):
    return OrgAdminFactory(organisation=org, role=User.Role.ORG_ADMIN)


@pytest.fixture
def staff_admin(org):
    return StaffAdminFactory(organisation=org, role=User.Role.STAFF_ADMIN)


@pytest.fixture
def client():
    return APIClient()


@pytest.mark.django_db
def test_org_admin_gets_200(client, org_admin, org):
    shop = ShopFactory(organisation=org)
    make_review(shop=shop, star_rating=4, enrichment_status=SUCCESS)
    client.force_authenticate(user=org_admin)

    resp = client.get("/api/v1/reports/stores/")

    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["shop_name"] == shop.name


@pytest.mark.django_db
def test_staff_admin_gets_403(client, staff_admin):
    client.force_authenticate(user=staff_admin)

    resp = client.get("/api/v1/reports/stores/")

    assert resp.status_code == 403


@pytest.mark.django_db
def test_unauthenticated_gets_403(client):
    resp = client.get("/api/v1/reports/stores/")
    assert resp.status_code == 403


@pytest.mark.django_db
def test_invalid_range_returns_400(client, org_admin):
    client.force_authenticate(user=org_admin)

    resp = client.get("/api/v1/reports/stores/?range=custom")

    assert resp.status_code == 400


@pytest.mark.django_db
def test_reply_status_filter_forwarded(client, org_admin, org):
    shop = ShopFactory(organisation=org)
    r = make_review(shop=shop, star_rating=5, enrichment_status=SUCCESS)
    r.is_replied = True
    r.save(update_fields=["is_replied"])
    make_review(shop=shop, star_rating=2, enrichment_status=SUCCESS)
    client.force_authenticate(user=org_admin)

    resp = client.get("/api/v1/reports/stores/?reply_status=replied")

    assert resp.status_code == 200
    assert resp.json()[0]["total_reviews"] == 1


@pytest.mark.django_db
def test_sentiment_filter_forwarded(client, org_admin, org):
    shop = ShopFactory(organisation=org)
    make_review(shop=shop, star_rating=5, sentiment="positive", enrichment_status=SUCCESS)
    make_review(shop=shop, star_rating=1, sentiment="negative", enrichment_status=SUCCESS)
    client.force_authenticate(user=org_admin)

    resp = client.get("/api/v1/reports/stores/?sentiment=negative")

    assert resp.status_code == 200
    assert resp.json()[0]["total_reviews"] == 1
