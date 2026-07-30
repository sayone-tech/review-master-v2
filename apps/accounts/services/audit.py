from __future__ import annotations

from typing import TYPE_CHECKING, Any

from apps.common.models import AuditLog

if TYPE_CHECKING:
    from apps.accounts.models import InvitationToken, User


class InvitationAuditAction:
    """Audit action strings for invitation lifecycle events (SA-078)."""

    SENT = "invitation.sent"
    RESENT = "invitation.resent"
    ACCEPTED = "invitation.accepted"
    EXPIRED = "invitation.expired"


def log_invitation_event(
    *,
    invitation: InvitationToken,
    action: str,
    actor: User | None = None,
    after_data: dict[str, Any] | None = None,
) -> None:
    """Write one AuditLog row for an invitation lifecycle event (SA-078).

    Reuses the generic AuditLog model (§29.4) — entity_type="invitation".
    actor is stored only when authenticated (system/anonymous events → null),
    matching the pattern in apps.action_items.services.lifecycle.
    """
    AuditLog.objects.create(
        organisation_id=invitation.organisation_id,
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        entity_type="invitation",
        entity_id=str(invitation.pk),
        action=action,
        before_data={},
        after_data=after_data or {},
    )


def log_invitation_expired_once(*, invitation: InvitationToken) -> None:
    """Log an ``invitation.expired`` event at most once per token (SA-078).

    Expiry has no natural trigger (tokens just age out), so it is recorded when
    an expired invite link is opened. The guard keeps repeated visits from
    spamming the audit log. Actor is null (the visitor is unauthenticated)."""
    already_logged = AuditLog.objects.filter(
        entity_type="invitation",
        entity_id=str(invitation.pk),
        action=InvitationAuditAction.EXPIRED,
    ).exists()
    if not already_logged:
        log_invitation_event(invitation=invitation, action=InvitationAuditAction.EXPIRED)
