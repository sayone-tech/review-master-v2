"""Phase 13 — Factories for ActionItem and ActionItemNote."""

from __future__ import annotations

import factory
from factory.django import DjangoModelFactory

from apps.action_items.models import ActionItem, ActionItemNote
from apps.organisations.tests.factories import OrganisationFactory
from apps.shops.tests.factories import ShopFactory


class ActionItemFactory(DjangoModelFactory):
    class Meta:
        model = ActionItem

    organisation = factory.SubFactory(OrganisationFactory)
    title = factory.Sequence(lambda n: f"Action item {n}")
    status = ActionItem.Status.TODO
    scope = ActionItem.Scope.SHOP
    priority = ActionItem.Priority.MEDIUM
    source = ActionItem.Source.MANUAL
    shop = factory.LazyAttribute(lambda o: ShopFactory(organisation=o.organisation))
    assignee = None
    due_date = None
    source_review = None


class ActionItemNoteFactory(DjangoModelFactory):
    class Meta:
        model = ActionItemNote

    action_item = factory.SubFactory(ActionItemFactory)
    author = None
    body = factory.Sequence(lambda n: f"Note body {n}")
