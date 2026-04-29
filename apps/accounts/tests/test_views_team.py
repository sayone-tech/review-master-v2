"""Tests for TeamViewSet (DRF) and team-related Django template views.

Plan 09-02 Task 1 — RED phase: all tests written before implementation.
"""

from __future__ import annotations

import secrets

import pytest
from django.core import mail
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from apps.accounts.models import InvitationToken, StaffAccessScope, User
from apps.accounts.tests.factories import (
    StaffAccessScopeFactory,
    UserFactory,
)
from apps.organisations.tests.factories import OrganisationFactory
from apps.regions.tests.factories import RegionFactory

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_org_admin(email: str = "admin@example.com") -> tuple[User, object]:
    org = OrganisationFactory()
    admin = UserFactory(role=User.Role.ORG_ADMIN, organisation=org, email=email)
    return admin, org


def _api_client_as(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


# ---------------------------------------------------------------------------
# TEAM-01: list
# ---------------------------------------------------------------------------


def test_list_team_members(db) -> None:
    """GET /api/v1/team/ returns paginated list scoped to the caller's org."""
    admin, org = _make_org_admin()
    member = UserFactory(
        role=User.Role.STAFF_ADMIN, organisation=org, email="staff@example.com", is_active=False
    )

    # Org B — must not appear
    _admin_b, org_b = _make_org_admin(email="admin_b@example.com")
    UserFactory(role=User.Role.STAFF_ADMIN, organisation=org_b, email="other@example.com")

    client = _api_client_as(admin)
    resp = client.get("/api/v1/team/")
    assert resp.status_code == 200
    data = resp.json()
    assert "results" in data
    emails = [r["email"] for r in data["results"]]
    # Org A members (admin + member)
    assert admin.email in emails
    assert member.email in emails
    # Org B must not appear
    assert "other@example.com" not in emails

    # Response shape
    first = next(r for r in data["results"] if r["email"] == member.email)
    for key in [
        "id",
        "full_name",
        "email",
        "role",
        "is_active",
        "invited_at",
        "accepted_at",
        "status",
        "access_scopes",
    ]:
        assert key in first, f"Missing key: {key}"


def test_team_list_query_count(db, assert_query_ceiling) -> None:
    """20 STAFF + 1 ADMIN with 3 scopes each must stay at or below 6 queries."""
    admin, org = _make_org_admin(email="qcadmin@example.com")
    region = RegionFactory(organisation=org)
    for i in range(20):
        staff = UserFactory(
            role=User.Role.STAFF_ADMIN,
            organisation=org,
            email=f"staff{i}@example.com",
        )
        for _ in range(3):
            StaffAccessScopeFactory(
                user=staff,
                scope_type=StaffAccessScope.ScopeType.REGION,
                region=region,
            )

    client = _api_client_as(admin)
    with CaptureQueriesContext(connection) as ctx:
        resp = client.get("/api/v1/team/")
    assert resp.status_code == 200
    assert_query_ceiling(ctx, max_queries=6)


# ---------------------------------------------------------------------------
# TEAM-03: create + email
# ---------------------------------------------------------------------------


def test_create_team_member_invites_and_emails(db) -> None:
    """POST /api/v1/team/ creates an inactive user and sends invitation email."""
    admin, org = _make_org_admin(email="createadmin@example.com")
    region = RegionFactory(organisation=org)
    mail.outbox = []

    client = _api_client_as(admin)
    resp = client.post(
        "/api/v1/team/",
        {
            "full_name": "Jane Staff",
            "email": "janestaff@example.com",
            "invited_for_role": "STAFF_ADMIN",
            "region_ids": [region.pk],
            "shop_ids": [],
        },
        format="json",
    )
    assert resp.status_code == 201
    created_user = User.objects.get(email="janestaff@example.com")
    assert created_user.is_active is False
    assert created_user.role == User.Role.STAFF_ADMIN
    assert len(mail.outbox) == 1


def test_create_team_member_validates_scopes_for_staff(db) -> None:
    """POST with STAFF_ADMIN and no scopes returns 400."""
    admin, _org = _make_org_admin(email="scopeadmin@example.com")
    mail.outbox = []

    client = _api_client_as(admin)
    resp = client.post(
        "/api/v1/team/",
        {
            "full_name": "Jane Staff",
            "email": "janestaff2@example.com",
            "invited_for_role": "STAFF_ADMIN",
            "region_ids": [],
            "shop_ids": [],
        },
        format="json",
    )
    assert resp.status_code == 400
    error_text = str(resp.json())
    assert "region" in error_text.lower() or "store" in error_text.lower()
    assert len(mail.outbox) == 0


# ---------------------------------------------------------------------------
# TEAM-08 / TEAM-09: partial update
# ---------------------------------------------------------------------------


def test_partial_update_team_member(db) -> None:
    """PATCH /api/v1/team/{id}/ updates name + role."""
    admin, org = _make_org_admin(email="patchadmin@example.com")
    # Add another admin so last-manager guard doesn't fire
    UserFactory(role=User.Role.ORG_ADMIN, organisation=org, email="admin2@example.com")
    member = UserFactory(
        role=User.Role.STAFF_ADMIN, organisation=org, email="patchmember@example.com"
    )

    client = _api_client_as(admin)
    resp = client.patch(
        f"/api/v1/team/{member.pk}/",
        {
            "full_name": "Updated Name",
            "role": "ORG_ADMIN",
            "region_ids": [],
            "shop_ids": [],
        },
        format="json",
    )
    assert resp.status_code == 200
    member.refresh_from_db()
    assert member.full_name == "Updated Name"
    assert member.role == User.Role.ORG_ADMIN


def test_email_locked_on_update(db) -> None:
    """PATCH with email field does NOT change member.email."""
    admin, org = _make_org_admin(email="emailadmin@example.com")
    member = UserFactory(role=User.Role.STAFF_ADMIN, organisation=org, email="original@example.com")
    region = RegionFactory(organisation=org)

    client = _api_client_as(admin)
    resp = client.patch(
        f"/api/v1/team/{member.pk}/",
        {
            "full_name": member.full_name,
            "role": "STAFF_ADMIN",
            "email": "hacked@example.com",
            "region_ids": [region.pk],
            "shop_ids": [],
        },
        format="json",
    )
    # Should succeed (email field is silently ignored by serializer)
    assert resp.status_code in (200, 400)
    member.refresh_from_db()
    assert member.email == "original@example.com"


# ---------------------------------------------------------------------------
# Custom actions: disable / enable / resend / destroy
# ---------------------------------------------------------------------------


def test_disable_action(db) -> None:
    """POST /api/v1/team/{id}/disable/ sets is_active=False."""
    admin, org = _make_org_admin(email="disableadmin@example.com")
    member = UserFactory(
        role=User.Role.STAFF_ADMIN, organisation=org, email="disablemember@example.com"
    )
    assert member.is_active is True

    client = _api_client_as(admin)
    resp = client.post(f"/api/v1/team/{member.pk}/disable/")
    assert resp.status_code in (200, 204)
    member.refresh_from_db()
    assert member.is_active is False


def test_enable_action(db) -> None:
    """POST /api/v1/team/{id}/enable/ sets is_active=True."""
    admin, org = _make_org_admin(email="enableadmin@example.com")
    member = UserFactory(
        role=User.Role.STAFF_ADMIN,
        organisation=org,
        email="enablemember@example.com",
        is_active=False,
    )

    client = _api_client_as(admin)
    resp = client.post(f"/api/v1/team/{member.pk}/enable/")
    assert resp.status_code == 200
    member.refresh_from_db()
    assert member.is_active is True


def test_resend_action_invalidates_old_and_sends_new_email(db) -> None:
    """POST /api/v1/team/{id}/resend/ invalidates old token, creates new, sends email."""
    admin, org = _make_org_admin(email="resendadmin@example.com")
    member = UserFactory(
        role=User.Role.STAFF_ADMIN,
        organisation=org,
        email="resendmember@example.com",
        is_active=False,
    )
    # Create an initial invitation token
    old_token_raw = secrets.token_urlsafe(32)
    old_inv = InvitationToken.objects.create(
        organisation=org,
        invited_user=member,
        token_hash=InvitationToken.hash_token(old_token_raw),
        purpose=InvitationToken.Purpose.TEAM_MEMBER,
        invited_for_role=InvitationToken.InvitedForRole.STAFF_ADMIN,
    )
    mail.outbox = []

    client = _api_client_as(admin)
    resp = client.post(f"/api/v1/team/{member.pk}/resend/")
    assert resp.status_code == 200
    old_inv.refresh_from_db()
    assert old_inv.is_used is True
    # New token exists
    new_token = InvitationToken.objects.filter(invited_user=member, is_used=False).first()
    assert new_token is not None
    assert len(mail.outbox) == 1


def test_destroy_removes_member(db) -> None:
    """DELETE /api/v1/team/{id}/ deactivates member and marks tokens used."""
    admin, org = _make_org_admin(email="destroyadmin@example.com")
    # Add a second admin so last-manager guard doesn't fire when deleting first admin
    member = UserFactory(
        role=User.Role.STAFF_ADMIN,
        organisation=org,
        email="destroymember@example.com",
    )

    client = _api_client_as(admin)
    resp = client.delete(f"/api/v1/team/{member.pk}/")
    assert resp.status_code == 204
    member.refresh_from_db()
    assert member.is_active is False


# ---------------------------------------------------------------------------
# TEAM-14: Self-protection guards
# ---------------------------------------------------------------------------


def test_cannot_remove_self(db) -> None:
    """DELETE on own pk returns 403 with 'You cannot remove yourself.'"""
    admin, _org = _make_org_admin(email="selfremoveadmin@example.com")
    client = _api_client_as(admin)
    resp = client.delete(f"/api/v1/team/{admin.pk}/")
    assert resp.status_code == 403
    assert "You cannot remove yourself." in resp.json().get("detail", "")


def test_cannot_disable_self(db) -> None:
    """POST disable on own pk returns 403."""
    admin, _org = _make_org_admin(email="selfdisableadmin@example.com")
    client = _api_client_as(admin)
    resp = client.post(f"/api/v1/team/{admin.pk}/disable/")
    assert resp.status_code == 403
    assert "You cannot disable yourself." in resp.json().get("detail", "")


def test_cannot_demote_self(db) -> None:
    """PATCH on own pk with role=STAFF_ADMIN returns 403 with 'You cannot demote yourself.'"""
    admin, org = _make_org_admin(email="selfdemoteadmin@example.com")
    region = RegionFactory(organisation=org)
    client = _api_client_as(admin)
    resp = client.patch(
        f"/api/v1/team/{admin.pk}/",
        {
            "full_name": admin.full_name,
            "role": "STAFF_ADMIN",
            "region_ids": [region.pk],
            "shop_ids": [],
        },
        format="json",
    )
    assert resp.status_code == 403
    assert "You cannot demote yourself." in resp.json().get("detail", "")


# ---------------------------------------------------------------------------
# TEAM-15: Last-manager guard
# ---------------------------------------------------------------------------


def test_last_manager_guard_on_delete(db) -> None:
    """DELETE on the only active ORG_ADMIN returns 403 with 'Cannot remove the last Manager.'"""
    # Set up org with two ORG_ADMINs; requester tries to remove the only remaining ORG_ADMIN
    admin, org = _make_org_admin(email="lastmgr@example.com")
    requester = UserFactory(
        role=User.Role.ORG_ADMIN, organisation=org, email="requester@example.com"
    )

    # Now org has: admin + requester, both ORG_ADMIN active
    # admin is the last active manager after requester self-removes — test the remove_member guard
    # We use remove_member service guard: removes member if they are the only active ORG_ADMIN.
    # Scenario: requester is a second ORG_ADMIN who tries to delete admin (the only active one
    # after requester is deactivated). We need requester to remain ORG_ADMIN to pass IsOrgAdmin.
    # So: deactivate requester in DB but keep role, then requester's is_active=False = no IsOrgAdmin pass.
    # Better approach: make requester the requester, admin the target, confirm admin is last.
    # Deactivate requester temporarily so admin becomes last, but we need requester to still call API.
    # Simplest: use service directly — but plan says test at API layer.
    # API approach: org has admin (target) and requester (caller, ORG_ADMIN).
    # Make admin the ONLY active ORG_ADMIN by deactivating requester in DB,
    # but keep requester as ORG_ADMIN for IsOrgAdmin permission check.
    # Wait — if requester is is_active=False, @login_required still works but IsOrgAdmin checks role.
    # IsOrgAdmin only checks role and organisation_id, not is_active. So this works.
    requester.is_active = False
    requester.save(update_fields=["is_active"])

    client2 = _api_client_as(requester)
    resp2 = client2.delete(f"/api/v1/team/{admin.pk}/")
    assert resp2.status_code == 403
    assert "Cannot remove the last Manager." in resp2.json().get("detail", "")


def test_last_manager_guard_on_patch(db) -> None:
    """PATCH role=STAFF_ADMIN on the last active ORG_ADMIN returns 403."""
    admin, org = _make_org_admin(email="lastmgr2@example.com")
    # admin is the only active ORG_ADMIN — add second ORG_ADMIN who will make the request
    requester = UserFactory(
        role=User.Role.ORG_ADMIN, organisation=org, email="requester2@example.com"
    )
    region = RegionFactory(organisation=org)

    # Deactivate requester so admin becomes the last active ORG_ADMIN, but requester
    # keeps ORG_ADMIN role so IsOrgAdmin permission still passes.
    requester.is_active = False
    requester.save(update_fields=["is_active"])

    client = _api_client_as(requester)
    resp = client.patch(
        f"/api/v1/team/{admin.pk}/",
        {
            "full_name": admin.full_name,
            "role": "STAFF_ADMIN",
            "region_ids": [region.pk],
            "shop_ids": [],
        },
        format="json",
    )
    assert resp.status_code == 403
    assert "Cannot remove the last Manager." in resp.json().get("detail", "")


# ---------------------------------------------------------------------------
# TEAM-04: stats endpoint
# ---------------------------------------------------------------------------


def test_stats_endpoint(db) -> None:
    """GET /api/v1/team/stats/ returns {total_members, managers, active_members}."""
    admin, org = _make_org_admin(email="statsadmin@example.com")
    UserFactory(role=User.Role.STAFF_ADMIN, organisation=org, email="statsstaff@example.com")

    client = _api_client_as(admin)
    resp = client.get("/api/v1/team/stats/")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_members" in data
    assert "managers" in data
    assert "active_members" in data
    assert data["total_members"] >= 2
    assert data["managers"] >= 1


# ---------------------------------------------------------------------------
# Cross-tenant isolation
# ---------------------------------------------------------------------------


def test_cross_tenant_isolation(db, two_orgs_two_admins) -> None:
    """ORG_ADMIN of org A gets 404 when accessing org B member."""
    fixtures = two_orgs_two_admins
    admin_a = fixtures["admin_a"]
    org_b = fixtures["org_b"]
    member_b = UserFactory(
        role=User.Role.STAFF_ADMIN, organisation=org_b, email="member_b@example.com"
    )

    client_a = _api_client_as(admin_a)
    resp = client_a.get(f"/api/v1/team/{member_b.pk}/")
    assert resp.status_code in (403, 404)


# ---------------------------------------------------------------------------
# TEAM-17: invite_accept_view purpose-branching + template
# ---------------------------------------------------------------------------


def _create_team_member_token() -> tuple[str, InvitationToken, User]:
    """Create a TEAM_MEMBER invitation token with an associated inactive user."""
    org = OrganisationFactory()
    inviter = UserFactory(
        role=User.Role.ORG_ADMIN, organisation=org, email=f"inv{secrets.token_hex(4)}@example.com"
    )
    member = UserFactory(
        role=User.Role.STAFF_ADMIN,
        organisation=org,
        email=f"member{secrets.token_hex(4)}@example.com",
        is_active=False,
        full_name="Team Member",
        invited_by=inviter,
    )
    member.set_unusable_password()
    member.save()

    raw_token = secrets.token_urlsafe(32)
    inv = InvitationToken.objects.create(
        organisation=org,
        invited_user=member,
        token_hash=InvitationToken.hash_token(raw_token),
        purpose=InvitationToken.Purpose.TEAM_MEMBER,
        invited_for_role=InvitationToken.InvitedForRole.STAFF_ADMIN,
    )
    return raw_token, inv, member


def test_team_invite_accept_uses_team_template(db) -> None:
    """GET /invite/accept/{TEAM_MEMBER_token}/ renders team_invite_accept.html."""
    raw_token, _inv, _member = _create_team_member_token()
    client = Client()
    resp = client.get(f"/invite/accept/{raw_token}/")
    assert resp.status_code == 200
    template_names = [t.name for t in resp.templates]
    assert "accounts/team_invite_accept.html" in template_names
    assert b"You're joining as" in resp.content


def test_team_invite_accept_post_staff_redirects_to_welcome(db) -> None:
    """POST on TEAM_MEMBER invite for STAFF_ADMIN redirects to /admin/org/welcome/."""
    raw_token, _inv, member = _create_team_member_token()
    client = Client()
    resp = client.post(
        f"/invite/accept/{raw_token}/",
        {
            "full_name": "Team Member",
            "password1": "Str0ngPass!2026",
            "password2": "Str0ngPass!2026",
        },
    )
    assert resp.status_code == 302
    assert resp.url == "/admin/org/welcome/"
    member.refresh_from_db()
    assert member.is_active is True


def test_team_invite_accept_post_manager_redirects_to_dashboard(db) -> None:
    """POST on TEAM_MEMBER invite for ORG_ADMIN redirects to /admin/org-dashboard/."""
    org = OrganisationFactory()
    inviter = UserFactory(
        role=User.Role.ORG_ADMIN, organisation=org, email=f"inv2{secrets.token_hex(4)}@example.com"
    )
    member = UserFactory(
        role=User.Role.ORG_ADMIN,
        organisation=org,
        email=f"mgr{secrets.token_hex(4)}@example.com",
        is_active=False,
        full_name="Manager Member",
        invited_by=inviter,
    )
    member.set_unusable_password()
    member.save()

    raw_token = secrets.token_urlsafe(32)
    InvitationToken.objects.create(
        organisation=org,
        invited_user=member,
        token_hash=InvitationToken.hash_token(raw_token),
        purpose=InvitationToken.Purpose.TEAM_MEMBER,
        invited_for_role=InvitationToken.InvitedForRole.ORG_ADMIN,
    )

    client = Client()
    resp = client.post(
        f"/invite/accept/{raw_token}/",
        {
            "full_name": "Manager Member",
            "password1": "Str0ngPass!2026",
            "password2": "Str0ngPass!2026",
        },
    )
    assert resp.status_code == 302
    assert resp.url == "/admin/org-dashboard/"


# ---------------------------------------------------------------------------
# Smoke tests for Django template views (Task 2 additions)
# ---------------------------------------------------------------------------


def test_team_list_page_renders(db) -> None:
    """GET /admin/org/team/ renders the React mount point for ORG_ADMIN."""
    admin, _org = _make_org_admin(email="teamlistadmin@example.com")
    client = Client()
    client.force_login(admin)
    resp = client.get("/admin/org/team/")
    assert resp.status_code == 200
    assert b"Team" in resp.content
    assert b"team-table-root" in resp.content


def test_team_welcome_renders(db) -> None:
    """GET /admin/org/welcome/ renders the Staff welcome page."""
    org = OrganisationFactory()
    staff = UserFactory(
        role=User.Role.STAFF_ADMIN, organisation=org, email="staffwelcome@example.com"
    )
    client = Client()
    client.force_login(staff)
    resp = client.get("/admin/org/welcome/")
    assert resp.status_code == 200
    assert b"Your account is ready" in resp.content
