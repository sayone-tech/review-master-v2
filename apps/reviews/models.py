"""Phase 11 — Review and Reply models.

A Review row mirrors a Google Business Profile review identified by
(shop_id, google_review_id). Re-fetches use update_or_create / bulk_create
with update_conflicts=True so duplicates can never be created.
"""

from __future__ import annotations

from typing import ClassVar

from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField
from django.db import models

from apps.common.models import TimeStampedModel
from apps.reviews.managers import ReviewQuerySet


class Review(TimeStampedModel):
    class StarRating(models.IntegerChoices):
        ONE = 1, "One"
        TWO = 2, "Two"
        THREE = 3, "Three"
        FOUR = 4, "Four"
        FIVE = 5, "Five"

    class EnrichmentStatus(models.TextChoices):
        PENDING = "PENDING", "Pending"
        IN_PROGRESS = "IN_PROGRESS", "In Progress"
        SUCCESS = "SUCCESS", "Success"
        FAILED = "FAILED", "Failed"

    organisation = models.ForeignKey(
        "organisations.Organisation",
        on_delete=models.CASCADE,
        related_name="reviews",
        db_index=True,
    )
    shop = models.ForeignKey(
        "shops.Shop",
        on_delete=models.CASCADE,
        related_name="reviews",
    )
    google_review_id = models.CharField(max_length=200, db_index=True)
    google_account_id = models.CharField(max_length=200, blank=True)
    google_location_id = models.CharField(max_length=200, blank=True)

    star_rating = models.SmallIntegerField(choices=StarRating.choices, db_index=True)
    reviewer_display_name = models.CharField(max_length=300, blank=True)
    reviewer_photo_url = models.URLField(max_length=500, blank=True)
    reviewer_is_anonymous = models.BooleanField(default=False)
    comment = models.TextField(blank=True)
    review_create_time = models.DateTimeField(db_index=True)
    review_update_time = models.DateTimeField()

    reply_comment = models.TextField(blank=True)
    reply_update_time = models.DateTimeField(null=True, blank=True)
    is_replied = models.BooleanField(default=False, db_index=True)

    enrichment_status = models.CharField(
        max_length=15,
        choices=EnrichmentStatus.choices,
        default=EnrichmentStatus.PENDING,
        db_index=True,
    )
    enrichment_version = models.PositiveSmallIntegerField(default=0)
    enrichment_attempted_at = models.DateTimeField(null=True, blank=True)
    sentiment = models.CharField(max_length=10, blank=True)
    tags = models.JSONField(default=list, blank=True)

    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)

    search_vector = SearchVectorField(null=True, blank=True)

    objects = ReviewQuerySet.as_manager()

    class Meta:
        db_table = "reviews_review"
        ordering: ClassVar[list[str]] = ["-review_create_time"]
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=["shop", "google_review_id"],
                name="review_unique_per_shop",
            ),
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(
                fields=["organisation", "shop", "is_replied", "star_rating"],
                name="review_org_shop_filter_idx",
            ),
            models.Index(
                fields=["organisation", "review_create_time"],
                name="review_org_date_idx",
            ),
            GinIndex(fields=["search_vector"], name="review_search_vec_idx"),
        ]

    def __str__(self) -> str:
        return f"Review({self.pk}, shop={self.shop_id}, stars={self.star_rating})"
