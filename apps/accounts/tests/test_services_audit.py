"""SA-078: invitation lifecycle audit-log coverage.

Verifies AuditLog rows are written for invite sent / resent / accepted (both the
org-admin and team-member flows) and for expiry-on-use (logged once).
"""

from __future__ import annotations

import secrets
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.accounts.models import InvitationToken, User
from apps.accounts.services.audit import InvitationAuditAction
from apps.accounts.services.team import (
    activate_team_member,
    invite_member,
    resend_team_invitation,
)
from apps.accounts.tests.factories import (
    InvitationTokenFactory,
    OrgAdminFactory,
    UserFactory,
)
from apps.common.models import AuditLog
from apps.organisations.services.organisations import (
    activate_account,
    create_organisation,
    resend_invitation,
)
from apps.organisations.tests.factories import OrganisationFactory

pytestmark = pytest.mark.django_db


def _actions_for(org_id: int) -> list[str]:
    return list(
        AuditLog.objects.filter(organisation_id=org_id, entity_type="invitation").values_list(
            "action", flat=True
        )
    )


# ---- org-admin flow -------------------------------------------------------


def test_create_organisation_logs_invitation_sent() -> None:
    superadmin = UserFactory(role=User.Role.SUPERADMIN)
    org, _ = create_organisation(
        name="Acme",
        org_type="RETAIL",
        email="admin@acme.com",
        address="",
        number_of_stores=5,
        created_by=superadmin,
    )
    entry = AuditLog.objects.get(organisation=org, action=InvitationAuditAction.SENT)
    assert entry.entity_type == "invitation"
    assert entry.actor_id == superadmin.id
    assert entry.after_data["invited_email"] == "admin@acme.com"


def test_resend_invitation_logs_invitation_resent() -> None:
    superadmin = UserFactory(role=User.Role.SUPERADMIN)
    org = OrganisationFactory(email="admin@acme.com")
    resend_invitation(organisation=org, resent_by=superadmin)
    assert InvitationAuditAction.RESENT in _actions_for(org.id)


def test_activate_account_logs_invitation_accepted() -> None:
    org = OrganisationFactory(email="admin@acme.com")
    token = InvitationTokenFactory(organisation=org)
    user = activate_account(invitation=token, full_name="Jane A", password="Tr0ub4dor&3")
    entry = AuditLog.objects.get(organisation=org, action=InvitationAuditAction.ACCEPTED)
    assert entry.after_data["user_id"] == user.id


# ---- team-member flow -----------------------------------------------------


def test_invite_member_logs_invitation_sent() -> None:
    org = OrganisationFactory()
    admin = OrgAdminFactory(organisation=org)
    invite_member(
        organisation=org,
        full_name="New Staff",
        email="staff@acme.com",
        invited_for_role=InvitationToken.InvitedForRole.STAFF_ADMIN,
        region_ids=[],
        shop_ids=[],
        invited_by=admin,
    )
    entry = AuditLog.objects.get(organisation=org, action=InvitationAuditAction.SENT)
    assert entry.actor_id == admin.id
    assert entry.after_data["invited_email"] == "staff@acme.com"


def test_activate_team_member_logs_invitation_accepted() -> None:
    org = OrganisationFactory()
    member = UserFactory(
        email="pending@acme.com", is_active=False, role=User.Role.STAFF_ADMIN, organisation=org
    )
    token = InvitationTokenFactory(
        organisation=org, invited_user=member, purpose=InvitationToken.Purpose.TEAM_MEMBER
    )
    activate_team_member(invitation=token, full_name="Staffer", password="newpass1234!")
    assert InvitationAuditAction.ACCEPTED in _actions_for(org.id)


def test_resend_team_invitation_logs_invitation_resent() -> None:
    org = OrganisationFactory()
    admin = OrgAdminFactory(organisation=org)
    member = UserFactory(role=User.Role.STAFF_ADMIN, organisation=org)
    InvitationTokenFactory(
        organisation=org, invited_user=member, purpose=InvitationToken.Purpose.TEAM_MEMBER
    )
    resend_team_invitation(member=member, resented_by=admin)
    assert InvitationAuditAction.RESENT in _actions_for(org.id)


# ---- expiry-on-use --------------------------------------------------------


def test_expired_invite_link_logs_expired_once(client) -> None:
    org = OrganisationFactory(email="admin@acme.com")
    raw_token = secrets.token_urlsafe(32)
    InvitationTokenFactory(
        organisation=org,
        token_hash=InvitationToken.hash_token(raw_token),
        is_used=False,
        expires_at=timezone.now() - timedelta(hours=1),
    )
    url = f"/invite/accept/{raw_token}/"

    # Two visits to the expired link → exactly one 'expired' audit row.
    client.get(url)
    client.get(url)

    expired = AuditLog.objects.filter(organisation=org, action=InvitationAuditAction.EXPIRED)
    assert expired.count() == 1
    assert expired.first().actor_id is None
