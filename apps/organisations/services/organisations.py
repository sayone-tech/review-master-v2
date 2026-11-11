from __future__ import annotations

import secrets
from typing import TYPE_CHECKING, Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import InvitationToken
from apps.accounts.services.audit import InvitationAuditAction, log_invitation_event
from apps.common.models import AuditLog
from apps.common.services.email import send_transactional_email
from apps.credits.selectors.balances import org_has_current_month_allocation
from apps.credits.services.allocation import materialise_org_balances, raise_zero_balances
from apps.credits.services.periods import current_period
from apps.organisations.models import Organisation

if TYPE_CHECKING:
    from apps.accounts.models import User


_UPDATABLE_FIELDS: frozenset[str] = frozenset(
    {
        "name",
        "org_type",
        "address",
        "number_of_stores",
        "status",
        "allow_custom_sync_depth",
        "monthly_credit_allocation",
    }
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
    monthly_credit_allocation: int = 0,
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
        monthly_credit_allocation=monthly_credit_allocation,
        created_by=created_by,
    )
    if monthly_credit_allocation > 0:
        # A default of 0 is not a change (no audit row); a first value > 0 is.
        period = current_period()
        AuditLog.objects.create(
            organisation=org,
            actor=created_by,
            entity_type="organisation",
            entity_id=str(org.pk),
            action="organisation.credits.set",
            before_data={"monthly_credit_allocation": 0},
            after_data={
                "monthly_credit_allocation": monthly_credit_allocation,
                "effective": "immediate",
                "shops_touched": 0,
                "period_year": period.year,
                "period_month": period.month,
            },
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


@transaction.atomic
def update_organisation(
    *,
    organisation: Organisation,
    actor: User | None = None,
    **data: Any,
) -> Organisation:
    """Applies name/org_type/address/number_of_stores/status/credit-allocation updates.
    Explicitly strips 'email' key if present (defence in depth vs EORG-02).

    Credit allocation (CRED-01, CRED-06): the old value is read from the organisation row
    locked with ``select_for_update`` (the passed instance may be stale). On a real change
    the current-month balances are written BEFORE the field is saved: 0 -> N with no
    current-month allocation (D-18) raises zero rows and is immediate; any other change
    materialises every shop's row at the old value so shops keep it this month. One
    ``organisation.credits.set`` AuditLog row is written only on a real change."""
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
    credit_change: dict[str, Any] | None = None
    if "monthly_credit_allocation" in data:
        old = (
            Organisation.objects.select_for_update(of=("self",))
            .filter(pk=organisation.pk)
            .values_list("monthly_credit_allocation", flat=True)
            .get()
        )
        # Compare against the locked truth, not the possibly stale instance.
        organisation.monthly_credit_allocation = old
        new = data["monthly_credit_allocation"]
        if new != old:
            period = current_period()
            if old == 0 and not org_has_current_month_allocation(
                organisation_id=organisation.pk, period=period
            ):
                touched = raise_zero_balances(
                    organisation_id=organisation.pk, allocation=new, period=period
                )
                effective = "immediate"
            else:
                touched = materialise_org_balances(
                    organisation_id=organisation.pk, allocation=old, period=period
                )
                effective = "next_month"
            credit_change = {
                "before": {"monthly_credit_allocation": old},
                "after": {
                    "monthly_credit_allocation": new,
                    "effective": effective,
                    "shops_touched": touched,
                    "period_year": period.year,
                    "period_month": period.month,
                },
            }
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
    if credit_change is not None:
        AuditLog.objects.create(
            organisation=organisation,
            actor=actor,
            entity_type="organisation",
            entity_id=str(organisation.pk),
            action="organisation.credits.set",
            before_data=credit_change["before"],
            after_data=credit_change["after"],
        )
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
