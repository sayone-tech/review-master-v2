"""Phase 13 plan 03 — Tests for ActionItem lifecycle services."""

from __future__ import annotations

import pytest
from django.core.exceptions import ValidationError

from apps.accounts.tests.factories import OrgAdminFactory, UserFactory
from apps.action_items.models import ActionItem, ActionItemNote
from apps.action_items.services.lifecycle import (
    add_note,
    assign_action_item,
    create_action_item,
    promote_action_items_from_review,
    transition_status,
)
from apps.action_items.tests.factories import ActionItemFactory
from apps.common.models import AuditLog
from apps.organisations.tests.factories import OrganisationFactory
from apps.reviews.tests.factories import ReviewFactory
from apps.shops.tests.factories import ShopFactory


@pytest.mark.django_db
def test_create_action_item_writes_created_audit_log():
    org = OrganisationFactory()
    actor = OrgAdminFactory(organisation=org)
    shop = ShopFactory(organisation=org)
    item = create_action_item(
        organisation_id=org.pk,
        title="Fix espresso machine",
        scope=ActionItem.Scope.SHOP,
        priority=ActionItem.Priority.HIGH,
        source=ActionItem.Source.MANUAL,
        actor=actor,
        shop_id=shop.pk,
    )
    assert item.pk is not None
    logs = AuditLog.objects.filter(entity_type="action_item", entity_id=str(item.pk))
    assert logs.count() == 1
    log = logs.first()
    assert log.action == "action_item.created"
    assert log.after_data["title"] == "Fix espresso machine"


@pytest.mark.django_db
def test_create_action_item_with_initial_note_writes_two_audit_rows():
    org = OrganisationFactory()
    actor = OrgAdminFactory(organisation=org)
    shop = ShopFactory(organisation=org)
    item = create_action_item(
        organisation_id=org.pk,
        title="With note",
        scope=ActionItem.Scope.SHOP,
        priority=ActionItem.Priority.MEDIUM,
        source=ActionItem.Source.MANUAL,
        actor=actor,
        shop_id=shop.pk,
        initial_note="Initial note body",
    )
    logs = AuditLog.objects.filter(entity_type="action_item", entity_id=str(item.pk))
    assert logs.count() == 2
    actions = set(logs.values_list("action", flat=True))
    assert actions == {"action_item.created", "action_item.note_added"}
    assert ActionItemNote.objects.filter(action_item=item).count() == 1


@pytest.mark.django_db
def test_create_brand_scope_ignores_shop_id():
    org = OrganisationFactory()
    actor = OrgAdminFactory(organisation=org)
    item = create_action_item(
        organisation_id=org.pk,
        title="Brand item",
        scope=ActionItem.Scope.BRAND,
        priority=ActionItem.Priority.LOW,
        source=ActionItem.Source.MANUAL,
        actor=actor,
        shop_id=42,  # ignored because scope=BRAND
    )
    assert item.shop_id is None


@pytest.mark.django_db
def test_create_shop_scope_requires_shop_id():
    org = OrganisationFactory()
    actor = OrgAdminFactory(organisation=org)
    with pytest.raises(ValidationError):
        create_action_item(
            organisation_id=org.pk,
            title="Missing shop",
            scope=ActionItem.Scope.SHOP,
            priority=ActionItem.Priority.MEDIUM,
            source=ActionItem.Source.MANUAL,
            actor=actor,
            shop_id=None,
        )


@pytest.mark.django_db
def test_transition_status_writes_audit_log():
    item = ActionItemFactory(status=ActionItem.Status.TODO)
    actor = OrgAdminFactory(organisation=item.organisation)
    transition_status(
        action_item=item,
        new_status=ActionItem.Status.IN_PROGRESS,
        actor=actor,
    )
    logs = AuditLog.objects.filter(
        entity_type="action_item",
        entity_id=str(item.pk),
        action="action_item.status_changed",
    )
    assert logs.count() == 1
    log = logs.first()
    assert log.before_data == {"status": "TODO"}
    assert log.after_data == {"status": "IN_PROGRESS"}


