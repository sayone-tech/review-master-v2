"""Phase 11 — django-filter FilterSet for Review list endpoint."""

from __future__ import annotations

from typing import ClassVar

import django_filters  # type: ignore[import-untyped]
from django.contrib.postgres.search import SearchQuery
from django.db.models import Q

from apps.reviews.models import Review


class ReviewFilterSet(django_filters.FilterSet):  # type: ignore[misc]
    shop = django_filters.NumberFilter(field_name="shop_id")
    rating = django_filters.NumberFilter(field_name="star_rating")
    sentiment = django_filters.CharFilter(field_name="sentiment")
    is_replied = django_filters.BooleanFilter(field_name="is_replied")
    from_date = django_filters.DateFilter(field_name="review_create_time", lookup_expr="gte")
    to_date = django_filters.DateFilter(field_name="review_create_time", lookup_expr="lte")
    search = django_filters.CharFilter(method="filter_search")

    class Meta:
        model = Review
        fields: ClassVar[list[str]] = []

    def filter_search(self, queryset, name, value):  # type: ignore[no-untyped-def]
        if not value:
            return queryset
        q = SearchQuery(value, config="english")
        return queryset.filter(Q(search_vector=q) | Q(reviewer_display_name__icontains=value))
