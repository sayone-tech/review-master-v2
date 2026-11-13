"""Sidebar badge counts and AI-credits meter for the signed-in tenant user.

Read-only. Scoping mirrors the list endpoints it summarises: Org Admin sees the whole
organisation, Staff only their accessible shops (and never brand-scoped action items,
enforced inside ``list_action_items``). Credits are summed over ACTIVE shops only,
because ``sum_credit_balances`` does not filter ``is_active``.
"""

from __future__ import annotations

from dataclasses import dataclass

from apps.accounts.models import User
from apps.action_items.models import ActionItem
from apps.action_items.selectors.items import list_action_items
from apps.credits.selectors.balances import CreditTotals, sum_credit_balances
from apps.reviews.selectors.reviews import base_reviews_queryset, get_accessible_shop_ids
from apps.shops.models import Shop


@dataclass(frozen=True, slots=True)
class NavSummary:
    reviews_awaiting_reply: int
    open_action_items: int
    credits: CreditTotals | None


_EMPTY = NavSummary(reviews_awaiting_reply=0, open_action_items=0, credits=None)


def get_nav_summary(*, user: User) -> NavSummary:
    org_id = user.organisation_id
    if user.role == User.Role.SUPERADMIN or org_id is None:
        return _EMPTY

    is_staff = user.role == User.Role.STAFF_ADMIN
    shops = Shop.objects.filter(organisation_id=org_id, is_active=True)
    reviews = base_reviews_queryset(organisation_id=org_id).filter(is_replied=False)
    accessible: list[int] | None = None
    if is_staff:
        accessible = get_accessible_shop_ids(user_id=user.pk)
        shops = shops.filter(pk__in=accessible)
        reviews = reviews.filter(shop_id__in=accessible)
    shop_ids = list(shops.values_list("pk", flat=True))

    open_items = (
        list_action_items(
            organisation_id=org_id,
            user=user,
            with_duplicate_count=False,
            accessible_shop_ids=accessible,
        )
        .filter(status__in=[ActionItem.Status.TODO, ActionItem.Status.IN_PROGRESS])
        .order_by()
        .values("pk")
        .count()
    )
    return NavSummary(
        reviews_awaiting_reply=reviews.order_by().values("pk").count(),
        open_action_items=open_items,
        credits=sum_credit_balances(shop_ids=shop_ids),
    )
