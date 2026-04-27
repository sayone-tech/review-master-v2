from __future__ import annotations

import pytest
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext

from apps.organisations.models import Organisation
from apps.organisations.tests.factories import OrganisationFactory

pytestmark = pytest.mark.django_db


def test_org_list_template_requires_auth(client):
    """Anonymous request to org list template should redirect to /login/ (ORGL-01)."""
    resp = client.get("/admin/organisations/")
    assert resp.status_code == 302
    assert "/login/" in resp["Location"]


def test_org_list_template_renders_200_for_superadmin(client_logged_in):
    """Superadmin can access org list template and it renders correctly (ORGL-01)."""
    # Create an org so the else branch (table mount point) renders
    OrganisationFactory()
    resp = client_logged_in.get("/admin/organisations/")
    assert resp.status_code == 200
    assert b'id="org-data"' in resp.content
    assert b'id="org-table-root"' in resp.content


def test_org_list_template_embeds_orgs_json(client_logged_in, three_orgs):
    """Org list template contains embedded JSON blob with org data (ORGL-02)."""
    resp = client_logged_in.get("/admin/organisations/")
    # Django may HTML-escape the JSON; check both forms
    assert b'"name": "Alpha Retail"' in resp.content or (
        b"&quot;name&quot;: &quot;Alpha Retail&quot;" in resp.content
    )


def test_org_list_template_per_page_default_10(client_logged_in):
    """Default pagination is 10 per page (ORGL-06)."""
    OrganisationFactory.create_batch(15)
    resp = client_logged_in.get("/admin/organisations/")
    assert resp.context["per_page"] == 10


def test_org_list_template_per_page_25_respected(client_logged_in):
    """per_page=25 query param is respected (ORGL-06)."""
    OrganisationFactory.create_batch(30)
    resp = client_logged_in.get("/admin/organisations/?per_page=25")
    assert resp.context["per_page"] == 25


def test_org_list_template_per_page_invalid_falls_back_to_10(client_logged_in):
    """Invalid per_page value falls back to 10 (ORGL-06)."""
    resp = client_logged_in.get("/admin/organisations/?per_page=999")
    assert resp.context["per_page"] == 10


def test_org_list_empty_state_renders_when_no_orgs(client_logged_in):
    """Empty state message is shown when no organisations exist (ORGL-07)."""
    resp = client_logged_in.get("/admin/organisations/")
    assert b"No organisations yet" in resp.content


def test_org_list_filter_by_status_returns_filtered_orgs(client_logged_in, three_orgs):
    resp = client_logged_in.get("/admin/organisations/?status=ACTIVE")
    assert resp.status_code == 200
    assert resp.context["current_status"] == "ACTIVE"
    # three_orgs has 2 ACTIVE, 1 DISABLED
    assert resp.context["page_obj"].paginator.count == 2


def test_org_list_pagination_preserves_filter_params(client_logged_in):
    OrganisationFactory.create_batch(30)
    resp = client_logged_in.get("/admin/organisations/?search=Org&per_page=25&page=2")
    # page_url_params should include search and per_page but not the `page` key
    from urllib.parse import parse_qs

    params = resp.context["page_url_params"]
    parsed = parse_qs(params)
    assert "search=Org" in params
    assert "per_page=25" in params
    assert "page" not in parsed


def test_api_list_organisations_query_count_ceiling(api_client_superadmin):
    """API list endpoint hits no more than 7 queries regardless of result set size (ORGL-08)."""
    OrganisationFactory.create_batch(25)
    with CaptureQueriesContext(connection) as ctx:
        resp = api_client_superadmin.get("/api/v1/organisations/")
    assert resp.status_code == 200
    assert (
        len(ctx.captured_queries) <= 7
    )  # auth + session + org list + prefetch + count + savepoints


def test_api_create_organisation_returns_201(api_client_superadmin):
    """POST to org API creates an organisation and returns 201 (CORG-01)."""
    resp = api_client_superadmin.post(
        "/api/v1/organisations/",
        {
            "name": "Acme",
            "org_type": "RETAIL",
            "email": "acme@example.com",
            "address": "",
            "number_of_stores": 5,
        },
        format="json",
    )
    assert resp.status_code == 201


def test_api_create_organisation_duplicate_email_returns_400(api_client_superadmin):
    """Duplicate email on POST returns 400 with email field error (CORG-02)."""
    OrganisationFactory(email="dup@example.com")
    resp = api_client_superadmin.post(
        "/api/v1/organisations/",
        {
            "name": "Dup",
            "org_type": "RETAIL",
            "email": "dup@example.com",
            "address": "",
            "number_of_stores": 1,
        },
        format="json",
    )
    assert resp.status_code == 400
    assert "email" in resp.json()


