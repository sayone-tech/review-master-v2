"""Phase 35 task 1 - platform-level (organisation NULL) audit rows never reach tenants."""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.accounts.tests.factories import OrgAdminFactory
from apps.common.models import AuditLog
from apps.common.selectors.audit_logs import list_audit_logs_for_org
from apps.organisations.tests.factories import OrganisationFactory
from apps.reviews.tests.factories import AuditLogFactory

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
