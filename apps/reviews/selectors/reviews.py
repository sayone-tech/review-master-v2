"""Phase 11 — Review selectors (read-side query helpers)."""

from __future__ import annotations

from django.db.models import QuerySet

from apps.accounts.models import StaffAccessScope, User
from apps.reviews.models import Review


def get_accessible_shop_ids(*, user_id: int) -> list[int]:
    """Return shop IDs accessible to a Staff user via StaffAccessScope.

    Handles SHOP-scoped and REGION-scoped entries. Used by ReviewViewSet for
    STAFF_ADMIN role only. Counts as 1 query against the <=5 budget.
    """
    from apps.shops.models import Shop

    scopes = list(
        StaffAccessScope.objects.filter(user_id=user_id).values(
            "scope_type", "shop_id", "region_id"
        )
    )
    shop_ids: set[int] = set()
    region_ids: set[int] = set()
    for s in scopes:
        if s["scope_type"] == StaffAccessScope.ScopeType.SHOP and s["shop_id"]:
            shop_ids.add(int(s["shop_id"]))
        elif s["scope_type"] == StaffAccessScope.ScopeType.REGION and s["region_id"]:
            region_ids.add(int(s["region_id"]))
    if region_ids:
        shop_ids.update(Shop.objects.filter(region_id__in=region_ids).values_list("id", flat=True))
    return sorted(shop_ids)


def base_reviews_queryset(*, organisation_id: int) -> QuerySet[Review]:
    """Base queryset for an org — active (non-deleted), prefetched for list views."""
    return (
        Review.objects.active()
        .filter(organisation_id=organisation_id)
        .select_related("shop", "shop__region")
    )


def list_reviews(
    *,
    organisation_id: int,
    user: User | None = None,
) -> QuerySet[Review]:
    """Return queryset for the Reviews list endpoint, scoped per role."""
    qs = base_reviews_queryset(organisation_id=organisation_id)
    if user is not None and getattr(user, "role", None) == User.Role.STAFF_ADMIN:
        accessible = get_accessible_shop_ids(user_id=user.pk)
        qs = qs.filter(shop_id__in=accessible)
    return qs