def test_api_update_organisation_email_field_is_ignored(api_client_superadmin):
    """PATCH with email field does not change the stored email (EORG-02)."""
    org = OrganisationFactory(email="orig@example.com")
    resp = api_client_superadmin.patch(
        f"/api/v1/organisations/{org.id}/",
        {"email": "hack@example.com", "name": "Renamed"},
        format="json",
    )
    assert resp.status_code in (200, 202)
    org.refresh_from_db()
    assert org.email == "orig@example.com"
    assert org.name == "Renamed"


def test_api_delete_organisation_soft_deletes(api_client_superadmin):
    """DELETE soft-deletes the organisation (sets status=DELETED) rather than removing (DORG-01/02)."""
    org = OrganisationFactory()
    resp = api_client_superadmin.delete(f"/api/v1/organisations/{org.id}/")
    assert resp.status_code in (204, 200)
    org.refresh_from_db()
    assert org.status == Organisation.Status.DELETED


def test_api_organisations_requires_authentication(anon_api_client):
    """Unauthenticated request to org API returns 401 or 403."""
    resp = anon_api_client.get("/api/v1/organisations/")
    assert resp.status_code in (401, 403)


def test_api_organisations_rejects_non_superadmin(api_client_orgadmin):
    """Org Admin role is rejected from org API with 403."""
    resp = api_client_orgadmin.get("/api/v1/organisations/")
    assert resp.status_code == 403


def test_api_enable_disable_via_patch_status(api_client_superadmin):
    """PATCH with status=DISABLED disables an active organisation (ENBL-01)."""
    org = OrganisationFactory(status=Organisation.Status.ACTIVE)
    resp = api_client_superadmin.patch(
        f"/api/v1/organisations/{org.id}/",
        {"status": "DISABLED"},
        format="json",
    )
    assert resp.status_code in (200, 202)
    org.refresh_from_db()
    assert org.status == Organisation.Status.DISABLED


