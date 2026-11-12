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

from django.db.models import Case, CharField, OuterRef, Q, QuerySet, Subquery, Value, When
from django.db.models.expressions import Expression
from django.db.models.functions import Cast

from apps.common.models import AuditLog

if TYPE_CHECKING:
    from apps.accounts.models import User


# CVIS-07: tenants never see a Superadmin's name or id. Their actions show as one
# generic platform actor, and the actor filter accepts this id for them.
PLATFORM_ACTOR_ID = "platform"
PLATFORM_ACTOR_LABEL = "ReviewBee Admin"


def is_platform_actor(actor: object) -> bool:
    """True when the audit actor is a Superadmin (platform staff)."""
    from apps.accounts.models import User

    return getattr(actor, "role", None) == User.Role.SUPERADMIN


# D-01: Audit log surface is review-reply events + all action_item events.
# Other entity_types (e.g. shop_sync, enrichment.*) are excluded from the
# user-facing viewer in Phase 21.
AUDIT_ENTITY_FILTER = Q(entity_type="action_item") | Q(
    entity_type="review",
    # CVIS-06: ai_reply_generated carries no credit numbers, so Staff may see it.
    action__in=["reply_posted", "reply_deleted", "reply_failed", "ai_reply_generated"],
)

# CVIS-05: credit events (per-shop ledger actions + the org-level monthly
# allocation edit) are visible to ORG ADMINS ONLY. This constant is used by
# ``list_audit_logs_for_org`` alone and must never be folded into
# AUDIT_ENTITY_FILTER, which the Staff selector shares.
CREDIT_AUDIT_FILTER = Q(entity_type="shop", action__startswith="shop.credits.") | Q(
    entity_type="organisation", action="organisation.credits.set"
)


def _shop_name_annotation() -> Expression:
    """Resolve the shop name for ``entity_type="shop"`` rows only (CVIS-05).

    ``AuditLog.entity_id`` is an untyped CharField shared by every entity type,
    so the lookup is (a) gated on ``entity_type="shop"`` (a review/action item
    whose PK collides with a shop PK must not borrow its name), (b) bound to the
    row's own organisation (no other tenant's name can leak) and (c) compared as
    TEXT (a non-numeric ``entity_id`` can never raise on PostgreSQL). It is one
    correlated subquery in the same SELECT, so the query count stays fixed.
    """
    from apps.shops.models import Shop

    shop_name = (
        Shop.objects.filter(organisation_id=OuterRef("organisation_id"))
        .annotate(_pk_text=Cast("pk", output_field=CharField()))
        .filter(_pk_text=OuterRef("entity_id"))
        .values("name")[:1]
    )
    return Case(
        When(entity_type="shop", then=Subquery(shop_name)),
        default=Value(None),
        output_field=CharField(),
    )


def list_audit_logs_for_org(*, organisation_id: int) -> QuerySet[AuditLog]:
    """Return all audit log rows for an organisation (D-01, D-02, CVIS-05).

    Used by ORG_ADMIN. No further scoping beyond org + entity filter; credit
    events are included (CVIS-05) and each row carries a ``shop_name``
    annotation (None unless it is a same-org shop row).
    select_related('actor') prevents N+1 on actor_name serialization.
    """
    return (
        AuditLog.objects.filter(organisation_id=organisation_id)
        .filter(AUDIT_ENTITY_FILTER | CREDIT_AUDIT_FILTER)
        .annotate(shop_name=_shop_name_annotation())
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
