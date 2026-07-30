from __future__ import annotations

import secrets
from typing import TYPE_CHECKING, Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import InvitationToken
from apps.accounts.services.audit import InvitationAuditAction, log_invitation_event
from apps.common.services.email import send_transactional_email
from apps.organisations.models import Organisation

if TYPE_CHECKING:
    from apps.accounts.models import User


_UPDATABLE_FIELDS: frozenset[str] = frozenset(
    {"name", "org_type", "address", "number_of_stores", "status", "allow_custom_sync_depth"}
)


def _build_accept_url(raw_token: str) -> str:
    """Absolute URL to the activation page — used verbatim in email templates."""
    from django.conf import settings

    base = settings.SITE_URL.rstrip("/")
    return f"{base}/invite/accept/{raw_token}/"


@transaction.atomic
def create_organisation(
    *,
    name: str,
    org_type: str,
    email: str,
    address: str = "",
    number_of_stores: int,
    created_by: User,
    allow_custom_sync_depth: bool = False,
) -> tuple[Organisation, str]:
    """Creates org + InvitationToken (48h) + sends invitation email atomically.
    Returns (org, raw_token) so callers can confirm delivery. If email send raises,
    transaction rolls back — nothing persisted."""
    org = Organisation.objects.create(
        name=name,
        org_type=org_type,
        email=email,
        address=address,
        number_of_stores=number_of_stores,
        allow_custom_sync_depth=allow_custom_sync_depth,
        created_by=created_by,
    )
    raw_token = secrets.token_urlsafe(32)
    token = InvitationToken.objects.create(
        organisation=org,
        token_hash=InvitationToken.hash_token(raw_token),
        purpose=InvitationToken.Purpose.ORG_ADMIN,
        invited_for_role=InvitationToken.InvitedForRole.ORG_ADMIN,
    )
    log_invitation_event(
        invitation=token,
        action=InvitationAuditAction.SENT,
        actor=created_by,
        after_data={"invited_email": email, "role": InvitationToken.InvitedForRole.ORG_ADMIN},
    )
    from django.conf import settings

    send_transactional_email(
        to=[email],
        subject=f"You're invited to manage {name}",
        template_base="emails/invitation",
        context={
            "organisation": org,
            "accept_url": _build_accept_url(raw_token),
            "expires_in_hours": 48,
            "site_url": settings.SITE_URL.rstrip("/"),
        },
        tags=["invitation"],
    )
    return org, raw_token


@transaction.atomic
def resend_invitation(
    *,
    organisation: Organisation,
    resent_by: User,
) -> str:
    """Invalidates all non-used tokens for this org, creates a fresh 48h token,
    sends invitation email with is_resend=True. Returns the new raw token.

    Audit-trail preserving: old tokens are marked is_used=True (not deleted).
    Recipients clicking an old link will see ACTV-05 "already used" copy.

    Atomic: if email send raises, all three effects (mark-old-used, create-new,
    email) roll back — consistent state guaranteed.
    """
    # Step 1: invalidate existing non-used tokens (update() runs in the atomic block)
    organisation.invitation_tokens.filter(is_used=False).update(is_used=True)

    # Step 2: create fresh token
    raw_token = secrets.token_urlsafe(32)
    token = InvitationToken.objects.create(
        organisation=organisation,
        token_hash=InvitationToken.hash_token(raw_token),
        purpose=InvitationToken.Purpose.ORG_ADMIN,
        invited_for_role=InvitationToken.InvitedForRole.ORG_ADMIN,
    )
    log_invitation_event(
        invitation=token,
        action=InvitationAuditAction.RESENT,
        actor=resent_by,
        after_data={
            "invited_email": organisation.email,
            "role": InvitationToken.InvitedForRole.ORG_ADMIN,
        },
    )

    # Step 3: send resend-flavoured invitation email
    from django.conf import settings

    send_transactional_email(
        to=[organisation.email],
        subject=f"You're invited to manage {organisation.name}",
        template_base="emails/invitation",
        context={
            "organisation": organisation,
            "accept_url": _build_accept_url(raw_token),
            "expires_in_hours": 48,
            "is_resend": True,
            "site_url": settings.SITE_URL.rstrip("/"),
        },
        tags=["invitation", "resend"],
    )
    return raw_token


