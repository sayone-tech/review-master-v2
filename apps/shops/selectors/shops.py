from __future__ import annotations

from django.db.models import Q, QuerySet

from apps.accounts.models import User
from apps.credits.selectors.balances import annotate_credit_state
from apps.credits.services.periods import Period
from apps.organisations.models import Organisation
from apps.regions.models import Region
from apps.shops.models import Shop


def restrict_to_staff_scope(*, queryset: QuerySet[Shop], user: User | None) -> QuerySet[Shop]:
    """Narrow a Shop queryset to a Staff user's StaffAccessScope; no-op for anyone else.

    Keyed off the role, never off the truthiness of the id list: a Staff user with no
    scope rows must see nothing, not the whole organisation (SCOPE-01). Callers always
    apply the organisation filter themselves, because region expansion in
    ``get_accessible_shop_ids`` is not organisation-bounded.
    """
    if user is not None and getattr(user, "role", None) == User.Role.STAFF_ADMIN:
        # Function-level import keeps apps.reviews out of this module's import graph.
        from apps.reviews.selectors.reviews import get_accessible_shop_ids

        return queryset.filter(pk__in=get_accessible_shop_ids(user_id=user.pk))
    return queryset


def list_shops(
    *,
    organisation_id: int,
    search: str = "",
    status: str = "",
    region_id: int | None = None,
    active_only: bool = False,
    user: User | None = None,
    with_credits: bool = False,
    period: Period | None = None,
) -> QuerySet[Shop]:
    qs = Shop.objects.filter(organisation_id=organisation_id).select_related("region")
    qs = restrict_to_staff_scope(queryset=qs, user=user)
    if active_only:
        qs = qs.filter(is_active=True)
    if search:
        qs = qs.filter(Q(name__icontains=search) | Q(street_address__icontains=search))
    if status == "active":
        qs = qs.filter(is_active=True)
    elif status == "inactive":
        qs = qs.filter(is_active=False)
    if region_id is not None:
        qs = qs.filter(region_id=region_id)
    if with_credits:
        qs = annotate_credit_state(queryset=qs, period=period)
    return qs


def get_accessible_shop_for_credits(*, user: User, shop_id: int) -> Shop | None:
    """The single tenant/Staff gate for reading one shop's credits (D-17).

    Same organisation bound and same Staff rule as ``list_shops``, so list, retrieve and
    the credits GET cannot disagree. Inactive shops are allowed. Callers answer 404 on
    ``None`` (never 403, so existence is not leaked). Read-only.
    """
    org_id = getattr(user, "organisation_id", None)
    if org_id is None:
        return None
    return list_shops(organisation_id=org_id, user=user).filter(pk=shop_id).first()


def get_has_regions(*, organisation_id: int) -> bool:
    return Region.objects.filter(organisation_id=organisation_id).exists()


def get_allocation_status(*, organisation: Organisation) -> dict[str, int | bool]:
    current = Shop.objects.filter(organisation=organisation).count()
    return {
        "current": current,
        "max": organisation.number_of_stores,
        "at_limit": current >= organisation.number_of_stores,
    }