def test_api_retrieve_organisation_returns_activation_status(api_client_superadmin):
    org = OrganisationFactory()
    resp = api_client_superadmin.get(f"/api/v1/organisations/{org.id}/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["activation_status"] in ("pending", "active", "expired")
    assert "last_invited_at" in body


def test_api_list_organisations_respects_search_filter(api_client_superadmin, three_orgs):
    resp = api_client_superadmin.get("/api/v1/organisations/?search=alpha")
    assert resp.status_code == 200
    results = resp.json()["results"]
    assert len(results) == 1
    assert results[0]["name"] == "Alpha Retail"


def test_api_create_organisation_sends_invitation_email_on_success(api_client_superadmin):
    from django.core import mail

    resp = api_client_superadmin.post(
        "/api/v1/organisations/",
        {
            "name": "Invite Co",
            "org_type": "RETAIL",
            "email": "invite@example.com",
            "address": "",
            "number_of_stores": 3,
        },
        format="json",
    )
    assert resp.status_code == 201
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ["invite@example.com"]
    assert "Invite Co" in mail.outbox[0].subject


def test_api_adjust_store_allocation_via_patch_number_of_stores(api_client_superadmin):
    org = OrganisationFactory(number_of_stores=5)
    resp = api_client_superadmin.patch(
        f"/api/v1/organisations/{org.id}/",
        {"number_of_stores": 25},
        format="json",
    )
    assert resp.status_code in (200, 202)
    org.refresh_from_db()
    assert org.number_of_stores == 25


# --- Phase 4 Plan 01: Org Admin dashboard stub ---


def test_org_admin_dashboard_url_name_resolves() -> None:
    from django.urls import reverse

    assert reverse("org_admin_dashboard") == "/admin/org-dashboard/"


def test_org_admin_dashboard_anonymous_redirects_to_login(client):
    resp = client.get("/admin/org-dashboard/")
    assert resp.status_code == 302
    assert "/login/" in resp["Location"]
    assert "next=/admin/org-dashboard/" in resp["Location"]


def test_org_admin_dashboard_superadmin_redirects_to_organisations(client_logged_in):
    resp = client_logged_in.get("/admin/org-dashboard/")
    assert resp.status_code == 302
    assert resp["Location"] == "/admin/organisations/"


def test_org_admin_dashboard_org_admin_without_org_redirects_to_login(client, db):
    from apps.accounts.models import User
    from apps.accounts.tests.factories import UserFactory

    user = UserFactory(role=User.Role.ORG_ADMIN, organisation=None, email="orphan@example.com")
    client.force_login(user)
    resp = client.get("/admin/org-dashboard/")
    assert resp.status_code == 302
    assert "/login/" in resp["Location"]


def test_org_admin_dashboard_org_admin_sees_welcome_card(client, db):
    from apps.accounts.models import User
    from apps.accounts.tests.factories import UserFactory

    org = OrganisationFactory(name="Acme Holdings")
    user = UserFactory(role=User.Role.ORG_ADMIN, organisation=org, email="admin@acme.com")
    client.force_login(user)
    resp = client.get("/admin/org-dashboard/")
    assert resp.status_code == 200
    assert b"Welcome to Acme Holdings" in resp.content
    assert b'data-testid="org-dashboard-card"' in resp.content


def test_org_admin_dashboard_renders_org_sidebar_not_superadmin_sidebar(client, db):
    from apps.accounts.models import User
    from apps.accounts.tests.factories import UserFactory

    org = OrganisationFactory(name="Acme Holdings")
    user = UserFactory(role=User.Role.ORG_ADMIN, organisation=org, email="admin2@acme.com")
    client.force_login(user)
    resp = client.get("/admin/org-dashboard/")
    assert resp.status_code == 200
    # Proves base_org.html shell was rendered (sidebar testid present)
    assert b'data-testid="sidebar"' in resp.content
    # Proves Superadmin-only "Organisations" nav href not present in the rendered sidebar
    # (Org Admin sidebar only has Dashboard + Profile links)
    assert b"/admin/organisations/" not in resp.content


# --- Phase 4 Plan 04: resend-invitation @action ---


def test_resend_invitation_endpoint_superadmin_success(client_logged_in, db):
    from django.core import mail

    from apps.accounts.models import InvitationToken

    org = OrganisationFactory(email="endpoint-ok@example.com")
    resp = client_logged_in.post(f"/api/v1/organisations/{org.id}/resend-invitation/")
    assert resp.status_code == 200
    assert resp.json() == {"detail": "Invitation resent."}
    assert InvitationToken.objects.filter(organisation=org, is_used=False).count() == 1
    assert len(mail.outbox) == 1


def test_resend_invitation_endpoint_anonymous_forbidden(client, db):
    org = OrganisationFactory(email="anon@example.com")
    resp = client.post(f"/api/v1/organisations/{org.id}/resend-invitation/")
    assert resp.status_code in (
        401,
        403,
    )  # DRF session auth returns 403 by default for unauthenticated


def test_resend_invitation_endpoint_org_admin_forbidden(client, db):
    from apps.accounts.models import User
    from apps.accounts.tests.factories import UserFactory

    org = OrganisationFactory(email="forbidden@example.com")
    org_admin = UserFactory(role=User.Role.ORG_ADMIN, organisation=org, email="oa@example.com")
    client.force_login(org_admin)
    resp = client.post(f"/api/v1/organisations/{org.id}/resend-invitation/")
    assert resp.status_code == 403


def test_resend_invitation_endpoint_not_found(client_logged_in, db):
    resp = client_logged_in.post("/api/v1/organisations/99999/resend-invitation/")
    assert resp.status_code == 404


def test_resend_invitation_endpoint_get_method_not_allowed(client_logged_in, db):
    org = OrganisationFactory(email="method@example.com")
    resp = client_logged_in.get(f"/api/v1/organisations/{org.id}/resend-invitation/")
    assert resp.status_code == 405


def test_resend_invitation_endpoint_delete_method_not_allowed(client_logged_in, db):
    org = OrganisationFactory(email="method-del@example.com")
    resp = client_logged_in.delete(f"/api/v1/organisations/{org.id}/resend-invitation/")
    assert resp.status_code == 405


def test_resend_invitation_endpoint_invalidates_existing_token(client_logged_in, db):
    from apps.accounts.models import InvitationToken
    from apps.accounts.tests.factories import InvitationTokenFactory

    org = OrganisationFactory(email="invalidate@example.com")
    old = InvitationTokenFactory(organisation=org, is_used=False)
    resp = client_logged_in.post(f"/api/v1/organisations/{org.id}/resend-invitation/")
    assert resp.status_code == 200
    old.refresh_from_db()
    assert old.is_used is True
    assert InvitationToken.objects.filter(organisation=org).count() == 2


def test_resend_invitation_url_name_resolves():
    from django.urls import reverse

    assert (
        reverse("organisation-resend-invitation", kwargs={"pk": 1})
        == "/api/v1/organisations/1/resend-invitation/"
    )


# --- Phase 6 Plan 03: Org Admin sidebar + stub pages ---


def _org_admin_client():
    from apps.accounts.models import User
    from apps.accounts.tests.factories import UserFactory

    org = OrganisationFactory()
    user = UserFactory(role=User.Role.ORG_ADMIN, organisation=org)
    client = Client()
    client.force_login(user)
    return client, user, org


def test_org_admin_dashboard_v02_alias_resolves() -> None:
    client, _, _ = _org_admin_client()
    response = client.get("/admin/org/dashboard/")
    assert response.status_code == 200


def test_legacy_org_admin_dashboard_url_still_works() -> None:
    """invite_accept_view's reverse('org_admin_dashboard') MUST keep resolving."""
    from django.urls import reverse

    assert reverse("org_admin_dashboard") == "/admin/org-dashboard/"
    client, _, _ = _org_admin_client()
    response = client.get("/admin/org-dashboard/")
    assert response.status_code == 200


def test_sidebar_renders_six_items_in_order() -> None:
    client, _, _ = _org_admin_client()
    response = client.get("/admin/org/dashboard/")
    html = response.content.decode("utf-8")
    # All six labels present
    for label in ["Dashboard", "Shops", "Regions", "Team", "Profile", "Log out"]:
        assert label in html, f"Sidebar missing label: {label}"
    # Order check — find positions, must be ascending
    positions = [
        html.find(">Dashboard<"),
        html.find(">Shops<"),
        html.find(">Regions<"),
        html.find(">Team<"),
        html.find(">Profile<"),
    ]
    assert all(p > 0 for p in positions), f"Some labels not found: {positions}"
    assert positions == sorted(positions), f"Sidebar items out of order: {positions}"


def test_sidebar_contains_six_lucide_icons() -> None:
    client, _, _ = _org_admin_client()
    response = client.get("/admin/org/dashboard/")
    html = response.content.decode("utf-8")
    for icon in [
        "layout-dashboard",
        "store",
        "map-pin",
        "users",
        "user",
        "log-out",
    ]:
        assert f'data-lucide="{icon}"' in html, f"Missing icon: {icon}"


def test_sidebar_uses_new_alias_urls() -> None:
    client, _, _ = _org_admin_client()
    response = client.get("/admin/org/dashboard/")
    html = response.content.decode("utf-8")
    assert 'href="/admin/org/dashboard/"' in html
    assert 'href="/admin/org/shops/"' in html
    assert 'href="/admin/org/regions/"' in html
    assert 'href="/admin/org/team/"' in html
    assert 'href="/admin/org/profile/"' in html


def test_org_stub_view_renders_regions_section() -> None:
    client, _, _ = _org_admin_client()
    response = client.get("/admin/org/regions/")
    assert response.status_code == 200
    assert b"Regions" in response.content
    assert b"This section is coming soon." in response.content


def test_org_stub_view_renders_shops_section() -> None:
    client, _, _ = _org_admin_client()
    response = client.get("/admin/org/shops/")
    assert response.status_code == 200
    assert b"Shops" in response.content


def test_org_stub_view_renders_team_section() -> None:
    client, _, _ = _org_admin_client()
    response = client.get("/admin/org/team/")
    assert response.status_code == 200
    assert b"Team" in response.content


def test_org_stub_view_returns_403_for_superadmin() -> None:
    from apps.accounts.models import User
    from apps.accounts.tests.factories import UserFactory

    user = UserFactory(role=User.Role.SUPERADMIN)
    client = Client()
    client.force_login(user)
    response = client.get("/admin/org/regions/")
    assert response.status_code == 403


def test_org_stub_view_returns_403_for_staff_admin() -> None:
    from apps.accounts.models import User
    from apps.accounts.tests.factories import UserFactory

    org = OrganisationFactory()
    user = UserFactory(role=User.Role.STAFF_ADMIN, organisation=org)
    client = Client()
    client.force_login(user)
    response = client.get("/admin/org/team/")
    assert response.status_code == 403


def test_named_url_patterns_resolve_correctly() -> None:
    from django.urls import reverse

    assert reverse("org_regions") == "/admin/org/regions/"
    assert reverse("org_shops") == "/admin/org/shops/"
    assert reverse("org_team") == "/admin/org/team/"
