from __future__ import annotations

from django.db.models import Count, Prefetch, Q, QuerySet

from apps.accounts.models import StaffAccessScope, User


def list_team_members(
    *,
    organisation_id: int,
    search: str = "",
    region_id: int | None = None,
    shop_id: int | None = None,
) -> QuerySet[User]:
    """Return all ORG_ADMIN and STAFF_ADMIN users for the given organisation.

    Uses Prefetch with to_attr='prefetched_scopes' for N+1-safe access scope loading.
    Each returned User instance has a 'prefetched_scopes' attribute (a plain list
    of StaffAccessScope instances) — access this directly instead of calling
    instance.access_scopes.all() in serializers.

    Ordering: most recently invited first, then by created_at descending.
    """
    qs = (
        User.objects.filter(
            organisation_id=organisation_id,
            role__in=[User.Role.ORG_ADMIN, User.Role.STAFF_ADMIN],
        )
        .select_related("invited_by")
        .prefetch_related(
            Prefetch(
                "access_scopes",
                queryset=StaffAccessScope.objects.select_related("region", "shop"),
                to_attr="prefetched_scopes",
            )
        )
    )

    if search:
        qs = qs.filter(Q(full_name__icontains=search) | Q(email__icontains=search))

    if region_id is not None:
        qs = qs.filter(access_scopes__region_id=region_id).distinct()

    if shop_id is not None:
        qs = qs.filter(access_scopes__shop_id=shop_id).distinct()

    return qs.order_by("-invited_at", "-created_at")


def get_team_stats(*, organisation_id: int) -> dict[str, int]:
    """Return aggregated team stats for the given organisation.

    Returns:
        {
            "total_members": count of all ORG_ADMIN + STAFF_ADMIN users,
            "managers": count of ORG_ADMIN users,
            "active_members": count of is_active=True users,
        }
    All counts are computed in a single aggregate query.
    """
    agg = User.objects.filter(
        organisation_id=organisation_id,
        role__in=[User.Role.ORG_ADMIN, User.Role.STAFF_ADMIN],
    ).aggregate(
        total_members=Count("pk"),
        managers=Count("pk", filter=Q(role=User.Role.ORG_ADMIN)),
        active_members=Count("pk", filter=Q(is_active=True)),
    )
    return {
        "total_members": agg["total_members"] or 0,
        "managers": agg["managers"] or 0,
        "active_members": agg["active_members"] or 0,
    }
