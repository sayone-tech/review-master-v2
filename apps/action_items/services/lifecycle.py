"""Phase 13 plan 03 — ActionItem lifecycle services.

Write-side business logic for ActionItem: create, transition_status, assign,
add_note, promote_from_review. Every state change writes an AuditLog row
(ACTN-13). All single-row mutations use select_for_update inside
transaction.atomic to prevent races (CLAUDE.md §6.12).

promote_action_items_from_review converts Review.extracted_action_items JSON
to ActionItem rows idempotently via bulk_create(ignore_conflicts=True) backed
by the partial unique constraint added in plan 13-01.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.action_items.models import ActionItem, ActionItemNote
from apps.common.models import AuditLog

if TYPE_CHECKING:
    from apps.accounts.models import User
    from apps.reviews.models import Review


_PRIORITY_MAP = {
    "high": ActionItem.Priority.HIGH,
    "medium": ActionItem.Priority.MEDIUM,
    "low": ActionItem.Priority.LOW,
}
_SCOPE_MAP = {
    "shop": ActionItem.Scope.SHOP,
    "brand": ActionItem.Scope.BRAND,
}


@transaction.atomic
def create_action_item(
    *,
    organisation_id: int,
    title: str,
    scope: str,
    priority: str,
    source: str,
    actor: User,
    shop_id: int | None = None,
    assignee_id: int | None = None,
    due_date: Any = None,
    source_review_id: int | None = None,
    initial_note: str | None = None,
) -> ActionItem:
    """Create an ActionItem and write the action_item.created AuditLog row.

    If initial_note is non-empty, also calls add_note() in the same transaction
    (writes a second action_item.note_added AuditLog row).
    """
    if scope == ActionItem.Scope.SHOP and not shop_id:
        raise ValidationError("shop_id is required when scope=SHOP")
    item = ActionItem.objects.create(
        organisation_id=organisation_id,
        title=title,
        scope=scope,
        priority=priority,
        source=source,
        shop_id=shop_id if scope == ActionItem.Scope.SHOP else None,
        assignee_id=assignee_id,
        due_date=due_date,
        source_review_id=source_review_id,
    )
    AuditLog.objects.create(
        organisation_id=organisation_id,
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        entity_type="action_item",
        entity_id=str(item.pk),
        action="action_item.created",
        before_data={},
        after_data={
            "title": title,
            "scope": scope,
            "priority": priority,
            "status": item.status,
            "source": source,
            "shop_id": item.shop_id,
            "assignee_id": item.assignee_id,
        },
    )
    if initial_note:
        add_note(action_item=item, author=actor, body=initial_note)
    return item


# Status transitions allowed (ACTN-08): any-to-any between
#   TODO -> IN_PROGRESS -> COMPLETE -> WONT_DO and any reverse direction.
# No state machine validation - every status pair is legal.
@transaction.atomic
def transition_status(*, action_item: ActionItem, new_status: str, actor: User) -> ActionItem:
    locked = ActionItem.objects.select_for_update().get(pk=action_item.pk)
    old_status = locked.status
    if old_status == new_status:
        return locked
    locked.status = new_status
    locked.save(update_fields=["status", "updated_at"])
    AuditLog.objects.create(
        organisation_id=locked.organisation_id,
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        entity_type="action_item",
        entity_id=str(locked.pk),
        action="action_item.status_changed",
        before_data={"status": old_status},
        after_data={"status": new_status},
    )
    return locked


@transaction.atomic
def assign_action_item(
    *, action_item: ActionItem, assignee_id: int | None, actor: User
) -> ActionItem:
    locked = ActionItem.objects.select_for_update().get(pk=action_item.pk)
    old = locked.assignee_id
    if old == assignee_id:
        return locked
    locked.assignee_id = assignee_id
    locked.save(update_fields=["assignee", "updated_at"])
    AuditLog.objects.create(
        organisation_id=locked.organisation_id,
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        entity_type="action_item",
        entity_id=str(locked.pk),
        action="action_item.assigned",
        before_data={"assignee_id": old},
        after_data={"assignee_id": assignee_id},
    )
    return locked


@transaction.atomic
def add_note(*, action_item: ActionItem, author: User | None, body: str) -> ActionItemNote:
    body = (body or "").strip()
    if not (1 <= len(body) <= 2000):
        raise ValidationError("Note body must be 1-2000 characters")
    note = ActionItemNote.objects.create(
        action_item=action_item,
        author=author if author and getattr(author, "is_authenticated", False) else None,
        body=body,
    )
    AuditLog.objects.create(
        organisation_id=action_item.organisation_id,
        actor=author if author and getattr(author, "is_authenticated", False) else None,
        entity_type="action_item",
        entity_id=str(action_item.pk),
        action="action_item.note_added",
        before_data={},
        after_data={"note_id": note.pk, "body_preview": body[:80]},
    )
    return note


def promote_action_items_from_review(*, review: Review) -> int:
    """Idempotent JSON -> row promotion (ACTN-01).

    Caller MUST call AFTER the enrichment transaction commits (per
    13-RESEARCH.md Pitfall 3 — never wrap this in transaction.atomic from
    inside _persist_success).

    Returns the number of newly created ActionItem rows. A second call on the
    same Review returns 0 because of the partial unique constraint
    `ai_unique_per_review_title_scope` + bulk_create(ignore_conflicts=True).

    Skips entries with missing title or unknown scope.
    """
    items = review.extracted_action_items or []
    if not items:
        return 0
    pre_count = ActionItem.objects.filter(source_review=review).count()
    to_create: list[ActionItem] = []
    for entry in items:
        scope_val = _SCOPE_MAP.get((entry.get("scope") or "").lower())
        priority_val = _PRIORITY_MAP.get(
            (entry.get("priority") or "").lower(), ActionItem.Priority.MEDIUM
        )
        title = (entry.get("title") or "").strip()
        if not scope_val or not title:
            continue
        to_create.append(
            ActionItem(
                organisation_id=review.organisation_id,
                title=title[:200],
                scope=scope_val,
                priority=priority_val,
                source=ActionItem.Source.AI,
                shop_id=review.shop_id if scope_val == ActionItem.Scope.SHOP else None,
                source_review=review,
            )
        )
    if not to_create:
        return 0
    ActionItem.objects.bulk_create(to_create, ignore_conflicts=True)
    post_count = ActionItem.objects.filter(source_review=review).count()
    return max(0, post_count - pre_count)
