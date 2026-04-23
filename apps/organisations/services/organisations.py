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
    # Phase 4 registers the real `invite_accept` named URL. For now return
    # the relative path; the template renders {{ accept_url }} as-is and
    # emails render links with an absolute origin injected separately if
    # needed (invitation.html uses the value verbatim).
    return f"/invite/accept/{raw_token}/"


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
    send_transactional_email(
        to=[email],
        subject=f"You're invited to manage {name}",
        template_base="emails/invitation",
        context={
            "organisation": org,
            "accept_url": _build_accept_url(raw_token),
            "expires_in_hours": 48,
        },
        tags=["invitation"],
    )
    return org, raw_token


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
