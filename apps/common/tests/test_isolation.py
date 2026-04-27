"""Cross-tenant isolation scaffold (XMOD-05).

Phase 6 establishes the test pattern. Phases 7-9 add per-resource cross-tenant
assertions for list, detail, and mutation endpoints.
"""

from __future__ import annotations

import pytest
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext

pytestmark = pytest.mark.django_db


def test_org_admin_dashboard_scoped_to_own_organisation(two_orgs_two_admins) -> None:
    """admin_a sees org_a in dashboard context, not org_b."""
    client = Client()
    client.force_login(two_orgs_two_admins["admin_a"])
    response = client.get("/admin/org-dashboard/")
    assert response.status_code == 200
    assert response.context["organisation"].pk == two_orgs_two_admins["org_a"].pk
    assert response.context["organisation"].pk != two_orgs_two_admins["org_b"].pk


def test_two_admins_cannot_see_each_others_organisation(two_orgs_two_admins) -> None:
    """admin_b sees org_b (not org_a) when hitting same dashboard URL."""
    client = Client()
    client.force_login(two_orgs_two_admins["admin_b"])
    response = client.get("/admin/org-dashboard/")
    assert response.status_code == 200
    assert response.context["organisation"].pk == two_orgs_two_admins["org_b"].pk


def test_assert_query_ceiling_passes_under_limit(two_orgs_two_admins, assert_query_ceiling) -> None:
    """Sanity check: assert_query_ceiling is callable and reports counts."""
    client = Client()
    client.force_login(two_orgs_two_admins["admin_a"])
    with CaptureQueriesContext(connection) as ctx:
        client.get("/admin/org-dashboard/")
    # Generous ceiling — Phase 6 dashboard is small; Phase 7+ tests will tighten this
    assert_query_ceiling(ctx, max_queries=20)


def test_assert_query_ceiling_raises_when_over_limit(
    two_orgs_two_admins, assert_query_ceiling
) -> None:
    """assert_query_ceiling must fail loudly when count exceeds the ceiling."""
    client = Client()
    client.force_login(two_orgs_two_admins["admin_a"])
    with CaptureQueriesContext(connection) as ctx:
        client.get("/admin/org-dashboard/")
    with pytest.raises(AssertionError, match="exceeds ceiling 0"):
        assert_query_ceiling(ctx, max_queries=0)
