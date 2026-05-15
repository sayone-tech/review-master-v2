"""Phase 13 plan 04 — ActionItem serializers.

Five serializers covering the read/list/create/update + custom-action shapes.
ACTN-07 enforced by ActionItemUpdateSerializer omitting scope/shop fields entirely.
"""

from __future__ import annotations

from typing import Any, ClassVar

from django.utils import timezone
from rest_framework import serializers

from apps.accounts.models import User
from apps.action_items.models import ActionItem, ActionItemNote
from apps.shops.models import Shop


class ActionItemNoteSerializer(serializers.ModelSerializer):  # type: ignore[type-arg]
    author_id = serializers.IntegerField(read_only=True)
    author_name = serializers.SerializerMethodField()

    class Meta:
        model = ActionItemNote
        fields: ClassVar[list[str]] = ["id", "body", "author_id", "author_name", "created_at"]
        read_only_fields: ClassVar[list[str]] = fields

    def get_author_name(self, obj: ActionItemNote) -> str:
        author = obj.author
        if author is None:
            return "—"
        full_name = getattr(author, "full_name", "") or ""
        return str(full_name) if full_name else "—"


class _ActionItemBaseRead(serializers.ModelSerializer):  # type: ignore[type-arg]
    shop_name = serializers.SerializerMethodField()
    assignee_name = serializers.SerializerMethodField()
    category_value = serializers.CharField(source="category", read_only=True)
    category = serializers.CharField(source="get_category_display", read_only=True)

    class Meta:
        model = ActionItem
        fields: ClassVar[list[str]] = [
            "id",
            "title",
            "status",
            "scope",
            "priority",
            "source",
            "shop_id",
            "shop_name",
            "assignee_id",
            "assignee_name",
            "due_date",
            "created_at",
            "updated_at",
            "source_review_id",
            "category_value",
            "category",
        ]
        read_only_fields: ClassVar[list[str]] = fields

    def get_shop_name(self, obj: ActionItem) -> str:
        return str(obj.shop.name) if obj.shop else ""

    def get_assignee_name(self, obj: ActionItem) -> str:
        assignee = obj.assignee
        if assignee is None:
            return ""
        full_name = getattr(assignee, "full_name", "") or ""
        return str(full_name)


class ActionItemListSerializer(_ActionItemBaseRead):
    """List endpoint payload — excludes nested notes/source_review for tight query budget."""


class ActionItemReadSerializer(_ActionItemBaseRead):
    """Detail endpoint payload — includes nested notes (oldest-first) and source_review."""

    notes = ActionItemNoteSerializer(many=True, read_only=True)
    source_review = serializers.SerializerMethodField()

    class Meta(_ActionItemBaseRead.Meta):
        fields: ClassVar[list[str]] = [
            *_ActionItemBaseRead.Meta.fields,
            "notes",
            "source_review",
        ]
        read_only_fields: ClassVar[list[str]] = fields

    def get_source_review(self, obj: ActionItem) -> dict[str, Any] | None:
        if obj.source != ActionItem.Source.AI or obj.source_review is None:
            return None
        review = obj.source_review
        return {
            "id": review.pk,
            "comment": (review.comment or "")[:200],
            "rating": review.star_rating,
            "reviewer_name": review.reviewer_display_name,
        }


class ActionItemCreateSerializer(serializers.ModelSerializer):  # type: ignore[type-arg]
    title = serializers.CharField(min_length=5, max_length=200)
    scope = serializers.ChoiceField(choices=ActionItem.Scope.choices)
    priority = serializers.ChoiceField(
        choices=ActionItem.Priority.choices, default=ActionItem.Priority.MEDIUM
    )
    shop = serializers.PrimaryKeyRelatedField(
        queryset=Shop.objects.all(), required=False, allow_null=True
    )
    assignee = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), required=False, allow_null=True
    )
    due_date = serializers.DateField(required=False, allow_null=True)
    initial_note = serializers.CharField(required=False, allow_blank=True, max_length=2000)

    class Meta:
        model = ActionItem
        fields: ClassVar[list[str]] = [
            "title",
            "scope",
            "priority",
            "shop",
            "assignee",
            "due_date",
            "initial_note",
        ]

    def validate_due_date(self, value: Any) -> Any:
        if value is None:
            return value
        if value < timezone.now().date():
            raise serializers.ValidationError("due_date must be today or in the future")
        return value

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        scope = attrs.get("scope")
        if scope == ActionItem.Scope.SHOP and not attrs.get("shop"):
            raise serializers.ValidationError({"shop": "shop is required when scope=SHOP"})
        if scope == ActionItem.Scope.BRAND:
            attrs["shop"] = None
        return attrs


class ActionItemUpdateSerializer(serializers.ModelSerializer):  # type: ignore[type-arg]
    """ACTN-07: Title, Priority, Due Date, Assignee are editable. Scope/Shop are NOT.

    Omitting scope and shop from Meta.fields means PATCH/PUT silently ignores
    them in the payload (DRF validates incoming data only against declared
    fields).
    """

    title = serializers.CharField(min_length=5, max_length=200, required=False)
    priority = serializers.ChoiceField(choices=ActionItem.Priority.choices, required=False)
    due_date = serializers.DateField(required=False, allow_null=True)
    assignee = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), required=False, allow_null=True
    )

    class Meta:
        model = ActionItem
        fields: ClassVar[list[str]] = ["title", "priority", "due_date", "assignee"]

    def validate_due_date(self, value: Any) -> Any:
        if value is None:
            return value
        if value < timezone.now().date():
            raise serializers.ValidationError("due_date must be today or in the future")
        return value


class StatusTransitionSerializer(serializers.Serializer):  # type: ignore[type-arg]
    status = serializers.ChoiceField(choices=ActionItem.Status.choices)


class ActionItemNoteCreateSerializer(serializers.Serializer):  # type: ignore[type-arg]
    body = serializers.CharField(min_length=1, max_length=2000, trim_whitespace=False)
