from __future__ import annotations

import secrets
from typing import TYPE_CHECKING, Any

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.accounts.models import InvitationToken
from apps.common.services.email import send_transactional_email
from apps.organisations.models import Organisation

if TYPE_CHECKING:
    from apps.accounts.models import User


_UPDATABLE_FIELDS: frozenset[str] = frozenset(
    {"name", "org_type", "address", "number_of_stores", "status"}
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
        created_by=created_by,
    )
    raw_token = secrets.token_urlsafe(32)
    InvitationToken.objects.create(
        organisation=org,
        token_hash=InvitationToken.hash_token(raw_token),
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
    InvitationToken.objects.create(
        organisation=organisation,
        token_hash=InvitationToken.hash_token(raw_token),
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
    # resent_by is accepted for future audit-log integration (Phase 5+); not used
    # in Phase 4 but part of the locked contract.
    _ = resent_by
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
    )
    locked.invited_user = user
    locked.is_used = True
    locked.save(update_fields=["invited_user", "is_used", "updated_at"])
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
