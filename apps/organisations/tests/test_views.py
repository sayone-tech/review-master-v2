from __future__ import annotations

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.organisations.models import Organisation
from apps.organisations.tests.factories import OrganisationFactory

pytestmark = pytest.mark.django_db

WAVE_0_TPL = pytest.mark.xfail(
    strict=False, reason="Wave 0 scaffold — implemented in Plan 02 (template view)"
)
WAVE_0_API = pytest.mark.xfail(
    strict=False, reason="Wave 0 scaffold — implemented in Plan 03 (viewset)"
)


@WAVE_0_TPL
def test_org_list_template_requires_auth(client):
    """Anonymous request to org list template should redirect to /login/ (ORGL-01)."""
    resp = client.get("/admin/organisations/")
    assert resp.status_code == 302
    assert "/login/" in resp["Location"]


@WAVE_0_TPL
def test_org_list_template_renders_200_for_superadmin(client_logged_in):
    """Superadmin can access org list template and it renders correctly (ORGL-01)."""
    resp = client_logged_in.get("/admin/organisations/")
    assert resp.status_code == 200
    assert b'id="org-data"' in resp.content
    assert b'id="org-table-root"' in resp.content


@WAVE_0_TPL
def test_org_list_template_embeds_orgs_json(client_logged_in, three_orgs):
    """Org list template contains embedded JSON blob with org data (ORGL-02)."""
    resp = client_logged_in.get("/admin/organisations/")
    # Django may HTML-escape the JSON; check both forms
    assert b'"name": "Alpha Retail"' in resp.content or (
        b"&quot;name&quot;: &quot;Alpha Retail&quot;" in resp.content
    )


@WAVE_0_TPL
def test_org_list_template_per_page_default_10(client_logged_in):
    """Default pagination is 10 per page (ORGL-06)."""
    OrganisationFactory.create_batch(15)
    resp = client_logged_in.get("/admin/organisations/")
    assert resp.context["per_page"] == 10


@WAVE_0_TPL
def test_org_list_template_per_page_25_respected(client_logged_in):
    """per_page=25 query param is respected (ORGL-06)."""
    OrganisationFactory.create_batch(30)
    resp = client_logged_in.get("/admin/organisations/?per_page=25")
    assert resp.context["per_page"] == 25


@WAVE_0_TPL
def test_org_list_template_per_page_invalid_falls_back_to_10(client_logged_in):
    """Invalid per_page value falls back to 10 (ORGL-06)."""
    resp = client_logged_in.get("/admin/organisations/?per_page=999")
    assert resp.context["per_page"] == 10


@WAVE_0_TPL
def test_org_list_empty_state_renders_when_no_orgs(client_logged_in):
    """Empty state message is shown when no organisations exist (ORGL-07)."""
    resp = client_logged_in.get("/admin/organisations/")
    assert b"No organisations yet" in resp.content


@WAVE_0_API
def test_api_list_organisations_query_count_ceiling(api_client_superadmin):
    """API list endpoint hits no more than 7 queries regardless of result set size (ORGL-08)."""
    OrganisationFactory.create_batch(25)
    with CaptureQueriesContext(connection) as ctx:
        resp = api_client_superadmin.get("/api/v1/organisations/")
    assert resp.status_code == 200
    assert (
        len(ctx.captured_queries) <= 7
    )  # auth + session + org list + prefetch + count + savepoints


@WAVE_0_API
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


@WAVE_0_API
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


@WAVE_0_API
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


@WAVE_0_API
def test_api_delete_organisation_soft_deletes(api_client_superadmin):
    """DELETE soft-deletes the organisation (sets status=DELETED) rather than removing (DORG-01/02)."""
    org = OrganisationFactory()
    resp = api_client_superadmin.delete(f"/api/v1/organisations/{org.id}/")
    assert resp.status_code in (204, 200)
    org.refresh_from_db()
    assert org.status == Organisation.Status.DELETED


@WAVE_0_API
def test_api_organisations_requires_authentication(anon_api_client):
    """Unauthenticated request to org API returns 401 or 403."""
    resp = anon_api_client.get("/api/v1/organisations/")
    assert resp.status_code in (401, 403)


@WAVE_0_API
def test_api_organisations_rejects_non_superadmin(api_client_orgadmin):
    """Org Admin role is rejected from org API with 403."""
    resp = api_client_orgadmin.get("/api/v1/organisations/")
    assert resp.status_code == 403


@WAVE_0_API
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
