import pytest
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.tests.factories import OrgAdminFactory, StaffAdminFactory, UserFactory
from apps.insights.tests.factories import InsightSnapshotFactory
from apps.insights.tests.test_selectors import _item
from apps.organisations.tests.factories import OrganisationFactory
from apps.reviews.models import OrgCanonicalTag
from apps.shops.tests.factories import ShopFactory

pytestmark = pytest.mark.django_db
URL = "/api/v1/insights/"


@pytest.fixture
def org():
    return OrganisationFactory(name="Acme")


def _login(user):
    c = APIClient()
    c.force_login(user)
    return c


def test_shape_for_org_admin(org):
    shop = ShopFactory(organisation=org, name="Soho")
    OrgCanonicalTag.objects.create(organisation=org, label="Slow")
    InsightSnapshotFactory(
        organisation=org,
        payload={
            "cover": {"reviews": 10, "stores": 1, "attention": 1, "good": 0},
            "items": [_item(store_id=shop.id, tag_text="Slow")],
        },
    )
    user = OrgAdminFactory(organisation=org, role=User.Role.ORG_ADMIN)
    r = _login(user).get(URL)
    assert r.status_code == 200
    data = r.json()
    assert set(data) == {"cover", "window", "items"}
    assert data["cover"]["organisation"] == "Acme"
    assert set(data["window"]) == {"from", "to"}
    assert set(data["items"][0]) == {
        "type", "chapter", "headline", "title", "body", "visual",
        "link", "store", "cta", "caption",
    }  # fmt: skip
    assert data["items"][0]["title"] == "Slow complaints at Soho"


def test_query_count_fixed_regardless_of_items(org):
    shop = ShopFactory(organisation=org)
    OrgCanonicalTag.objects.create(organisation=org, label="T")
    InsightSnapshotFactory(
        organisation=org,
        payload={"cover": {}, "items": [_item(store_id=shop.id, tag_text="T")] * 8},
    )
    user = OrgAdminFactory(organisation=org, role=User.Role.ORG_ADMIN)
    c = _login(user)
    c.get(URL)
    with CaptureQueriesContext(connection) as ctx:
        c.get(URL)
    assert len(ctx.captured_queries) <= 5  # +1: org canonical-tag labels (spec 2.8)


def test_empty_without_snapshot(org):
    user = OrgAdminFactory(organisation=org, role=User.Role.ORG_ADMIN)
    r = _login(user).get(URL)
    assert r.status_code == 200
    assert r.json() == {"cover": None, "window": None, "items": []}


def test_staff_forbidden(org):
    user = StaffAdminFactory(organisation=org, role=User.Role.STAFF_ADMIN)
    assert _login(user).get(URL).status_code == 403


def test_superadmin_forbidden():
    user = UserFactory(role=User.Role.SUPERADMIN, organisation=None)
    assert _login(user).get(URL).status_code == 403


def test_unauthenticated_rejected():
    assert APIClient().get(URL).status_code in (401, 403)


def test_page_org_admin_ok_and_staff_blocked(org):
    admin = OrgAdminFactory(organisation=org, role=User.Role.ORG_ADMIN)
    c = Client()
    c.force_login(admin)
    r = c.get("/admin/org/insights/")
    assert r.status_code == 200
    assert b'id="insights-root"' in r.content
    staff = StaffAdminFactory(organisation=org, role=User.Role.STAFF_ADMIN)
    c2 = Client()
    c2.force_login(staff)
    assert c2.get("/admin/org/insights/").status_code in (302, 403)
