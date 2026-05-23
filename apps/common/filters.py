"""Phase 21 plan 01 — Common app FilterSets (AuditLog query params).

D-07: Supported filters: entity_type, actor, date_from, date_to, shop.
"""

from __future__ import annotations

from typing import ClassVar

import django_filters  # type: ignore[import-untyped]
from rest_framework.exceptions import ValidationError as DRFValidationError

from apps.common.models import AuditLog

# WR-01 fix: explicit whitelist for entity_type (D-07 restricts to these two).
ENTITY_TYPE_CHOICES = [
    ("review", "Review"),
    ("action_item", "Action Item"),
]


class AuditLogFilterSet(django_filters.FilterSet):  # type: ignore[misc]
    # WR-01: ChoiceFilter rejects values outside the whitelist with a 400.
    entity_type = django_filters.ChoiceFilter(
        field_name="entity_type",
        choices=ENTITY_TYPE_CHOICES,
    )
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
        from apps.reviews.selectors.reviews import get_accessible_shop_ids

        if value is None:
            return qs

        # WR-04: defence-in-depth — reject shop_ids the caller cannot access,
        # rather than silently returning an empty result set. Staff users get
        # a 400 with a clear message instead of an opaque empty page.
        request = getattr(self, "request", None)
        user = getattr(request, "user", None)
        if user is not None and getattr(user, "is_authenticated", False):
            from apps.accounts.models import User as UserModel

            role = getattr(user, "role", None)
            if role == UserModel.Role.STAFF_ADMIN:
                accessible = set(get_accessible_shop_ids(user_id=user.pk))
                if int(value) not in accessible:
                    raise DRFValidationError({"shop": "Shop is not accessible."})

        review_ids = [
            str(pk)
            for pk in Review.objects.filter(shop_id=value, deleted_at__isnull=True).values_list(
                "pk", flat=True
            )
        ]
        return qs.filter(entity_type="review", entity_id__in=review_ids)

    @property
    def qs(self):  # type: ignore[no-untyped-def]
        # WR-02 fix: validate date_from <= date_to as a cross-field rule.
        # django-filter's per-field validation does not cover this; raising
        # here lets DRF map it to HTTP 400 via its exception handler.
        data = self.data if hasattr(self, "data") else {}
        date_from = data.get("date_from")
        date_to = data.get("date_to")
        if date_from and date_to and date_from > date_to:
            raise DRFValidationError({"date_from": "date_from must be on or before date_to."})
        return super().qs
