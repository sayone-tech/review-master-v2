"""Phase 21 plan 01 — Audit log selectors with org + Staff scoping.

References CONTEXT decisions D-01 (only review reply + action_item events),
D-02 (org isolation enforced at selector layer from authenticated user), and
D-03 (Staff two-step scoping: materialise accessible entity_ids first, then
filter AuditLog).

Pattern 1 from 21-RESEARCH.md: the two-step Staff approach avoids leaking
brand-scope action items or inaccessible-shop review events through generic
entity_type/entity_id filtering — the visibility is decided by the source
entity row (Review.shop_id, ActionItem.scope+shop_id), not by AuditLog data.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db.models import Q, QuerySet

from apps.common.models import AuditLog

if TYPE_CHECKING:
    from apps.accounts.models import User


# D-01: Audit log surface is review-reply events + all action_item events.
# Other entity_types (e.g. shop_sync, enrichment.*) are excluded from the
# user-facing viewer in Phase 21.
AUDIT_ENTITY_FILTER = Q(entity_type="action_item") | Q(
    entity_type="review",
    action__in=["reply_posted", "reply_deleted", "reply_failed"],
)


def list_audit_logs_for_org(*, organisation_id: int) -> QuerySet[AuditLog]:
    """Return all audit log rows for an organisation (D-01, D-02).

    Used by ORG_ADMIN. No further scoping beyond org + entity filter.
    select_related('actor') prevents N+1 on actor_name serialization.
    """
    return (
        AuditLog.objects.filter(organisation_id=organisation_id)
        .filter(AUDIT_ENTITY_FILTER)
        .select_related("actor")
    )


def list_audit_logs_for_staff(*, organisation_id: int, user: User) -> QuerySet[AuditLog]:
    """Return audit log rows visible to a Staff user (D-03).

    Two-step scope:
      1. Materialise entity_ids the user can see — review PKs from accessible
         shops (and not soft-deleted) + ActionItem PKs with scope=SHOP in
         accessible shops.
      2. Filter AuditLog to entity_id__in=[...] on top of org + entity filter.
    """
    # Lazy imports to avoid circular dependency at module import time.
    from apps.action_items.models import ActionItem
    from apps.reviews.models import Review
    from apps.reviews.selectors.reviews import get_accessible_shop_ids

    accessible_shop_ids = get_accessible_shop_ids(user_id=user.pk)

    review_ids = [
        str(pk)
        for pk in Review.objects.filter(
            organisation_id=organisation_id,
            shop_id__in=accessible_shop_ids,
            deleted_at__isnull=True,
        ).values_list("pk", flat=True)
    ]
    action_item_ids = [
        str(pk)
        for pk in ActionItem.objects.filter(
            organisation_id=organisation_id,
            scope=ActionItem.Scope.SHOP,
            shop_id__in=accessible_shop_ids,
        ).values_list("pk", flat=True)
    ]
    # CR-01 fix: bind each entity_id list to its matching entity_type. Reviews
    # and ActionItems have independent integer PK sequences (PK collisions
    # across the two tables are routine), so a flat entity_id__in=[...] could
    # leak audit rows whose entity_type/entity_id pair maps to an inaccessible
    # entity (e.g. an inaccessible review's PK collides with an accessible
    # action item's PK). The Q(...) | Q(...) split makes the type+id pairing
    # authoritative — layer-1 defence per CLAUDE.md §9.
    return (
        AuditLog.objects.filter(organisation_id=organisation_id)
        .filter(AUDIT_ENTITY_FILTER)
        .filter(
            Q(entity_type="review", entity_id__in=review_ids)
            | Q(entity_type="action_item", entity_id__in=action_item_ids)
        )
        .select_related("actor")
    )
