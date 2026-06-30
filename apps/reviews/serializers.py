"""Phase 11 — Review serializers.

Phase 25 Plan 02 — OrgCanonicalTagReadSerializer, RenameSerializer, TagMergeJobSerializer.
"""

from __future__ import annotations

from typing import ClassVar

from rest_framework import serializers

from apps.integrations.openai.prompts import ALLOWED_REPLY_TONES
from apps.reviews.models import OrgCanonicalTag, Review, ReviewTag, TagMergeJob


class ReviewTagSerializer(serializers.Serializer):  # type: ignore[type-arg]
    """Phase 17 (TAG-02): nested read serializer for ReviewTag rows.

    Plain Serializer (not ModelSerializer) following the ReviewReplySerializer
    pattern. Returns {label, polarity} to preserve the JSON shape the
    frontend already consumes from the old Review.tags JSONField.
    """

    label = serializers.CharField(read_only=True)  # type: ignore[assignment]
    # Phase 17 WR-05: surface the model's Polarity choices to consumers so
    # drf-spectacular emits the enum in the OpenAPI schema. The frontend
    # TagPolarity type is a strict literal union; CharField hid the
    # constraint and let contract drift surface only at runtime.
    polarity = serializers.ChoiceField(choices=ReviewTag.Polarity.choices, read_only=True)


class ReviewReadSerializer(serializers.ModelSerializer):  # type: ignore[type-arg]
    shop_name = serializers.CharField(source="shop.name", read_only=True)
    shop_region_name = serializers.SerializerMethodField()
    region_id = serializers.IntegerField(source="shop.region_id", read_only=True)
    replied_by_name = serializers.SerializerMethodField()
    # Phase 13 Plan 07 (B3): True iff one or more ActionItem rows exist for this
    # review. Backed by an Exists() annotation on the queryset (see
    # ReviewViewSet.get_queryset). Annotation collapses into the existing list
    # JOINs so the REVW-14 <=5-query budget is preserved.
    has_action_items = serializers.BooleanField(read_only=True)
    # Phase 17 (TAG-02): tags now come from ReviewTag rows via the
    # related_name="tags" RelatedManager (prefetch_related("tags") in the
    # selector keeps this O(1) extra query, not N+1).
    tags = ReviewTagSerializer(many=True, read_only=True)

    class Meta:
        model = Review
        fields: ClassVar[list[str]] = [
            "id",
            "shop_id",
            "shop_name",
            "shop_region_name",
            "region_id",
            "google_review_id",
            "star_rating",
            "reviewer_display_name",
            "reviewer_photo_url",
            "reviewer_is_anonymous",
            "comment",
            "review_create_time",
            "review_update_time",
            "reply_comment",
            "reply_update_time",
            "is_replied",
            "replied_by_name",
            "enrichment_status",
            "sentiment",
            "tags",
            "extracted_action_items",
            "has_action_items",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_shop_region_name(self, obj: Review) -> str:
        if obj.shop and obj.shop.region:
            return str(obj.shop.region.name)
        return ""

    def get_replied_by_name(self, obj: Review) -> str | None:
        if obj.replied_by_id is None:
            return None
        user = obj.replied_by
        if user is None:
            return None
        return str(user.full_name).strip() or str(user.email)


class ReviewReplySerializer(serializers.Serializer):  # type: ignore[type-arg]
    """Input serializer for POST /reviews/{id}/reply/ (Plan 07)."""

    comment = serializers.CharField(min_length=1, max_length=4000, trim_whitespace=False)


class GenerateReplySerializer(serializers.Serializer):  # type: ignore[type-arg]
    """Phase 19 Plan 02: input serializer for POST /reviews/{id}/generate-reply/.

    D-10/D-11: tone is a required ChoiceField restricted to two values.
    """

    # WR-03: single source of truth lives in apps.integrations.openai.prompts.
    TONE_CHOICES: ClassVar[tuple[str, ...]] = ALLOWED_REPLY_TONES
    tone = serializers.ChoiceField(choices=ALLOWED_REPLY_TONES)


# ---------------------------------------------------------------------------
# Phase 25 Plan 02 — Canonical Tag Management serializers (§8 two-serializer rule)
# ---------------------------------------------------------------------------


class OrgCanonicalTagReadSerializer(serializers.ModelSerializer):  # type: ignore[type-arg]
    """Read serializer for OrgCanonicalTag (TMGT-02 list + rename response).

    Exposes ``created_at`` as ``first_seen`` (UI-SPEC Surface 1 column name).
    All fields are read-only — mutations go through service functions.
    """

    first_seen = serializers.DateTimeField(source="created_at", read_only=True)

    class Meta:
        model = OrgCanonicalTag
        fields: ClassVar[list[str]] = [
            "id",
            "label",
            "polarity_type",
            "review_count",
            "first_seen",
        ]
        read_only_fields = fields


class RenameSerializer(serializers.Serializer):  # type: ignore[type-arg]
    """Input serializer for the rename action (TMGT-03).

    Validates label length 1-100; service applies Title-Case and iexact dedup.
    """

    label = serializers.CharField(min_length=1, max_length=100)  # type: ignore[assignment]


class TagMergeJobSerializer(serializers.ModelSerializer):  # type: ignore[type-arg]
    """Read serializer for TagMergeJob poll/dismiss endpoints (TMGT-06).

    All fields are read-only; status transitions happen inside the service.
    """

    class Meta:
        model = TagMergeJob
        fields: ClassVar[list[str]] = [
            "id",
            "status",
            "processed",
            "total",
            "source_label",
            "target_label",
            "error_message",
            "dismissed",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields
