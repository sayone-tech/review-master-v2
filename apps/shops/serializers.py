from __future__ import annotations

from typing import Any, ClassVar

from rest_framework import serializers

from apps.shops.models import Shop


class ShopReadSerializer(serializers.ModelSerializer[Shop]):
    region_name = serializers.CharField(source="region.name", default="", read_only=True)
    region_region_id = serializers.CharField(source="region.region_id", default="", read_only=True)
    api_key_masked = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Shop
        fields: ClassVar[list[str]] = [
            "id",
            "name",
            "phone",
            "street_address",
            "city",
            "state",
            "zip_code",
            "place_id",
            "connection_method",
            "connection_status",
            "is_active",
            "region",
            "region_name",
            "region_region_id",
            "api_key_masked",
            "created_at",
            "updated_at",
        ]
        # Explicitly excludes google_refresh_token and api_key raw fields (SHOP-13).
        read_only_fields: ClassVar[list[str]] = [
            "id",
            "connection_status",
            "connection_method",
            "region_name",
            "region_region_id",
            "api_key_masked",
            "created_at",
            "updated_at",
        ]

    def get_api_key_masked(self, obj: Shop) -> str:
        """Return masked key for table display. NEVER returns the full key."""
        k = obj.api_key or ""
        return ("••••" + k[-4:]) if len(k) >= 4 else ""


class ShopCreateSerializer(serializers.Serializer):  # type: ignore[type-arg]
    name = serializers.CharField(min_length=2, max_length=100)
    phone = serializers.CharField(required=False, allow_blank=True, max_length=20, default="")
    street_address = serializers.CharField(required=False, allow_blank=True, default="")
    city = serializers.CharField(required=False, allow_blank=True, default="")
    state = serializers.CharField(required=False, allow_blank=True, default="")
    zip_code = serializers.CharField(required=False, allow_blank=True, default="")
    connection_method = serializers.ChoiceField(choices=Shop.ConnectionMethod.choices)
    place_id = serializers.CharField(required=False, allow_blank=True, default="", max_length=300)
    # write_only: the raw token never appears in responses (SHOP-13).
    # For GOOGLE_OAUTH, the view resolves this value from the session (it is
    # actually the OAuth state string, not the raw refresh token).
    google_refresh_token = serializers.CharField(
        required=False, allow_blank=True, default="", write_only=True
    )
    # write_only: raw API key never exposed in responses.
    api_key = serializers.CharField(required=False, allow_blank=True, default="", write_only=True)

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        req = self.context.get("request")
        org_id = getattr(getattr(req, "user", None), "organisation_id", None)
        from apps.regions.models import Region

        qs = Region.objects.filter(organisation_id=org_id) if org_id else Region.objects.none()
        self.fields["region"] = serializers.PrimaryKeyRelatedField(queryset=qs)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        method = attrs.get("connection_method", "")
        if method == Shop.ConnectionMethod.MANUAL:
            if not attrs.get("place_id"):
                raise serializers.ValidationError(
                    {"place_id": ["This field is required for manual connection."]}
                )
            if not attrs.get("api_key"):
                raise serializers.ValidationError(
                    {"api_key": ["This field is required for manual connection."]}
                )
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
        return attrs


class ShopUpdateSerializer(serializers.Serializer):  # type: ignore[type-arg]
    name = serializers.CharField(min_length=2, max_length=100, required=False)
    phone = serializers.CharField(required=False, allow_blank=True, max_length=20)
    street_address = serializers.CharField(required=False, allow_blank=True)
    city = serializers.CharField(required=False, allow_blank=True)
    state = serializers.CharField(required=False, allow_blank=True)
    zip_code = serializers.CharField(required=False, allow_blank=True)

    LOCKED_FIELDS: ClassVar[set[str]] = {
        "connection_method",
        "place_id",
        "google_refresh_token",
        "api_key",
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


class RotateKeySerializer(serializers.Serializer):  # type: ignore[type-arg]
    new_api_key = serializers.CharField(min_length=10, max_length=200, write_only=True)
