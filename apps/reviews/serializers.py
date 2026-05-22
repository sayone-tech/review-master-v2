"""Phase 11 — Review serializers."""

from __future__ import annotations

from typing import ClassVar

from rest_framework import serializers

from apps.reviews.models import Review, ReviewTag


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
