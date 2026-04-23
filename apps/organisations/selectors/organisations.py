from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from django.db.models import Prefetch, Q

from apps.accounts.models import InvitationToken
from apps.organisations.models import Organisation

if TYPE_CHECKING:
    from django.db.models import QuerySet


def _base_queryset() -> QuerySet[Organisation]:
    return (
        Organisation.objects.not_deleted()
        .select_related("created_by")
        .annotate_store_counts()
        .prefetch_related(
            Prefetch(
                "invitation_tokens",
                queryset=InvitationToken.objects.order_by("-created_at"),
                to_attr="prefetched_tokens",
            )
        )
    )


def list_organisations(
    *,
    search: str = "",
    status: str = "",
    org_type: str = "",
) -> QuerySet[Organisation]:
    """Returns not_deleted orgs with select_related('created_by'),
    annotate_store_counts(), and prefetch_related invitation_tokens
    (to_attr='prefetched_tokens', ordered by -created_at).
    Applies Q(name__icontains) | Q(email__icontains) on search.
    Filters by status if in Status.values; by org_type if in OrgType.values.
    Orders -created_at."""
    qs = _base_queryset()
    if search:
        qs = qs.filter(Q(name__icontains=search) | Q(email__icontains=search))
    if status and status in Organisation.Status.values:
        qs = qs.filter(status=status)
    if org_type and org_type in Organisation.OrgType.values:
        qs = qs.filter(org_type=org_type)
    return qs.order_by("-created_at")


def get_organisation_detail(*, organisation_id: int) -> Organisation:
    """Same queryset as list_organisations but filtered to a single org by id,
    raises Organisation.DoesNotExist if missing or deleted."""
    return _base_queryset().get(id=organisation_id)


def activation_status_for(organisation: Organisation) -> str:
    """Returns one of 'active', 'pending', 'expired' based on the latest
    InvitationToken on the prefetched list (or invitation_tokens.all() fallback).
    - If any token is_used=True -> 'active'
    - Else if latest non-used token is_expired -> 'expired'
    - Else -> 'pending'
    - If no tokens exist -> 'pending' (CORG-04 creates one immediately)"""
    tokens = getattr(organisation, "prefetched_tokens", None)
    if tokens is None:
        tokens = list(organisation.invitation_tokens.order_by("-created_at"))
    if not tokens:
        return "pending"
    if any(t.is_used for t in tokens):
        return "active"
    latest = tokens[0]  # already -created_at ordered
    return "expired" if latest.is_expired else "pending"


def last_invited_at_for(organisation: Organisation) -> datetime | None:
    """Latest InvitationToken.created_at or None."""
    tokens = getattr(organisation, "prefetched_tokens", None)
    if tokens is None:
        tokens = list(organisation.invitation_tokens.order_by("-created_at"))
    return tokens[0].created_at if tokens else None