@pytest.mark.django_db
def test_todo_to_in_progress_auto_assigns_actor_when_unassigned():
    item = ActionItemFactory(status=ActionItem.Status.TODO, assignee=None)
    actor = OrgAdminFactory(organisation=item.organisation)
    transition_status(action_item=item, new_status=ActionItem.Status.IN_PROGRESS, actor=actor)
    item.refresh_from_db()
    assert item.assignee_id == actor.pk
    assert (
        AuditLog.objects.filter(
            entity_type="action_item",
            entity_id=str(item.pk),
            action="action_item.assigned",
        ).count()
        == 1
    )


@pytest.mark.django_db
def test_todo_to_in_progress_does_not_override_existing_assignee():
    org = OrganisationFactory()
    existing_assignee = UserFactory(organisation=org)
    item = ActionItemFactory(
        status=ActionItem.Status.TODO,
        organisation=org,
        assignee=existing_assignee,
    )
    actor = OrgAdminFactory(organisation=org)
    transition_status(action_item=item, new_status=ActionItem.Status.IN_PROGRESS, actor=actor)
    item.refresh_from_db()
    assert item.assignee_id == existing_assignee.pk
    assert (
        AuditLog.objects.filter(
            entity_type="action_item",
            entity_id=str(item.pk),
            action="action_item.assigned",
        ).count()
        == 0
    )


@pytest.mark.django_db
def test_other_transitions_do_not_auto_assign():
    item = ActionItemFactory(status=ActionItem.Status.IN_PROGRESS, assignee=None)
    actor = OrgAdminFactory(organisation=item.organisation)
    transition_status(action_item=item, new_status=ActionItem.Status.COMPLETE, actor=actor)
    item.refresh_from_db()
    assert item.assignee_id is None


@pytest.mark.django_db
def test_transition_status_no_op_on_same_status():
    item = ActionItemFactory(status=ActionItem.Status.TODO)
    actor = OrgAdminFactory(organisation=item.organisation)
    transition_status(
        action_item=item,
        new_status=ActionItem.Status.TODO,
        actor=actor,
    )
    assert (
        AuditLog.objects.filter(
            entity_type="action_item",
            entity_id=str(item.pk),
            action="action_item.status_changed",
        ).count()
        == 0
    )


_STATUSES = [
    ActionItem.Status.TODO,
    ActionItem.Status.IN_PROGRESS,
    ActionItem.Status.COMPLETE,
    ActionItem.Status.WONT_DO,
]


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("from_status", "to_status"),
    [(a, b) for a in _STATUSES for b in _STATUSES if a != b],
)
def test_all_status_transitions_legal(from_status, to_status):
    item = ActionItemFactory(status=from_status)
    actor = OrgAdminFactory(organisation=item.organisation)
    transition_status(action_item=item, new_status=to_status, actor=actor)
    item.refresh_from_db()
    assert item.status == to_status
    assert (
        AuditLog.objects.filter(
            entity_type="action_item",
            entity_id=str(item.pk),
            action="action_item.status_changed",
        ).count()
        == 1
    )


@pytest.mark.django_db
def test_assign_action_item_writes_audit_log():
    item = ActionItemFactory()
    actor = OrgAdminFactory(organisation=item.organisation)
    assignee = UserFactory(organisation=item.organisation)
    assign_action_item(action_item=item, assignee_id=assignee.pk, actor=actor)
    item.refresh_from_db()
    assert item.assignee_id == assignee.pk
    logs = AuditLog.objects.filter(
        entity_type="action_item",
        entity_id=str(item.pk),
        action="action_item.assigned",
    )
    assert logs.count() == 1
    log = logs.first()
    assert log.before_data == {"assignee_id": None}
    assert log.after_data == {"assignee_id": assignee.pk}


@pytest.mark.django_db
def test_add_note_validates_length():
    item = ActionItemFactory()
    actor = OrgAdminFactory(organisation=item.organisation)
    with pytest.raises(ValidationError):
        add_note(action_item=item, author=actor, body="")
    with pytest.raises(ValidationError):
        add_note(action_item=item, author=actor, body="x" * 2001)


@pytest.mark.django_db
def test_add_note_creates_row_and_audit():
    item = ActionItemFactory()
    actor = OrgAdminFactory(organisation=item.organisation)
    note = add_note(action_item=item, author=actor, body="A valid note body")
    assert note.pk is not None
    assert note.body == "A valid note body"
    logs = AuditLog.objects.filter(
        entity_type="action_item",
        entity_id=str(item.pk),
        action="action_item.note_added",
    )
    assert logs.count() == 1
    log = logs.first()
    assert log.after_data["note_id"] == note.pk
    assert log.after_data["body_preview"] == "A valid note body"


