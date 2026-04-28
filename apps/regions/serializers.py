from __future__ import annotations

import re
from typing import ClassVar

from rest_framework import serializers

from apps.regions.models import Region

REGION_ID_RE = re.compile(r"^[A-Z0-9]{2,10}$")

REGION_ID_ERROR = "Region ID must be uppercase letters and digits only (2-10 characters)."


class RegionReadSerializer(serializers.ModelSerializer[Region]):
    class Meta:
        model = Region
        fields: ClassVar[list[str]] = ["id", "name", "region_id", "created_at"]
        read_only_fields: ClassVar[list[str]] = ["id", "created_at"]


class RegionCreateSerializer(serializers.Serializer):  # type: ignore[type-arg]
    name = serializers.CharField(min_length=2, max_length=60)
    region_id = serializers.CharField(min_length=2, max_length=10)

    def validate_region_id(self, value: str) -> str:
        if not REGION_ID_RE.match(value):
            raise serializers.ValidationError(REGION_ID_ERROR)
        return value


class RegionUpdateSerializer(serializers.Serializer):  # type: ignore[type-arg]
    name = serializers.CharField(min_length=2, max_length=60, required=False)
    region_id = serializers.CharField(min_length=2, max_length=10, required=False)

    def validate_region_id(self, value: str) -> str:
        if not REGION_ID_RE.match(value):
            raise serializers.ValidationError(REGION_ID_ERROR)
        return value
