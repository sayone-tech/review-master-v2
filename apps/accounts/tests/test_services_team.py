from __future__ import annotations

import pytest
from django.core import mail

from apps.accounts.exceptions import LastManagerError
from apps.accounts.models import InvitationToken, StaffAccessScope, User
from apps.accounts.services.team import (
    activate_team_member,
    disable_member,
    enable_member,
    invite_member,
    remove_member,
    resend_team_invitation,
    send_team_invitation_email,
    update_member,
)
from apps.accounts.tests.factories import (
    InvitationTokenFactory,
    OrgAdminFactory,
    StaffAccessScopeFactory,
    StaffAdminFactory,
    UserFactory,
)
from apps.organisations.tests.factories import OrganisationFactory
from apps.regions.tests.factories import RegionFactory
from apps.shops.tests.factories import ShopFactory


@pytest.mark.django_db
def test_invite_member():
    """invite_member creates User(is_active=False) + InvitationToken + StaffAccessScope rows atomically."""
    org = OrganisationFactory()
    admin = OrgAdminFactory(organisation=org)
    region = RegionFactory(organisation=org)
    shop = ShopFactory(organisation=org)

    user, raw_token = invite_member(
        organisation=org,
        full_name="New Staff",
        email="newstaff@example.com",
        invited_for_role=InvitationToken.InvitedForRole.STAFF_ADMIN,
        region_ids=[region.pk],
        shop_ids=[shop.pk],
        invited_by=admin,
    )

    # User attributes
    assert user.is_active is False
    assert user.email == "newstaff@example.com"
    assert user.full_name == "New Staff"
    assert user.role == User.Role.STAFF_ADMIN
    assert user.organisation == org
    assert user.invited_by == admin
    assert user.invited_at is not None

    # InvitationToken
    token = InvitationToken.objects.get(invited_user=user)
    assert token.purpose == InvitationToken.Purpose.TEAM_MEMBER
    assert token.invited_for_role == InvitationToken.InvitedForRole.STAFF_ADMIN
    assert token.token_hash == InvitationToken.hash_token(raw_token)

    # StaffAccessScope rows
    scopes = list(user.access_scopes.all())
    assert len(scopes) == 2
    scope_types = {s.scope_type for s in scopes}
    assert scope_types == {StaffAccessScope.ScopeType.REGION, StaffAccessScope.ScopeType.SHOP}


@pytest.mark.django_db
def test_invite_member_org_admin_role():
    """invite_member with ORG_ADMIN invited_for_role creates User with ORG_ADMIN role."""
    org = OrganisationFactory()
    admin = OrgAdminFactory(organisation=org)

    user, _ = invite_member(
        organisation=org,
        full_name="New Manager",
        email="newmgr@example.com",
        invited_for_role=InvitationToken.InvitedForRole.ORG_ADMIN,
        region_ids=[],
        shop_ids=[],
        invited_by=admin,
    )

    assert user.role == User.Role.ORG_ADMIN
    token = InvitationToken.objects.get(invited_user=user)
    assert token.purpose == InvitationToken.Purpose.TEAM_MEMBER


@pytest.mark.django_db
def test_invite_member_sends_email():
    """After invite_member + send_team_invitation_email, email lands in outbox."""
    org = OrganisationFactory()
    admin = OrgAdminFactory(organisation=org, full_name="Admin User")
    region = RegionFactory(organisation=org)

    user, raw_token = invite_member(
        organisation=org,
        full_name="Staff Person",
        email="staff@example.com",
        invited_for_role=InvitationToken.InvitedForRole.STAFF_ADMIN,
        region_ids=[region.pk],
        shop_ids=[],
        invited_by=admin,
    )
    scopes = list(user.access_scopes.select_related("region", "shop").all())
    send_team_invitation_email(
        member=user,
        raw_token=raw_token,
        inviter=admin,
        scopes=scopes,
        is_resend=False,
    )

    assert len(mail.outbox) == 1
    msg = mail.outbox[0]
    assert msg.to == ["staff@example.com"]
    assert org.name in msg.subject


