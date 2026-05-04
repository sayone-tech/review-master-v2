"""Phase 13 plan 03 — ActionItem selectors (read-side queries).

list_action_items implements Layer 1 of the three-layer Staff scope
(CLAUDE.md §9): Staff users see ONLY ActionItems with scope=SHOP that belong
to a shop in their StaffAccessScope. Brand-scoped items are NEVER returned
to Staff via the list endpoint.

Layer 2 (BrandScopeGuard permission) catches direct-URL access to brand items
on detail/mutation endpoints. Layer 3 (UI hiding) lives in plans 13-06/07.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db.models import QuerySet

from apps.action_items.models import ActionItem
from apps.reviews.selectors.reviews import get_accessible_shop_ids

if TYPE_CHECKING:
    from apps.accounts.models import User


def list_action_items(*, organisation_id: int, user: User) -> QuerySet[ActionItem]:
    """Return the ActionItem queryset scoped per role.

    - ORG_ADMIN: all action items in org
    - STAFF_ADMIN: only SHOP-scope items in accessible shops (Layer 1)
    - SUPERADMIN: empty (action items are org-scoped; superadmin uses other routes)
    """
    role = getattr(user, "role", None)
    if role == "SUPERADMIN":
        return ActionItem.objects.none()
    qs = ActionItem.objects.filter(organisation_id=organisation_id).select_related(
        "shop",
        "assignee",
        "source_review",
        "source_review__shop",
    )
    if role == "STAFF_ADMIN":
        accessible = get_accessible_shop_ids(user_id=user.pk)
        # CRITICAL Layer 1: Staff sees only SHOP-scope items in accessible shops.
        qs = qs.filter(scope=ActionItem.Scope.SHOP, shop_id__in=accessible)
    return qs.order_by("-created_at")


def get_action_item(*, organisation_id: int, user: User, pk: int) -> ActionItem | None:
    """Single-item fetch via the same scope filter as list_action_items."""
    return list_action_items(organisation_id=organisation_id, user=user).filter(pk=pk).first()
