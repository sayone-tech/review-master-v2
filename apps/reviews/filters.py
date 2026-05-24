"""Phase 11 — django-filter FilterSet for Review list endpoint."""

from __future__ import annotations

from typing import ClassVar

import django_filters  # type: ignore[import-untyped]
from django.contrib.postgres.search import SearchQuery
from django.db.models import Exists, OuterRef, Q

from apps.reviews.models import Review, ReviewTag


class ReviewFilterSet(django_filters.FilterSet):  # type: ignore[misc]
    shop = django_filters.NumberFilter(field_name="shop_id")
    rating = django_filters.NumberFilter(field_name="star_rating")
    sentiment = django_filters.CharFilter(field_name="sentiment")
    is_replied = django_filters.BooleanFilter(field_name="is_replied")
    has_comment = django_filters.BooleanFilter(method="filter_has_comment")
    from_date = django_filters.DateFilter(field_name="review_create_time", lookup_expr="gte")
    to_date = django_filters.DateFilter(field_name="review_create_time", lookup_expr="lte")
    search = django_filters.CharFilter(method="filter_search")
    tags = django_filters.CharFilter(field_name="", method="filter_tags")

    class Meta:
        model = Review
        fields: ClassVar[list[str]] = []

    def filter_has_comment(self, queryset, name, value):  # type: ignore[no-untyped-def]
        if value:
            return queryset.exclude(comment="")
        return queryset.filter(comment="")

    def filter_search(self, queryset, name, value):  # type: ignore[no-untyped-def]
        if not value:
            return queryset
        q = SearchQuery(value, config="english")
        return queryset.filter(Q(search_vector=q) | Q(reviewer_display_name__icontains=value))

    def filter_tags(self, queryset, name, value):  # type: ignore[no-untyped-def]
        # Phase 17 CR-01/WR-01/WR-06: use Exists(OuterRef) per label rather than
        # chained joins on `tags__label__iexact`. The previous JOIN-based
        # implementation row-multiplied reviews that carried multiple matching
        # tag rows, which corrupted non-COUNT aggregates (Avg, filtered Counts)
        # in the stats endpoint and made the query plan scale as N self-joins
        # in the list endpoint. With Exists() each label becomes one correlated
        # subquery against the indexed (review, label) columns, no row
        # multiplication, and `.distinct()` is no longer required.
        if not value:
            return queryset
        tag_labels = [t.strip() for t in value.split(",") if t.strip()]
        for label in tag_labels:
            sub = ReviewTag.objects.filter(review=OuterRef("pk"), label__iexact=label)
            queryset = queryset.filter(Exists(sub))
        return queryset
