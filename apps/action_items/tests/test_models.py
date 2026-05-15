"""Phase 13 — Tests for ActionItem and ActionItemNote models."""

from __future__ import annotations

import pytest
from django.db import connection

from apps.action_items.models import ActionItem
from apps.action_items.tests.factories import (
    ActionItemFactory,
    ActionItemNoteFactory,
)
from apps.reviews.tests.factories import ReviewFactory


@pytest.mark.django_db
def test_create_action_item_defaults() -> None:
    item = ActionItemFactory()
    assert item.status == ActionItem.Status.TODO
    assert item.source == ActionItem.Source.MANUAL
    assert item.priority == ActionItem.Priority.MEDIUM
    assert item.scope == ActionItem.Scope.SHOP
    assert item.shop is not None


@pytest.mark.django_db
def test_action_item_str() -> None:
    item = ActionItemFactory(title="Fix the door")
    s = str(item)
    assert "Fix the door" in s
    assert item.status in s


@pytest.mark.django_db
def test_action_item_note_oldest_first() -> None:
    item = ActionItemFactory()
    n1 = ActionItemNoteFactory(action_item=item, body="first")
    n2 = ActionItemNoteFactory(action_item=item, body="second")
    n3 = ActionItemNoteFactory(action_item=item, body="third")
    notes = list(item.notes.all())
    assert notes == [n1, n2, n3]
    assert notes[0].created_at <= notes[1].created_at <= notes[2].created_at


@pytest.mark.skipif(
    connection.vendor != "postgresql",
    reason="Partial unique constraints require PostgreSQL",
)
@pytest.mark.django_db
def test_partial_unique_ai_per_review_title_scope() -> None:
    review = ReviewFactory()
    first = ActionItemFactory(
        organisation=review.organisation,
        source=ActionItem.Source.AI,
        source_review=review,
        title="Train staff on coffee",
        scope=ActionItem.Scope.SHOP,
        shop=review.shop,
    )
    duplicate = ActionItem(
        organisation=review.organisation,
        source=ActionItem.Source.AI,
        source_review=review,
        title="Train staff on coffee",
        scope=ActionItem.Scope.SHOP,
        shop=review.shop,
        priority=ActionItem.Priority.MEDIUM,
        status=ActionItem.Status.TODO,
    )
    ActionItem.objects.bulk_create([duplicate], ignore_conflicts=True)
    assert ActionItem.objects.filter(source_review=review).count() == 1
    assert ActionItem.objects.filter(source_review=review).first().pk == first.pk


@pytest.mark.django_db
def test_partial_unique_does_not_apply_to_manual() -> None:
    org_item = ActionItemFactory(
        source=ActionItem.Source.MANUAL,
        title="Repeat manual title",
        scope=ActionItem.Scope.SHOP,
        source_review=None,
    )
    ActionItemFactory(
        organisation=org_item.organisation,
        source=ActionItem.Source.MANUAL,
        title="Repeat manual title",
        scope=ActionItem.Scope.SHOP,
        source_review=None,
    )
    qs = ActionItem.objects.filter(title="Repeat manual title", source=ActionItem.Source.MANUAL)
    assert qs.count() == 2


@pytest.mark.django_db
def test_brand_item_allows_null_shop() -> None:
    item = ActionItemFactory(scope=ActionItem.Scope.BRAND, shop=None)
    item.refresh_from_db()
    assert item.shop is None
    assert item.scope == ActionItem.Scope.BRAND


@pytest.mark.django_db
def test_action_item_category_defaults_to_other() -> None:
    item = ActionItemFactory()
    assert item.category == ActionItem.Category.OTHER
