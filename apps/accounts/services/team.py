from __future__ import annotations

import logging
import secrets
from typing import TYPE_CHECKING

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.accounts.exceptions import LastManagerError
from apps.accounts.models import InvitationToken, StaffAccessScope, User
from apps.accounts.services.audit import InvitationAuditAction, log_invitation_event
from apps.common.services.email import send_transactional_email

if TYPE_CHECKING:
    from apps.organisations.models import Organisation

logger = logging.getLogger(__name__)


def _build_accept_url(raw_token: str) -> str:
    """Absolute URL to the team member activation page."""
    base = settings.SITE_URL.rstrip("/")
    return f"{base}/invite/accept/{raw_token}/"


def _flush_user_sessions(user_pk: int) -> None:
    """Delete all active django_session rows for this user (database session backend).

    Non-fatal: if session flush fails, is_active=False still blocks future logins.
    Scans active sessions and matches those belonging to user_pk via get_decoded().
    """
    from django.contrib.sessions.models import Session

    active_sessions = Session.objects.filter(expire_date__gte=timezone.now())
    to_delete = []
    for session in active_sessions:
        try:
            data = session.get_decoded()
            if data.get("_auth_user_id") == str(user_pk):
                to_delete.append(session.pk)
        except Exception as exc:
            logger.debug("Could not decode session %s: %s", session.pk, exc)
    if to_delete:
        Session.objects.filter(pk__in=to_delete).delete()


@transaction.atomic
def invite_member(
    *,
    organisation: Organisation,
    full_name: str,
    email: str,
    invited_for_role: str,
    region_ids: list[int],
    shop_ids: list[int],
    invited_by: User,
) -> tuple[User, str]:
    """Create User(is_active=False) + InvitationToken(TEAM_MEMBER) + StaffAccessScope rows.

    Returns (user, raw_token). Email sending is the CALLER's responsibility — call
    send_team_invitation_email() after this returns.
    """
    role = (
        User.Role.STAFF_ADMIN
        if invited_for_role == InvitationToken.InvitedForRole.STAFF_ADMIN
        else User.Role.ORG_ADMIN
    )
    user = User(
        email=email,
        full_name=full_name,
        role=role,
        organisation=organisation,
        invited_by=invited_by,
        invited_at=timezone.now(),
        is_active=False,
    )
    user.set_unusable_password()
    user.save()

    raw_token = secrets.token_urlsafe(32)
    token = InvitationToken.objects.create(
        organisation=organisation,
        invited_user=user,
        token_hash=InvitationToken.hash_token(raw_token),
        purpose=InvitationToken.Purpose.TEAM_MEMBER,
        invited_for_role=invited_for_role,
    )
    log_invitation_event(
        invitation=token,
        action=InvitationAuditAction.SENT,
        actor=invited_by,
        after_data={"invited_email": email, "role": invited_for_role},
    )

    scopes: list[StaffAccessScope] = [
        StaffAccessScope(
            user=user,
            scope_type=StaffAccessScope.ScopeType.REGION,
            region_id=rid,
            shop=None,
        )
        for rid in region_ids
    ] + [
        StaffAccessScope(
            user=user,
            scope_type=StaffAccessScope.ScopeType.SHOP,
            shop_id=sid,
            region=None,
        )
        for sid in shop_ids
    ]
    if scopes:
        StaffAccessScope.objects.bulk_create(scopes)

    return user, raw_token


@transaction.atomic
def activate_team_member(
    *,
    invitation: InvitationToken,
    full_name: str,
    password: str,
) -> User:
    """Activate an existing (is_active=False) team member User.

    Uses select_for_update() to guard against double-submit races. Raises
    ValidationError if the invitation is already used.
    """
    locked = InvitationToken.objects.select_for_update().get(pk=invitation.pk)
    if locked.is_used:
        raise ValidationError("Invitation already used.")

    user = locked.invited_user
    if user is None:
        raise ValidationError("Invitation is invalid.")

    user.full_name = full_name
    user.set_password(password)
    user.is_active = True
    user.accepted_at = timezone.now()
    user.save(update_fields=["full_name", "password", "is_active", "accepted_at", "updated_at"])

    locked.is_used = True
    locked.save(update_fields=["is_used", "updated_at"])

    log_invitation_event(
        invitation=locked,
        action=InvitationAuditAction.ACCEPTED,
        actor=user,
        after_data={"user_id": user.pk},
    )

    return user


@transaction.atomic
def update_member(
    *,
    member: User,
    full_name: str,
    role: str,
    region_ids: list[int],
    shop_ids: list[int],
) -> User:
    """Update member's full_name, role, and access scopes atomically (delete-all + recreate)."""
    member.full_name = full_name
    member.role = role
    member.save(update_fields=["full_name", "role", "updated_at"])

    # Delete-all + bulk_create is the chosen replace strategy (see RESEARCH Pattern 6)
    member.access_scopes.all().delete()
    new_scopes: list[StaffAccessScope] = [
        StaffAccessScope(
            user=member,
            scope_type=StaffAccessScope.ScopeType.REGION,
            region_id=rid,
            shop=None,
        )
        for rid in region_ids
    ] + [
        StaffAccessScope(
            user=member,
            scope_type=StaffAccessScope.ScopeType.SHOP,
            shop_id=sid,
            region=None,
        )
        for sid in shop_ids
    ]
    if new_scopes:
        StaffAccessScope.objects.bulk_create(new_scopes)

    return member