@pytest.mark.django_db
def test_activate_team_member():
    """activate_team_member sets is_active=True, full_name, password, accepted_at; marks token used."""
    org = OrganisationFactory()
    user = UserFactory(
        email="pending@example.com",
        is_active=False,
        role=User.Role.STAFF_ADMIN,
        organisation=org,
    )
    token = InvitationTokenFactory(
        organisation=org,
        invited_user=user,
        is_used=False,
        purpose=InvitationToken.Purpose.TEAM_MEMBER,
        invited_for_role=InvitationToken.InvitedForRole.STAFF_ADMIN,
    )

    activated = activate_team_member(
        invitation=token,
        full_name="Updated Name",
        password="newpass1234!",
    )

    assert activated.pk == user.pk
    activated.refresh_from_db()
    assert activated.is_active is True
    assert activated.full_name == "Updated Name"
    assert activated.check_password("newpass1234!") is True
    assert activated.accepted_at is not None

    token.refresh_from_db()
    assert token.is_used is True


@pytest.mark.django_db
def test_activate_team_member_already_used_raises():
    """activate_team_member raises ValidationError if invitation is already used."""
    from django.core.exceptions import ValidationError

    org = OrganisationFactory()
    user = UserFactory(email="used@example.com", is_active=False, organisation=org)
    token = InvitationTokenFactory(
        organisation=org,
        invited_user=user,
        is_used=True,
        purpose=InvitationToken.Purpose.TEAM_MEMBER,
        invited_for_role=InvitationToken.InvitedForRole.STAFF_ADMIN,
    )

    with pytest.raises(ValidationError, match="already used"):
        activate_team_member(invitation=token, full_name="Test", password="testpass123!")


@pytest.mark.django_db
def test_disable_member():
    """disable_member sets is_active=False."""
    org = OrganisationFactory()
    member = StaffAdminFactory(organisation=org, is_active=True)

    result = disable_member(member=member)

    assert result.is_active is False
    member.refresh_from_db()
    assert member.is_active is False


@pytest.mark.django_db
def test_enable_member():
    """enable_member sets is_active=True."""
    org = OrganisationFactory()
    member = StaffAdminFactory(organisation=org, is_active=False)

    result = enable_member(member=member)

    assert result.is_active is True
    member.refresh_from_db()
    assert member.is_active is True


@pytest.mark.django_db
def test_remove_member():
    """remove_member sets is_active=False."""
    org = OrganisationFactory()
    admin = OrgAdminFactory(organisation=org)
    # Need a second active ORG_ADMIN so guard doesn't fire
    OrgAdminFactory(organisation=org)
    member = StaffAdminFactory(organisation=org, is_active=True)

    remove_member(member=member, removed_by=admin)

    member.refresh_from_db()
    assert member.is_active is False


@pytest.mark.django_db
def test_remove_member_invalidates_pending_tokens():
    """remove_member invalidates all pending InvitationTokens for the member."""
    org = OrganisationFactory()
    admin = OrgAdminFactory(organisation=org)
    OrgAdminFactory(organisation=org)  # second admin so guard doesn't fire
    member = StaffAdminFactory(organisation=org, is_active=True)
    pending_token = InvitationTokenFactory(
        organisation=org,
        invited_user=member,
        is_used=False,
        purpose=InvitationToken.Purpose.TEAM_MEMBER,
        invited_for_role=InvitationToken.InvitedForRole.STAFF_ADMIN,
    )

    remove_member(member=member, removed_by=admin)

    pending_token.refresh_from_db()
    assert pending_token.is_used is True


@pytest.mark.django_db
def test_remove_member_last_manager_guard():
    """remove_member raises LastManagerError when removing the only active ORG_ADMIN."""
    org = OrganisationFactory()
    admin = OrgAdminFactory(organisation=org)
    remover = OrgAdminFactory(organisation=org)

    # Deactivate the second admin — now admin is the only active ORG_ADMIN
    remover.is_active = False
    remover.save()

    with pytest.raises(LastManagerError):
        remove_member(member=admin, removed_by=remover)

    # Member should not have been deactivated
    admin.refresh_from_db()
    assert admin.is_active is True


