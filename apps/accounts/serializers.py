from __future__ import annotations

from typing import ClassVar

from rest_framework import serializers

from apps.accounts.models import StaffAccessScope, User


class StaffAccessScopeSerializer(serializers.ModelSerializer[StaffAccessScope]):
    region_name = serializers.CharField(source="region.name", read_only=True, allow_null=True)
    region_region_id = serializers.CharField(
        source="region.region_id", read_only=True, allow_null=True
    )
    shop_name = serializers.CharField(source="shop.name", read_only=True, allow_null=True)

    class Meta:
        model = StaffAccessScope
        fields: ClassVar[list[str]] = [
            "id",
            "scope_type",
            "region",
            "region_name",
            "region_region_id",
            "shop",
            "shop_name",
        ]
        read_only_fields: ClassVar[list[str]] = [
            "id",
            "scope_type",
            "region",
            "region_name",
            "region_region_id",
            "shop",
            "shop_name",
        ]


class TeamMemberReadSerializer(serializers.ModelSerializer[User]):
    access_scopes = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields: ClassVar[list[str]] = [
            "id",
            "full_name",
            "email",
            "role",
            "is_active",
            "invited_at",
            "accepted_at",
            "status",
            "access_scopes",
        ]
        read_only_fields: ClassVar[list[str]] = [
            "id",
            "full_name",
            "email",
            "role",
            "is_active",
            "invited_at",
            "accepted_at",
            "status",
            "access_scopes",
        ]

    def get_access_scopes(self, instance: User) -> list[dict]:  # type: ignore[type-arg]
        """CRITICAL: read prefetched_scopes (to_attr) to avoid N+1.

        Fallback for instances loaded without prefetch.
        """
        scopes = getattr(instance, "prefetched_scopes", None)
        if scopes is None:
            scopes = list(instance.access_scopes.select_related("region", "shop").all())
        return StaffAccessScopeSerializer(scopes, many=True).data  # type: ignore[return-value]

    def get_status(self, instance: User) -> str:
        """PENDING: invited but not accepted. ACTIVE: accepted + is_active=True. DISABLED: accepted + is_active=False."""
        if instance.accepted_at is None:
            return "PENDING"
        return "ACTIVE" if instance.is_active else "DISABLED"


class TeamMemberCreateSerializer(serializers.Serializer):  # type: ignore[type-arg]
    full_name = serializers.CharField(min_length=2, max_length=100)
    email = serializers.EmailField()
    invited_for_role = serializers.ChoiceField(
        choices=[("ORG_ADMIN", "Manager"), ("STAFF_ADMIN", "Staff")],
    )
    region_ids = serializers.ListField(
        child=serializers.IntegerField(), required=False, default=list
    )
    shop_ids = serializers.ListField(child=serializers.IntegerField(), required=False, default=list)

    def validate_email(self, value: str) -> str:
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def validate(self, attrs: dict) -> dict:  # type: ignore[type-arg]
        role = attrs["invited_for_role"]
        if role == "STAFF_ADMIN" and not attrs.get("region_ids") and not attrs.get("shop_ids"):
            raise serializers.ValidationError("Please select at least one region or store.")
        return attrs


class TeamMemberUpdateSerializer(serializers.Serializer):  # type: ignore[type-arg]
    full_name = serializers.CharField(min_length=2, max_length=100)
    role = serializers.ChoiceField(choices=[("ORG_ADMIN", "Manager"), ("STAFF_ADMIN", "Staff")])
    region_ids = serializers.ListField(
        child=serializers.IntegerField(), required=False, default=list
    )
    shop_ids = serializers.ListField(child=serializers.IntegerField(), required=False, default=list)

    def validate(self, attrs: dict) -> dict:  # type: ignore[type-arg]
        # Email is intentionally absent — locked at edit time.
        if (
            attrs["role"] == "STAFF_ADMIN"
            and not attrs.get("region_ids")
            and not attrs.get("shop_ids")
        ):
            raise serializers.ValidationError("Please select at least one region or store.")
        return attrs
