from __future__ import annotations

from django.db import models


class ReviewQuerySet(models.QuerySet):  # type: ignore[type-arg]
    def active(self) -> ReviewQuerySet:
        return self.filter(deleted_at__isnull=True)

    def for_organisation(self, organisation_id: int) -> ReviewQuerySet:
        return self.filter(organisation_id=organisation_id)

    def for_shops(self, shop_ids: list[int]) -> ReviewQuerySet:
        return self.filter(shop_id__in=shop_ids)

    def replied(self, replied: bool = True) -> ReviewQuerySet:
        return self.filter(is_replied=replied)