def enable_member(*, member: User) -> User:
    """Set member.is_active=True."""
    member.is_active = True
    member.save(update_fields=["is_active", "updated_at"])
    return member


def disable_member(*, member: User) -> User:
    """Set member.is_active=False; best-effort session flush."""
    member.is_active = False
    member.save(update_fields=["is_active", "updated_at"])
    try:
        _flush_user_sessions(member.pk)
    except Exception:
        logger.warning("Session flush failed for user pk=%s", member.pk)
    return member


@transaction.atomic
def remove_member(*, member: User, removed_by: User) -> None:
    """Deactivate member, invalidate pending tokens, flush sessions.

    Raises LastManagerError if member is the only active ORG_ADMIN.
    """
    # Last-manager guard: count other active ORG_ADMINs in the same org
    if member.role == User.Role.ORG_ADMIN and member.organisation_id is not None:
        other_active_managers = (
            User.objects.filter(
                organisation_id=int(member.organisation_id),
                role=User.Role.ORG_ADMIN,
                is_active=True,
            )
            .exclude(pk=member.pk)
            .count()
        )
        if other_active_managers == 0:
            raise LastManagerError("Cannot remove the last Manager.")

    member.is_active = False
    member.save(update_fields=["is_active", "updated_at"])

    # Invalidate all pending tokens for this member
    InvitationToken.objects.filter(invited_user=member, is_used=False).update(is_used=True)

    try:
        _flush_user_sessions(member.pk)
    except Exception:
        logger.warning("Session flush failed for user pk=%s", member.pk)

    # accepted for future audit log integration
    _ = removed_by


@transaction.atomic
def resend_team_invitation(*, member: User, resented_by: User) -> str:
    """Invalidate old token + create fresh token. Returns raw token string.

    CRITICAL: null out invited_user on old token BEFORE creating new token
    to avoid UniqueConstraint on the OneToOneField (Pitfall 4 from RESEARCH).
    """
    # Find the most recent pending token for this member
    old_token = InvitationToken.objects.filter(invited_user=member).order_by("-created_at").first()
    if old_token is not None and not old_token.is_used:
        # Null out invited_user FIRST (required before creating new token)
        old_token.invited_user = None
        old_token.is_used = True
        old_token.save(update_fields=["is_used", "invited_user", "updated_at"])

    # Defensive: invalidate any other lingering pending tokens
    InvitationToken.objects.filter(invited_user=member, is_used=False).update(is_used=True)

    # Create fresh token
    if member.organisation is None:
        raise ValidationError("Member has no associated organisation.")
    raw_token = secrets.token_urlsafe(32)
    token = InvitationToken.objects.create(
        organisation=member.organisation,
        invited_user=member,
        token_hash=InvitationToken.hash_token(raw_token),
        purpose=InvitationToken.Purpose.TEAM_MEMBER,
        invited_for_role=member.role,
    )
    log_invitation_event(
        invitation=token,
        action=InvitationAuditAction.RESENT,
        actor=resented_by,
        after_data={"invited_email": member.email, "role": member.role},
    )

    return raw_token


def send_team_invitation_email(
    *,
    member: User,
    raw_token: str,
    inviter: User,
    scopes: list[StaffAccessScope],
    is_resend: bool = False,
) -> None:
    """Compose and send the team invitation email.

    This is intentionally separate from invite_member() and resend_team_invitation()
    so that email failures don't roll back the DB writes, and so the caller can
    control timing (e.g. send after response is committed).
    """
    context: dict[str, object] = {
        "invitee_name": member.full_name,
        "inviter_name": inviter.full_name,
        "organisation": member.organisation,
        "role_display": "Manager" if member.role == User.Role.ORG_ADMIN else "Staff",
        "accept_url": _build_accept_url(raw_token),
        "expires_in_hours": 48,
        "site_url": settings.SITE_URL.rstrip("/"),
        "assigned_region_names": [
            s.region.name for s in scopes if s.scope_type == "REGION" and s.region
        ],
        "assigned_shop_names": [s.shop.name for s in scopes if s.scope_type == "SHOP" and s.shop],
        "is_staff_role": member.role == User.Role.STAFF_ADMIN,
        "is_resend": is_resend,
    }

    org_name = member.organisation.name if member.organisation else "your organisation"
    if is_resend:
        template_base = "emails/team_invitation_resent"
        subject = f"New invitation link for {org_name}"
        tags = ["team-invitation", "resend"]
    else:
        template_base = "emails/team_invitation"
        subject = f"You're invited to join {org_name}"
        tags = ["team-invitation"]

    send_transactional_email(
        to=[member.email],
        subject=subject,
        template_base=template_base,
        context=context,
        tags=tags,
    )
