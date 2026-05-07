"""Phase 11 — Review serializers."""

from __future__ import annotations

from typing import ClassVar

from rest_framework import serializers

from apps.reviews.models import Review


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
