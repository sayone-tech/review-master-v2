"""Superadmin credit serializers (CSUP-01): validate and shape only, no business logic."""

from __future__ import annotations

from typing import Any

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.credits.services.periods import Period, period_label


class BonusAllocationSerializer(serializers.Serializer[Any]):
    amount = serializers.IntegerField(min_value=1, max_value=10000)
    reason = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    period_year = serializers.IntegerField(min_value=2000, max_value=9999)
    period_month = serializers.IntegerField(min_value=1, max_value=12)


class CreditPeriodSerializer(serializers.Serializer[Any]):
    year = serializers.IntegerField()
    month = serializers.IntegerField()


class BonusResultSerializer(serializers.Serializer[Any]):
    shop_id = serializers.IntegerField()
    period = serializers.SerializerMethodField()
    allocated = serializers.IntegerField()
    bonus = serializers.IntegerField()
    consumed = serializers.IntegerField()
    remaining = serializers.IntegerField()
    transaction_id = serializers.IntegerField()

    @extend_schema_field(CreditPeriodSerializer)
    def get_period(self, obj: Any) -> dict[str, int]:
        return {"year": obj.period_year, "month": obj.period_month}


class CreditBalanceSnapshotSerializer(serializers.Serializer[Any]):
    shop_id = serializers.IntegerField()
    allocated = serializers.IntegerField()
    bonus = serializers.IntegerField()
    consumed = serializers.IntegerField()
    remaining = serializers.IntegerField()


class CreditShopRowSerializer(serializers.Serializer[Any]):
    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(read_only=True)
    allocated = serializers.IntegerField(source="credit_allocated", read_only=True)
    bonus = serializers.IntegerField(source="credit_bonus", read_only=True)
    consumed = serializers.IntegerField(source="credit_consumed", read_only=True)
    remaining = serializers.IntegerField(source="credit_remaining", read_only=True)
    is_materialized = serializers.BooleanField(source="credit_materialized", read_only=True)


class ShopCreditsSerializer(serializers.Serializer[Any]):
    """Shape of ``CreditBalanceView`` for the tenant shop-credits read (CVIS-01)."""

    shop_id = serializers.IntegerField()
    period = serializers.SerializerMethodField()
    period_label = serializers.SerializerMethodField()
    renews_on = serializers.DateField()
    allocated = serializers.IntegerField()
    bonus = serializers.IntegerField()
    consumed = serializers.IntegerField()
    remaining = serializers.IntegerField()
    total = serializers.SerializerMethodField()
    is_enabled = serializers.BooleanField()

    @extend_schema_field(CreditPeriodSerializer)
    def get_period(self, obj: Any) -> dict[str, int]:
        return {"year": obj.year, "month": obj.month}

    def get_period_label(self, obj: Any) -> str:
        return period_label(Period(obj.year, obj.month))

    def get_total(self, obj: Any) -> int:
        return int(obj.allocated + obj.bonus)


# Schema-only serializers (never instantiated for output) ----------------------------------


class CreditErrorSerializer(serializers.Serializer[Any]):
    code = serializers.CharField()
    detail = serializers.CharField()


class PeriodMismatchResponseSerializer(serializers.Serializer[Any]):
    code = serializers.CharField()
    detail = serializers.CharField()
    period = CreditPeriodSerializer()
    balance = CreditBalanceSnapshotSerializer()


class CreditShopListResponseSerializer(serializers.Serializer[Any]):
    count = serializers.IntegerField()
    next = serializers.CharField(allow_null=True)
    previous = serializers.CharField(allow_null=True)
    period = CreditPeriodSerializer()
    allocation_per_shop = serializers.IntegerField()
    results = CreditShopRowSerializer(many=True)