@pytest.mark.django_db
def test_promote_action_items_from_review_creates_rows():
    org = OrganisationFactory()
    shop = ShopFactory(organisation=org)
    review = ReviewFactory(
        organisation=org,
        shop=shop,
        extracted_action_items=[
            {"title": "Fix espresso machine", "scope": "shop", "priority": "high"},
            {"title": "Update brand voice", "scope": "brand", "priority": "low"},
        ],
    )
    created = promote_action_items_from_review(review=review)
    assert created == 2
    items = list(ActionItem.objects.filter(source_review=review).order_by("title"))
    assert len(items) == 2
    by_scope = {i.scope: i for i in items}
    shop_item = by_scope[ActionItem.Scope.SHOP]
    brand_item = by_scope[ActionItem.Scope.BRAND]
    assert shop_item.shop_id == shop.pk
    assert shop_item.priority == ActionItem.Priority.HIGH
    assert shop_item.source == ActionItem.Source.AI
    assert brand_item.shop_id is None
    assert brand_item.priority == ActionItem.Priority.LOW


@pytest.mark.django_db
def test_promote_action_items_from_review_idempotent():
    org = OrganisationFactory()
    shop = ShopFactory(organisation=org)
    review = ReviewFactory(
        organisation=org,
        shop=shop,
        extracted_action_items=[
            {"title": "Fix espresso machine", "scope": "shop", "priority": "high"},
            {"title": "Update brand voice", "scope": "brand", "priority": "low"},
        ],
    )
    first = promote_action_items_from_review(review=review)
    second = promote_action_items_from_review(review=review)
    assert first == 2
    assert second == 0
    assert ActionItem.objects.filter(source_review=review).count() == 2


@pytest.mark.django_db
def test_promote_skips_invalid_entries():
    org = OrganisationFactory()
    shop = ShopFactory(organisation=org)
    review = ReviewFactory(
        organisation=org,
        shop=shop,
        extracted_action_items=[
            {"title": "Valid", "scope": "shop", "priority": "medium"},
            {"title": "", "scope": "shop", "priority": "high"},  # missing title
            {"title": "Bad scope", "scope": "global", "priority": "low"},  # unknown scope
        ],
    )
    created = promote_action_items_from_review(review=review)
    assert created == 1
    assert ActionItem.objects.filter(source_review=review).count() == 1


@pytest.mark.django_db
def test_promote_maps_category_correctly():
    org = OrganisationFactory()
    shop = ShopFactory(organisation=org)
    review = ReviewFactory(
        organisation=org,
        shop=shop,
        extracted_action_items=[
            {"title": "Fix cold food", "scope": "shop", "priority": "high", "category": "quality"},
            {"title": "Train staff", "scope": "brand", "priority": "medium", "category": "service"},
        ],
    )
    promote_action_items_from_review(review=review)
    items = {i.title: i for i in ActionItem.objects.filter(source_review=review)}
    assert items["Fix cold food"].category == ActionItem.Category.QUALITY
    assert items["Train staff"].category == ActionItem.Category.SERVICE


@pytest.mark.django_db
def test_promote_category_falls_back_to_other_when_missing():
    org = OrganisationFactory()
    shop = ShopFactory(organisation=org)
    review = ReviewFactory(
        organisation=org,
        shop=shop,
        extracted_action_items=[
            {"title": "Fix entrance sign", "scope": "shop", "priority": "low"},
        ],
    )
    promote_action_items_from_review(review=review)
    item = ActionItem.objects.get(source_review=review)
    assert item.category == ActionItem.Category.OTHER


@pytest.mark.django_db
def test_promote_category_falls_back_to_other_on_unknown_value():
    org = OrganisationFactory()
    shop = ShopFactory(organisation=org)
    review = ReviewFactory(
        organisation=org,
        shop=shop,
        extracted_action_items=[
            {"title": "Do something", "scope": "shop", "priority": "low", "category": "invented"},
        ],
    )
    promote_action_items_from_review(review=review)
    item = ActionItem.objects.get(source_review=review)
    assert item.category == ActionItem.Category.OTHER
