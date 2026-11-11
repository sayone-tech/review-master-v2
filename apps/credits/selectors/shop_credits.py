"""Read-only Superadmin credit primitives (CSUP-01, CRED-05, D-06).

These selectors never create, update or delete a row: an unmaterialised shop reports its
virtual balance. They are unscoped by tenant and must only be called from Superadmin-only views
(Org Admin / Staff scoping of credit reads is Phase 33).
"""

from __future__ import annotations

from typing import Any

from django.db.models import QuerySet

from apps.credits.selectors.balances import (
    annotate_credit_state,
    org_current_month_allocation_expression,
)
from apps.credits.services.periods import Period


def list_org_shop_credits(
    *, organisation_id: int, search: str = "", period: Period | None = None
) -> QuerySet[Any]:
    """Active shops of the organisation with their ``period`` balance, ordered by name then id."""
    # Function-level import keeps the credits -> shops edge out of module scope.
    from apps.shops.models import Shop

    qs = Shop.objects.filter(organisation_id=organisation_id, is_active=True)
    term = search.strip()
    if term:
        qs = qs.filter(name__icontains=term)
    return annotate_credit_state(queryset=qs.only("id", "name"), period=period).order_by(
        "name", "pk"
    )


def get_org_allocation_per_shop(*, organisation_id: int, period: Period) -> int | None:
    """This month's per-shop allocation (D-21), or None for an unknown or DELETED organisation."""
    from apps.organisations.models import Organisation

    value: int | None = (
        Organisation.objects.not_deleted()
        .filter(pk=organisation_id)
        .annotate(allocation_per_shop=org_current_month_allocation_expression(period=period))
        .values_list("allocation_per_shop", flat=True)
        .first()
    )
    return value
