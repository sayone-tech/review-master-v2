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
    replied_by = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="replies",
        db_index=True,
    )

    enrichment_status = models.CharField(
        max_length=15,
        choices=EnrichmentStatus.choices,
        default=EnrichmentStatus.PENDING,
        db_index=True,
    )
    enrichment_version = models.PositiveSmallIntegerField(default=0)
    enrichment_attempted_at = models.DateTimeField(null=True, blank=True)
    # Denormalized last-failure code; consumed by retry_failed_enrichments_task
    # to skip 'content_moderated' rows (D-25, D-31). Populated by enrichment
    # service helpers. No db_index — the retry task already filters on the
    # indexed enrichment_status=FAILED, so the residual scan is small.
    enrichment_error_code = models.CharField(max_length=32, blank=True, default="")
    sentiment = models.CharField(max_length=10, blank=True)
    extracted_action_items = models.JSONField(default=list, blank=True)

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
            models.Index(
                fields=["organisation", "review_create_time", "sentiment"],
                name="review_org_time_sent_idx",
            ),
            models.Index(
                fields=["shop", "review_create_time"],
                name="review_shop_time_idx",
            ),
            models.Index(
                fields=["organisation", "review_create_time", "enrichment_status"],
                name="review_org_time_status_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"Review({self.pk}, shop={self.shop_id}, stars={self.star_rating})"


class OrgCanonicalTag(TimeStampedModel):
    """Per-organisation canonical tag vocabulary entry.

    One row per unique (organisation, label) pair. The `review_count` column is
    a DENORMALIZED CACHE only — populated at 0, NEVER incremented in the
    enrichment hot path (D-03 derive-on-read; refreshed only by the Phase 24
    weekly job / Phase 25 merge).
    """

    class PolarityType(models.TextChoices):
        ALWAYS_POSITIVE = "always_positive", "Always Positive"
        ALWAYS_NEGATIVE = "always_negative", "Always Negative"
        MIXED = "mixed", "Mixed"

    organisation = models.ForeignKey(
        "organisations.Organisation",
        on_delete=models.CASCADE,
        related_name="canonical_tags",
        db_index=True,
    )
    label = models.CharField(max_length=100)
    polarity_type = models.CharField(max_length=20, choices=PolarityType.choices)
    # Denormalised cache stamped by the Phase 24 weekly reclassification job.
    # Null means never auto-reclassified. AuditLog remains authoritative.
    # Provides Phase 25 tag-list display a cheap last-reclassified value
    # without requiring an AuditLog JOIN.
    polarity_reclassified_at = models.DateTimeField(null=True, blank=True)
    # DENORMALIZED CACHE — default 0. NEVER incremented in the enrichment hot
    # path (D-03). Refreshed only by the Phase 24 weekly reclassification job
    # and Phase 25 merge operations.
    review_count = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "reviews_orgcanonicaltag"
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=["organisation", "label"],
                name="uniq_orgcanonicaltag_org_label",
            ),
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(
                fields=["organisation", "-review_count"],
                name="orgcanon_org_count_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.label} (org={self.organisation_id})"


class TagMergeJob(TimeStampedModel):
    """Durable record of a user-initiated canonical tag merge (D-08).

    source_tag FK becomes null after the merge (on_delete=SET_NULL — source is deleted).
    source_label / target_label are denormalized for display after deletion.
    Poll endpoint filters by (organisation, dismissed, status) using tagmergejob_org_status_idx.
    """

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        IN_PROGRESS = "IN_PROGRESS", "In Progress"
        SUCCESS = "SUCCESS", "Success"
        FAILED = "FAILED", "Failed"

    organisation = models.ForeignKey(
        "organisations.Organisation",
        on_delete=models.CASCADE,
        db_index=True,
        related_name="tag_merge_jobs",
    )
    source_tag = models.ForeignKey(
        "reviews.OrgCanonicalTag",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    source_label = models.CharField(max_length=100)  # denormalized — source deleted on success
    target_tag = models.ForeignKey(
        "reviews.OrgCanonicalTag",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    target_label = models.CharField(max_length=100)  # denormalized for display
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    processed = models.PositiveIntegerField(default=0)
    total = models.PositiveIntegerField(default=0)
    error_message = models.TextField(blank=True, default="")
    dismissed = models.BooleanField(default=False, db_index=True)

    class Meta:
        indexes: ClassVar[list[models.Index]] = [
            models.Index(
                fields=["organisation", "status"],
                name="tagmergejob_org_status_idx",
            ),
            models.Index(
                fields=["organisation", "-created_at"],
                name="tagmergejob_org_date_idx",
            ),
        ]

    def __str__(self) -> str:
        return (
            f"TagMergeJob({self.pk}, org={self.organisation_id}, "
            f"{self.source_label!r}→{self.target_label!r}, status={self.status})"
        )


class ReviewTag(models.Model):
    class Polarity(models.TextChoices):
        POSITIVE = "positive", "Positive"
        NEUTRAL = "neutral", "Neutral"
        NEGATIVE = "negative", "Negative"

    review = models.ForeignKey(
        "reviews.Review",
        on_delete=models.CASCADE,
        related_name="tags",
    )
    label = models.CharField(max_length=100, db_index=True)
    polarity = models.CharField(max_length=10, choices=Polarity.choices)
    canonical_tag = models.ForeignKey(
        "reviews.OrgCanonicalTag",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="review_tags",
        db_index=True,
    )

    class Meta:
        db_table = "reviews_reviewtag"
        constraints: ClassVar[list[models.BaseConstraint]] = [
            # Phase 17 CR-02: DB-level guard against the cross-transaction race
            # in enrich_review's delete-then-bulk_create write path. Without
            # this constraint a Redis-lock miss (e.g. Redis outage with
            # IGNORE_EXCEPTIONS) could let two concurrent enrichments produce
            # duplicate (review, label, polarity) rows; with it the second
            # bulk_create fails at the DB layer and the second transaction
            # rolls back cleanly.
            # NOTE: canonical_tag is intentionally excluded from this constraint
            # to preserve the delete-then-bulk_create race guard (Phase 22).
            models.UniqueConstraint(
                fields=["review", "label", "polarity"],
                name="uniq_reviewtag_review_label_polarity",
            ),
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=["review", "label"], name="reviewtag_review_label_idx"),
        ]

    def __str__(self) -> str:
        return f"ReviewTag({self.review_id}, {self.label}, {self.polarity})"