@transaction.atomic
def activate_account(
    *,
    invitation: InvitationToken,
    full_name: str,
    password: str,
) -> User:
    """Atomically creates ORG_ADMIN user + marks invitation used.

    Uses select_for_update() to guard against double-submit races. Raises
    ValidationError if the token is already used (race detection).
    """
    from apps.accounts.models import User as _User

    # Re-fetch with row lock. Must be inside an atomic block (enforced by the
    # @transaction.atomic decorator). Prevents two concurrent POSTs both passing
    # the is_used check and creating duplicate User rows.
    locked = InvitationToken.objects.select_for_update().get(pk=invitation.pk)
    if locked.is_used:
        raise ValidationError("Invitation already used.")

    user = _User.objects.create_user(
        email=locked.organisation.email,
        password=password,
        full_name=full_name,
        role=_User.Role.ORG_ADMIN,
        organisation=locked.organisation,
        accepted_at=timezone.now(),
    )
    locked.invited_user = user
    locked.is_used = True
    locked.save(update_fields=["invited_user", "is_used", "updated_at"])
    log_invitation_event(
        invitation=locked,
        action=InvitationAuditAction.ACCEPTED,
        actor=user,
        after_data={"user_id": user.pk},
    )
    return user


def update_organisation(
    *,
    organisation: Organisation,
    **data: Any,
) -> Organisation:
    """Applies name/org_type/address/number_of_stores/status updates.
    Explicitly strips 'email' key if present (defence in depth vs EORG-02)."""
    # Defensive: strip email even if caller/serializer passes it (EORG-02).
    data.pop("email", None)
    # SA-056: cannot allocate fewer stores than are currently in use. The React
    # modal already blocks this client-side (StoreAllocationModal keys off
    # active_stores); this is the authoritative server-side guard.
    new_allocation = data.get("number_of_stores")
    if new_allocation is not None:
        in_use = organisation.shops.filter(is_active=True).count()
        if new_allocation < in_use:
            raise ValidationError(f"You cannot set this below the current in-use count ({in_use}).")
    changed: list[str] = []
    for field, value in data.items():
        if field not in _UPDATABLE_FIELDS:
            continue
        if getattr(organisation, field) != value:
            setattr(organisation, field, value)
            changed.append(field)
    if changed:
        changed.append("updated_at")
        organisation.save(update_fields=changed)
    return organisation


def enable_organisation(*, organisation: Organisation) -> Organisation:
    """Sets status=ACTIVE and saves update_fields=['status','updated_at']."""
    organisation.status = Organisation.Status.ACTIVE
    organisation.save(update_fields=["status", "updated_at"])
    return organisation


def disable_organisation(*, organisation: Organisation) -> Organisation:
    """Sets status=DISABLED and saves update_fields=['status','updated_at']."""
    organisation.status = Organisation.Status.DISABLED
    organisation.save(update_fields=["status", "updated_at"])
    return organisation


def delete_organisation(*, organisation: Organisation) -> None:
    """Calls organisation.soft_delete() (status=DELETED)."""
    organisation.soft_delete()


def adjust_store_allocation(
    *,
    organisation: Organisation,
    new_allocation: int,
) -> Organisation:
    """Sets number_of_stores=new_allocation. Validates new_allocation >= 1."""
    if new_allocation < 1 or new_allocation > 1000:
        raise ValidationError("Store allocation must be between 1 and 1000.")
    organisation.number_of_stores = new_allocation
    organisation.save(update_fields=["number_of_stores", "updated_at"])
    return organisation