@pytest.mark.django_db
def test_resend_team_invitation():
    """resend_team_invitation marks old token used + nulls invited_user + creates new token."""
    org = OrganisationFactory()
    admin = OrgAdminFactory(organisation=org)
    member = StaffAdminFactory(organisation=org, is_active=False)
    old_token = InvitationTokenFactory(
        organisation=org,
        invited_user=member,
        is_used=False,
        purpose=InvitationToken.Purpose.TEAM_MEMBER,
        invited_for_role=InvitationToken.InvitedForRole.STAFF_ADMIN,
    )

    raw_token = resend_team_invitation(member=member, resented_by=admin)

    # Old token should be marked used and have invited_user=None
    old_token.refresh_from_db()
    assert old_token.is_used is True
    assert old_token.invited_user is None

    # New token should exist
    new_token = InvitationToken.objects.get(invited_user=member, is_used=False)
    assert new_token.token_hash == InvitationToken.hash_token(raw_token)
    assert new_token.purpose == InvitationToken.Purpose.TEAM_MEMBER


@pytest.mark.django_db
def test_resend_nulls_old_token_invited_user():
    """resend_team_invitation nulls old token's invited_user before creating new — prevents UniqueConstraint error."""
    org = OrganisationFactory()
    admin = OrgAdminFactory(organisation=org)
    member = StaffAdminFactory(organisation=org, is_active=False)
    InvitationTokenFactory(
        organisation=org,
        invited_user=member,
        is_used=False,
        purpose=InvitationToken.Purpose.TEAM_MEMBER,
        invited_for_role=InvitationToken.InvitedForRole.STAFF_ADMIN,
    )

    # Should not raise IntegrityError (OneToOne uniqueness)
    raw_token = resend_team_invitation(member=member, resented_by=admin)
    assert raw_token is not None


@pytest.mark.django_db
def test_team_invitation_email():
    """send_team_invitation_email sends 1 email with correct recipient and subject."""
    org = OrganisationFactory()
    inviter = OrgAdminFactory(organisation=org, full_name="Inviter Name")
    member = StaffAdminFactory(organisation=org, email="invitee@example.com", full_name="Invitee")

    send_team_invitation_email(
        member=member,
        raw_token="testtoken123",
        inviter=inviter,
        scopes=[],
        is_resend=False,
    )

    assert len(mail.outbox) == 1
    msg = mail.outbox[0]
    assert msg.to == ["invitee@example.com"]
    assert org.name in msg.subject
    assert "invited to join" in msg.subject.lower()


@pytest.mark.django_db
def test_team_invitation_resent_email():
    """send_team_invitation_email with is_resend=True sends resent email with correct subject."""
    org = OrganisationFactory()
    inviter = OrgAdminFactory(organisation=org, full_name="Inviter Name")
    member = StaffAdminFactory(organisation=org, email="invitee@example.com", full_name="Invitee")

    send_team_invitation_email(
        member=member,
        raw_token="testtoken123",
        inviter=inviter,
        scopes=[],
        is_resend=True,
    )

    assert len(mail.outbox) == 1
    msg = mail.outbox[0]
    assert msg.to == ["invitee@example.com"]
    assert "New invitation link" in msg.subject


@pytest.mark.django_db
def test_update_member_replaces_scopes():
    """update_member deletes old scopes and creates new ones; updates name and role."""
    org = OrganisationFactory()
    member = StaffAdminFactory(organisation=org, full_name="Old Name")
    old_region = RegionFactory(organisation=org)
    StaffAccessScopeFactory(
        user=member,
        scope_type=StaffAccessScope.ScopeType.REGION,
        region=old_region,
        shop=None,
    )

    new_region = RegionFactory(organisation=org)
    new_shop = ShopFactory(organisation=org)

    updated = update_member(
        member=member,
        full_name="New Name",
        role=User.Role.STAFF_ADMIN,
        region_ids=[new_region.pk],
        shop_ids=[new_shop.pk],
    )

    assert updated.full_name == "New Name"

    # Old scope gone, new ones present
    scopes = list(member.access_scopes.all())
    assert len(scopes) == 2
    region_ids = {s.region_id for s in scopes if s.scope_type == StaffAccessScope.ScopeType.REGION}
    shop_ids = {s.shop_id for s in scopes if s.scope_type == StaffAccessScope.ScopeType.SHOP}
    assert old_region.pk not in region_ids
    assert new_region.pk in region_ids
    assert new_shop.pk in shop_ids
