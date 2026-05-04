"""Phase 13 plan 04 — django-filter FilterSet for ActionItem list endpoint."""

from __future__ import annotations

from typing import ClassVar

import django_filters  # type: ignore[import-untyped]
from django.db.models import Q

from apps.action_items.models import ActionItem


class ActionItemFilterSet(django_filters.FilterSet):  # type: ignore[misc]
    shop = django_filters.NumberFilter(field_name="shop_id")
    status = django_filters.ChoiceFilter(choices=ActionItem.Status.choices)
    scope = django_filters.ChoiceFilter(choices=ActionItem.Scope.choices)
    assignee = django_filters.CharFilter(method="filter_assignee")
    from_date = django_filters.DateFilter(field_name="created_at", lookup_expr="gte")
    to_date = django_filters.DateFilter(field_name="created_at", lookup_expr="lte")
    search = django_filters.CharFilter(method="filter_search")
    review = django_filters.NumberFilter(field_name="source_review_id")

    class Meta:
        model = ActionItem
        fields: ClassVar[list[str]] = []

    def filter_assignee(self, qs, name, value):  # type: ignore[no-untyped-def]
        if value == "unassigned":
            return qs.filter(assignee__isnull=True)
        if value == "me":
            user = getattr(self.request, "user", None) if hasattr(self, "request") else None
            return qs.filter(assignee=user) if user and user.is_authenticated else qs
        try:
            return qs.filter(assignee_id=int(value))
        except (TypeError, ValueError):
            return qs

    def filter_search(self, qs, name, value):  # type: ignore[no-untyped-def]
        if not value:
            return qs
        return qs.filter(Q(title__icontains=value) | Q(notes__body__icontains=value)).distinct()
