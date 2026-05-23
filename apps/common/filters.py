"""Phase 21 plan 01 — Common app FilterSets (AuditLog query params).

D-07: Supported filters: entity_type, actor, date_from, date_to, shop.
"""

from __future__ import annotations

from typing import ClassVar

import django_filters  # type: ignore[import-untyped]

from apps.common.models import AuditLog


class AuditLogFilterSet(django_filters.FilterSet):  # type: ignore[misc]
    entity_type = django_filters.CharFilter(field_name="entity_type")
    actor = django_filters.CharFilter(method="filter_actor")
    date_from = django_filters.DateFilter(field_name="created_at", lookup_expr="gte")
    date_to = django_filters.DateFilter(field_name="created_at", lookup_expr="lte")
    shop = django_filters.NumberFilter(method="filter_shop")

    class Meta:
        model = AuditLog
        fields: ClassVar[list[str]] = []

    def filter_actor(self, qs, name, value):  # type: ignore[no-untyped-def]
        if value == "system":
            return qs.filter(actor__isnull=True)
        try:
            return qs.filter(actor_id=int(value))
        except (TypeError, ValueError):
            return qs

    def filter_shop(self, qs, name, value):  # type: ignore[no-untyped-def]
        # Lazy import to avoid pulling apps.reviews into apps.common import path.
        from apps.reviews.models import Review

        if value is None:
            return qs
        review_ids = [
            str(pk)
            for pk in Review.objects.filter(shop_id=value, deleted_at__isnull=True).values_list(
                "pk", flat=True
            )
        ]
        return qs.filter(entity_type="review", entity_id__in=review_ids)
