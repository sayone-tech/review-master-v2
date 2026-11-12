"""Phase 35 task 1 - platform-level (organisation NULL) audit rows never reach tenants."""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import StaffAccessScope, User
from apps.accounts.tests.factories import OrgAdminFactory, StaffAdminFactory, UserFactory
from apps.common.models import AuditLog
from apps.common.selectors.audit_logs import list_audit_logs_for_org, list_audit_logs_for_staff
from apps.organisations.tests.factories import OrganisationFactory
from apps.reviews.tests.factories import AuditLogFactory, ReviewFactory
from apps.shops.tests.factories import ShopFactory

pytestmark = pytest.mark.django_db


def test_audit_log_organisation_is_nullable():
    row = AuditLog.objects.create(
        organisation=None, entity_type="ai_pricing", entity_id="1", action="ai_pricing.added"
    )
    row.refresh_from_db()
    assert row.organisation_id is None


def test_platform_audit_rows_never_in_tenant_activity_log():
    AuditLog.objects.create(
        organisation=None, entity_type="ai_pricing", entity_id="1", action="ai_pricing.added"
    )
    org = OrganisationFactory()
    org_admin = OrgAdminFactory(organisation=org)
    AuditLogFactory(organisation=org)
    qs = list_audit_logs_for_org(organisation_id=org_admin.organisation_id)
    assert not qs.filter(organisation__isnull=True).exists()
    assert not qs.filter(entity_type="ai_pricing").exists()
    assert qs.count() == 1

    client = APIClient()
    client.force_authenticate(user=org_admin)
    resp = client.get("/api/v1/audit-logs/")
    assert resp.status_code == 200
    actions = [r["action"] for r in resp.json()["results"]]
    assert "ai_pricing.added" not in actions
    assert actions == ["reply_posted"]


@pytest.fixture
def platform_setup():
    """A tenant (org admin + scoped staff) plus platform rows a superadmin wrote.

    One platform row is deliberately shaped like a tenant row (entity_type="review" with the
    PK of a review the staff user can see) so only the organisation guard keeps it out.
    """
    superadmin = UserFactory(role=User.Role.SUPERADMIN, organisation=None, full_name="Price Op")
    org = OrganisationFactory()
    shop = ShopFactory(organisation=org)
    review = ReviewFactory(organisation=org, shop=shop)
    org_admin = OrgAdminFactory(organisation=org)
    staff = StaffAdminFactory(organisation=org)
    StaffAccessScope.objects.create(
        user=staff, scope_type=StaffAccessScope.ScopeType.SHOP, shop=shop
    )
    AuditLog.objects.create(
        organisation=None,
        actor=superadmin,
        entity_type="ai_pricing",
        entity_id="1",
        action="ai_pricing.added",
    )
    AuditLog.objects.create(
        organisation=None,
        actor=superadmin,
        entity_type="review",
        entity_id=str(review.pk),
        action="reply_posted",
    )
    tenant_row = AuditLogFactory(organisation=org, entity_type="review", entity_id=str(review.pk))
    return {
        "superadmin": superadmin,
        "org_admin": org_admin,
        "staff": staff,
        "tenant_row": tenant_row,
    }


def test_selectors_return_empty_when_organisation_id_is_none(platform_setup):
    staff = platform_setup["staff"]
    assert not list_audit_logs_for_org(organisation_id=None).exists()
    assert not list_audit_logs_for_staff(organisation_id=None, user=staff).exists()


def test_staff_selector_never_returns_platform_rows(platform_setup):
    staff = platform_setup["staff"]
    qs = list_audit_logs_for_staff(organisation_id=staff.organisation_id, user=staff)
    assert list(qs) == [platform_setup["tenant_row"]]


def test_staff_api_never_returns_platform_rows(platform_setup):
    client = APIClient()
    client.force_authenticate(user=platform_setup["staff"])
    resp = client.get("/api/v1/audit-logs/")
    assert resp.status_code == 200
    ids = [r["id"] for r in resp.json()["results"]]
    assert ids == [platform_setup["tenant_row"].pk]


def test_superadmin_cannot_read_platform_rows_via_tenant_api(platform_setup):
    client = APIClient()
    client.force_authenticate(user=platform_setup["superadmin"])
    resp = client.get("/api/v1/audit-logs/")
    assert resp.status_code == 403


@pytest.mark.parametrize("role_key", ["org_admin", "staff"])
def test_activity_log_actor_dropdown_excludes_pricing_superadmin(platform_setup, role_key):
    client = APIClient()
    client.force_login(platform_setup[role_key])
    resp = client.get("/admin/org/activity-log/")
    assert resp.status_code == 200
    assert resp.context["actors_json"] == []
