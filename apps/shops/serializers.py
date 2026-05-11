from __future__ import annotations

from typing import Any, ClassVar

from rest_framework import serializers

from apps.shops.models import ReviewTarget, Shop


class ShopReadSerializer(serializers.ModelSerializer[Shop]):
    region_name = serializers.CharField(source="region.name", default="", read_only=True)
    region_region_id = serializers.CharField(source="region.region_id", default="", read_only=True)

    class Meta:
        model = Shop
        fields: ClassVar[list[str]] = [
            "id",
            "name",
            "phone",
            "street_address",
            "place_id",
            "connection_method",
            "connection_status",
            "is_active",
            "region",
            "region_name",
            "region_region_id",
            "created_at",
            "updated_at",
        ]
        # Explicitly excludes google_refresh_token (SHOP-13).
        read_only_fields: ClassVar[list[str]] = [
            "id",
            "connection_status",
            "connection_method",
            "region_name",
            "region_region_id",
            "created_at",
            "updated_at",
        ]


class ShopCreateSerializer(serializers.Serializer):  # type: ignore[type-arg]
    name = serializers.CharField(min_length=2, max_length=100)
    phone = serializers.CharField(required=False, allow_blank=True, max_length=20, default="")
    street_address = serializers.CharField(required=False, allow_blank=True, default="")
    connection_method = serializers.ChoiceField(choices=Shop.ConnectionMethod.choices)
    place_id = serializers.CharField(required=False, allow_blank=True, default="", max_length=300)
    # write_only: the raw token never appears in responses (SHOP-13).
    # For GOOGLE_OAUTH, the view resolves this value from the session (it is
    # actually the OAuth state string, not the raw refresh token).
    google_refresh_token = serializers.CharField(
        required=False, allow_blank=True, default="", write_only=True
    )
    # Phase 11-08: GBP resource names populated from OAuth listing payload.
    # Optional — frontend may not yet pass these; falls back to empty string.
    google_account_name = serializers.CharField(
        max_length=200, required=False, allow_blank=True, default=""
    )
    google_location_name = serializers.CharField(
        max_length=200, required=False, allow_blank=True, default=""
    )

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        req = self.context.get("request")
        org_id = getattr(getattr(req, "user", None), "organisation_id", None)
        from apps.regions.models import Region

        qs = Region.objects.filter(organisation_id=org_id) if org_id else Region.objects.none()
        self.fields["region"] = serializers.PrimaryKeyRelatedField(queryset=qs)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        method = attrs.get("connection_method", "")
        if method == Shop.ConnectionMethod.GOOGLE_OAUTH:
            if not attrs.get("google_refresh_token"):
                raise serializers.ValidationError(
                    {
                        "google_refresh_token": [
                            "This field is required for Google OAuth connection."
                        ]
                    }
                )
            if not attrs.get("place_id"):
                raise serializers.ValidationError(
                    {"place_id": ["This field is required for Google OAuth connection."]}
                )
            # Duplicate place check — friendly error before hitting the DB constraint.
            place_id = attrs["place_id"]
            req = self.context.get("request")
            org_id = getattr(getattr(req, "user", None), "organisation_id", None)
            if org_id and Shop.objects.filter(organisation_id=org_id, place_id=place_id).exists():
                raise serializers.ValidationError(
                    {"place_id": ["This location has already been added to your organisation."]}
                )
        return attrs


class ShopUpdateSerializer(serializers.Serializer):  # type: ignore[type-arg]
    name = serializers.CharField(min_length=2, max_length=100, required=False)
    phone = serializers.CharField(required=False, allow_blank=True, max_length=20)
    street_address = serializers.CharField(required=False, allow_blank=True)

    # api_key column no longer exists; if a legacy client posts it, it would be silently
    # ignored by DRF (no field declared). It is intentionally excluded from LOCKED_FIELDS.
    LOCKED_FIELDS: ClassVar[set[str]] = {
        "connection_method",
        "place_id",
        "google_refresh_token",
    }

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        req = self.context.get("request")
        org_id = getattr(getattr(req, "user", None), "organisation_id", None)
        from apps.regions.models import Region

        qs = Region.objects.filter(organisation_id=org_id) if org_id else Region.objects.none()
        self.fields["region"] = serializers.PrimaryKeyRelatedField(
            queryset=qs, required=False, allow_null=True
        )

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        initial: dict[str, Any] = getattr(self, "initial_data", {}) or {}
        locked_present = self.LOCKED_FIELDS & set(initial.keys())
        if locked_present:
            raise serializers.ValidationError(
                {
                    field: ["This field cannot be modified after creation."]
                    for field in locked_present
                }
            )
        return attrs


class ReviewTargetReadSerializer(serializers.Serializer):  # type: ignore[type-arg]
    id = serializers.IntegerField()
    period_type = serializers.CharField()
    target_count = serializers.IntegerField()
    received_count = serializers.IntegerField()
    pct = serializers.IntegerField()
    period_label = serializers.CharField()
    days_remaining = serializers.IntegerField()


class ReviewTargetWriteSerializer(serializers.Serializer):  # type: ignore[type-arg]
    period_type = serializers.ChoiceField(choices=ReviewTarget.PeriodType.choices)
    target_count = serializers.IntegerField(min_value=1)
