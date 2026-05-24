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
from django.db.models import Prefetch

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
_CATEGORY_MAP = {
    "quality": ActionItem.Category.QUALITY,
    "service": ActionItem.Category.SERVICE,
    "experience": ActionItem.Category.EXPERIENCE,
    "operations": ActionItem.Category.OPERATIONS,
    "other": ActionItem.Category.OTHER,
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

    # Phase 13-05: notify the assignee (if any, and if not the actor) AFTER commit.
    # transaction.on_commit defers the call until the @transaction.atomic block
    # commits, so a rollback never produces a phantom notification.
    actor_pk = getattr(actor, "pk", None)
    item_assignee_id: int | None = item.assignee_id
    if item_assignee_id is not None and item_assignee_id != actor_pk:
        # Local import avoids the notifications<->action_items app cycle.
        from apps.notifications.services.dispatch import dispatch_notification

        assignee_pk: int = item_assignee_id
        item_pk = item.pk
        item_title = item.title

        def _notify_assignee() -> None:
            dispatch_notification(
                organisation_id=organisation_id,
                notification_type="action_item_assigned",
                title=f"You've been assigned: {item_title}",
                target_url=f"/admin/org/action-items/?id={item_pk}",
                action_item=item,
                recipient_ids=[assignee_pk],
            )

        transaction.on_commit(_notify_assignee)
    return item


# Status transitions allowed (ACTN-08): any-to-any between
#   TODO -> IN_PROGRESS -> COMPLETE -> WONT_DO and any reverse direction.
# No state machine validation - every status pair is legal.
@transaction.atomic
def transition_status(*, action_item: ActionItem, new_status: str, actor: User) -> ActionItem:
    # Phase 18 (WR-02 fix): pre-lock check is a fast-path; the authoritative
    # check is re-run on the locked row to close the TOCTOU window between
    # the view's get_object() snapshot and select_for_update().
    if action_item.canonical_id is not None:
        raise ValidationError("Cannot modify a merged duplicate.")
    locked = ActionItem.objects.select_for_update().get(pk=action_item.pk)
    if locked.canonical_id is not None:
        raise ValidationError("Cannot modify a merged duplicate.")
    old_status = locked.status
    if old_status == new_status:
        return locked
    locked.status = new_status

    # Auto-assign to the actor when claiming an item (TODO → IN_PROGRESS).
    # Only fires when the item is currently unassigned — explicit assignments
    # made by an admin are not overridden.
    actor_pk = getattr(actor, "pk", None)
    prev_assignee_id = locked.assignee_id
    auto_assigned = (
        old_status == ActionItem.Status.TODO
        and new_status == ActionItem.Status.IN_PROGRESS
        and locked.assignee_id is None
        and actor_pk is not None
    )
    if auto_assigned:
        locked.assignee_id = actor_pk
        locked.save(update_fields=["status", "assignee", "updated_at"])
    else:
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
    if auto_assigned:
        AuditLog.objects.create(
            organisation_id=locked.organisation_id,
            actor=actor if getattr(actor, "is_authenticated", False) else None,
            entity_type="action_item",
            entity_id=str(locked.pk),
            action="action_item.assigned",
            before_data={"assignee_id": prev_assignee_id},
            after_data={"assignee_id": actor_pk},
        )

    return locked


@transaction.atomic
def assign_action_item(
    *, action_item: ActionItem, assignee_id: int | None, actor: User
) -> ActionItem:
    # Phase 18 (WR-02 fix): pre-lock check is a fast-path; the authoritative
    # check is re-run on the locked row to close the TOCTOU window between
    # the view's get_object() snapshot and select_for_update().
    if action_item.canonical_id is not None:
        raise ValidationError("Cannot modify a merged duplicate.")
    locked = ActionItem.objects.select_for_update().get(pk=action_item.pk)
    if locked.canonical_id is not None:
        raise ValidationError("Cannot modify a merged duplicate.")
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

    # Phase 13-05: notify the new assignee (if any, and if not the actor)
    # AFTER the transaction commits — never on rollback.
    actor_pk = getattr(actor, "pk", None)
    if assignee_id is not None and assignee_id != actor_pk:
        # Local import avoids the notifications<->action_items app cycle.
        from apps.notifications.services.dispatch import dispatch_notification

        assignee_pk: int = assignee_id
        item_pk = locked.pk
        item_title = locked.title
        item_org_id = locked.organisation_id

        def _notify_new_assignee() -> None:
            dispatch_notification(
                organisation_id=item_org_id,
                notification_type="action_item_assigned",
                title=f"You've been assigned: {item_title}",
                target_url=f"/admin/org/action-items/?id={item_pk}",
                action_item=locked,
                recipient_ids=[assignee_pk],
            )

        transaction.on_commit(_notify_new_assignee)
    return locked


@transaction.atomic
def add_note(*, action_item: ActionItem, author: User | None, body: str) -> ActionItemNote:
    # Phase 18 (WR-02 fix): pre-lock check is a fast-path; lock the row and
    # re-check canonical_id to close the TOCTOU window between get_object()
    # and the note insert. Notes are append-only, so a stale-snapshot insert
    # cannot be undone — closing this window matters more here than for the
    # status / assign transitions.
    if action_item.canonical_id is not None:
        raise ValidationError("Cannot modify a merged duplicate.")
    body = (body or "").strip()
    if not (1 <= len(body) <= 2000):
        raise ValidationError("Note body must be 1-2000 characters")
    locked = ActionItem.objects.select_for_update().get(pk=action_item.pk)
    if locked.canonical_id is not None:
        raise ValidationError("Cannot modify a merged duplicate.")
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
        category_val = _CATEGORY_MAP.get(
            (entry.get("category") or "").lower(), ActionItem.Category.OTHER
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
                category=category_val,
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


@transaction.atomic
def merge_action_items(
    *,
    primary_id: int,
    duplicate_ids: list[int],
    actor: User,
    organisation_id: int,
) -> ActionItem:
    """Mark duplicate_ids as duplicates of primary_id (D-14/D-15).

    Validates same-org, same-scope (D-05), source=AI only (D-06), primary has
    no canonical (D-08), and re-parents any sub-duplicates of the selected
    duplicate_ids BEFORE marking them (D-09).

    Locks all involved rows in ascending PK order to prevent deadlocks.
    Writes one AuditLog row: action="action_item.merged".
    """
    if not duplicate_ids:
        raise ValidationError("duplicate_ids must not be empty.")
    if primary_id in duplicate_ids:
        raise ValidationError("primary_id must not be in duplicate_ids.")
    if len(set(duplicate_ids)) != len(duplicate_ids):
        raise ValidationError("duplicate_ids must be unique.")

    # Phase 18 (WR-03 fix): resolve sub-duplicates BEFORE acquiring the lock
    # so the SELECT FOR UPDATE covers every row this transaction will write
    # to. The re-parent statement below mutates rows whose canonical_id is in
    # duplicate_ids — if we don't lock them here, a concurrent merge that
    # picks one of those sub-duplicates as a primary in a different
    # transaction can interleave and produce an inconsistent canonical chain.
    sub_dup_ids = list(
        ActionItem.objects.filter(
            canonical_id__in=duplicate_ids, organisation_id=organisation_id
        ).values_list("pk", flat=True)
    )
    all_ids = sorted({primary_id, *duplicate_ids, *sub_dup_ids})
    selected_ids = {primary_id, *duplicate_ids}

    # Lock rows in PK order to prevent deadlocks; org filter validates ownership.
    locked = list(
        ActionItem.objects.select_for_update()
        .filter(pk__in=all_ids, organisation_id=organisation_id)
        .order_by("pk")
    )
    # Only the directly-selected rows (primary + duplicate_ids) need to all
    # exist; sub-duplicates are discovered by query and may legitimately
    # vanish between the resolve and the lock (e.g. a concurrent operation
    # already moved them) — the re-parent UPDATE handles any remaining ones.
    locked_ids = {item.pk for item in locked}
    if not selected_ids.issubset(locked_ids):
        raise ValidationError("One or more action items not found in this organisation.")

    by_pk = {item.pk: item for item in locked}
    primary = by_pk[primary_id]

    # D-08: primary must not already be a duplicate.
    if primary.canonical_id is not None:
        raise ValidationError("Primary is already a merged duplicate.")

    # D-06: all directly-selected items must be AI-sourced. Sub-duplicates
    # (already merged in a prior transaction) are not re-validated here — they
    # passed D-06 when they were originally merged.
    # Phase 18 (WR-05 fix): distinguish primary vs. duplicates in the error
    # so the frontend can show a useful toast. Previously the generic
    # "Only AI-sourced action items can be merged" message left users
    # guessing which row was rejected.
    selected_items = [by_pk[pk] for pk in selected_ids]
    if primary.source != ActionItem.Source.AI:
        raise ValidationError("Primary must be an AI-sourced action item.")
    non_ai_dup_ids = [
        i.pk for i in selected_items if i.pk != primary_id and i.source != ActionItem.Source.AI
    ]
    if non_ai_dup_ids:
        raise ValidationError(
            f"Only AI-sourced items can be merged. Non-AI duplicates: {non_ai_dup_ids}"
        )

    # D-05: all directly-selected items must have the same scope.
    scopes = {item.scope for item in selected_items}
    if len(scopes) > 1:
        raise ValidationError("All merged items must share the same scope.")

    # D-05 (extended): SHOP-scope items must also share the same shop_id —
    # merging "Fix broken AC" from Shop A with "Fix broken AC" from Shop B
    # would collapse two genuinely distinct operational issues into one
    # canonical row, breaking per-shop accountability and confusing the
    # "Also reported in" UI (which assumes duplicates corroborate the same
    # underlying issue at the same location). For BRAND-scope items shop_id
    # is always None, so this constraint is naturally satisfied.
    shop_ids = {item.shop_id for item in selected_items}
    if len(shop_ids) > 1:
        raise ValidationError("Shop-scope items can only be merged with items from the same shop.")

    # D-09: re-parent sub-duplicates of selected duplicates onto primary FIRST.
    # Phase 18 (WR-04 fix): capture the old canonical_id for each
    # sub-duplicate BEFORE the update so we can write a per-row AuditLog
    # entry. Without these entries, querying the audit trail by the
    # sub-duplicate's entity_id would show no record of it being silently
    # moved onto a different canonical.
    sub_dup_before = [(item.pk, item.canonical_id) for item in locked if item.pk in sub_dup_ids]
    ActionItem.objects.filter(canonical_id__in=duplicate_ids).update(canonical_id=primary_id)

    # Now mark the selected duplicates.
    ActionItem.objects.filter(pk__in=duplicate_ids).update(canonical_id=primary_id)

    AuditLog.objects.create(
        organisation_id=primary.organisation_id,
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        entity_type="action_item",
        entity_id=str(primary.pk),
        action="action_item.merged",
        before_data={},
        after_data={"merged_ids": list(duplicate_ids)},
    )

    # Phase 18 (WR-04 fix): one AuditLog row per re-parented sub-duplicate so
    # the per-entity audit trail records the canonical change. Bulk-create
    # keeps the query count constant regardless of sub-duplicate count.
    if sub_dup_before:
        actor_obj = actor if getattr(actor, "is_authenticated", False) else None
        AuditLog.objects.bulk_create(
            [
                AuditLog(
                    organisation_id=primary.organisation_id,
                    actor=actor_obj,
                    entity_type="action_item",
                    entity_id=str(sub_pk),
                    action="action_item.canonical_changed",
                    before_data={"canonical_id": old_canonical_id},
                    after_data={"canonical_id": primary_id},
                )
                for sub_pk, old_canonical_id in sub_dup_before
            ]
        )

    return ActionItem.objects.prefetch_related(
        Prefetch(
            "duplicates",
            queryset=ActionItem.objects.select_related("shop", "source_review"),
        )
    ).get(pk=primary_id)
