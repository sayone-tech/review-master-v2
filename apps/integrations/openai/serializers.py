"""Response serializers for the Superadmin AI Cost Explorer (Phase 34).

Shape-only: decimals render as strings with exactly six decimal places.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from django.utils import timezone
from rest_framework import serializers

from apps.integrations.openai.models import AiPricing


def cost_field() -> serializers.DecimalField:
    return serializers.DecimalField(max_digits=20, decimal_places=6)


class CostWindowSerializer(serializers.Serializer[Any]):
    key = serializers.CharField()
    start = serializers.DateTimeField()
    end = serializers.DateTimeField()


class CostTotalsSerializer(serializers.Serializer[Any]):
    calls = serializers.IntegerField()
    success_calls = serializers.IntegerField()
    failed_calls = serializers.IntegerField()
    moderated_calls = serializers.IntegerField()
    input_tokens = serializers.IntegerField()
    output_tokens = serializers.IntegerField()
    cost = cost_field()


class CostSummaryTotalsSerializer(CostTotalsSerializer):
    org_count = serializers.IntegerField()
    active_shops = serializers.IntegerField()


class CostSummaryResponseSerializer(serializers.Serializer[Any]):
    range = CostWindowSerializer()
    generated_at = serializers.DateTimeField()
    has_any_usage = serializers.BooleanField()
    totals = CostSummaryTotalsSerializer()


class OrgCostRowSerializer(serializers.Serializer[Any]):
    organisation_id = serializers.IntegerField()
    name = serializers.CharField()
    org_type = serializers.CharField()
    active_shops = serializers.IntegerField()
    calls = serializers.IntegerField()
    input_tokens = serializers.IntegerField()
    output_tokens = serializers.IntegerField()
    cost = cost_field()
    by_request_type = serializers.DictField(child=cost_field())


class OrgCostListResponseSerializer(serializers.Serializer[Any]):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    generated_at = serializers.DateTimeField()
    results = OrgCostRowSerializer(many=True)


class OrgHeaderSerializer(serializers.Serializer[Any]):
    id = serializers.IntegerField()
    name = serializers.CharField()
    org_type = serializers.CharField()
    shop_count = serializers.IntegerField()


class OrgSummaryResponseSerializer(serializers.Serializer[Any]):
    organisation = OrgHeaderSerializer()
    range = CostWindowSerializer()
    generated_at = serializers.DateTimeField()
    totals = CostSummaryTotalsSerializer()


class ShopCostRowSerializer(serializers.Serializer[Any]):
    shop_id = serializers.IntegerField()
    name = serializers.CharField()
    region_name = serializers.CharField(allow_null=True)
    calls = serializers.IntegerField()
    input_tokens = serializers.IntegerField()
    output_tokens = serializers.IntegerField()
    cost = cost_field()
    by_request_type = serializers.DictField(child=cost_field())


class UnattributedCostSerializer(serializers.Serializer[Any]):
    calls = serializers.IntegerField()
    input_tokens = serializers.IntegerField()
    output_tokens = serializers.IntegerField()
    cost = cost_field()
    by_request_type = serializers.DictField(child=cost_field())


class ShopCostListResponseSerializer(serializers.Serializer[Any]):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    generated_at = serializers.DateTimeField()
    unattributed = UnattributedCostSerializer(allow_null=True)
    results = ShopCostRowSerializer(many=True)


class ModelCostRowSerializer(serializers.Serializer[Any]):
    model = serializers.CharField()
    calls = serializers.IntegerField()
    input_tokens = serializers.IntegerField()
    output_tokens = serializers.IntegerField()
    cost = cost_field()


class ModelCostListResponseSerializer(serializers.Serializer[Any]):
    results = ModelCostRowSerializer(many=True)
    generated_at = serializers.DateTimeField()


def price_field() -> serializers.DecimalField:
    return serializers.DecimalField(max_digits=12, decimal_places=8)


def write_price_field() -> serializers.DecimalField:
    return serializers.DecimalField(
        max_digits=12, decimal_places=8, min_value=Decimal(0), max_value=Decimal(1000)
    )


class PriceRowSerializer(serializers.ModelSerializer[AiPricing]):
    """One ``AiPricing`` row. Pass ``context={"now": ...}`` to pin the status clock."""

    input_token_price_per_1m = price_field()
    output_token_price_per_1m = price_field()
    cached_token_price_per_1m = price_field()
    created_by = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    can_delete = serializers.SerializerMethodField()

    class Meta:
        model = AiPricing
        fields = (
            "id",
            "model",
            "input_token_price_per_1m",
            "output_token_price_per_1m",
            "cached_token_price_per_1m",
            "effective_from",
            "effective_to",
            "source",
            "created_by",
            "status",
            "can_delete",
        )
        read_only_fields = fields

    def _now(self) -> datetime:
        now: datetime = self.context.get("now") or timezone.now()
        return now

    def get_created_by(self, obj: AiPricing) -> dict[str, Any] | None:
        user = obj.created_by
        if user is None:
            return None
        return {"id": user.pk, "name": user.full_name or user.email}

    def get_status(self, obj: AiPricing) -> str:
        now = self._now()
        if obj.effective_from > now:
            return "scheduled"
        if obj.effective_to is None or obj.effective_to > now:
            return "current"
        return "past"

    def get_can_delete(self, obj: AiPricing) -> bool:
        return self.get_status(obj) == "scheduled"


class AiPriceCreateSerializer(serializers.Serializer[Any]):
    """Input for adding/scheduling a price; validation only (the service does the work)."""

    model = serializers.CharField(min_length=1, max_length=100)
    input_token_price_per_1m = write_price_field()
    output_token_price_per_1m = write_price_field()
    cached_token_price_per_1m = write_price_field()
    effective_from = serializers.DateTimeField()


class PriceSummaryRowSerializer(serializers.Serializer[Any]):
    model = serializers.CharField()
    current = PriceRowSerializer(allow_null=True)
    scheduled = PriceRowSerializer(allow_null=True)


class PriceSummaryListResponseSerializer(serializers.Serializer[Any]):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = PriceSummaryRowSerializer(many=True)


class PriceHistoryListResponseSerializer(serializers.Serializer[Any]):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = PriceRowSerializer(many=True)


class ModelSuggestionSerializer(serializers.Serializer[Any]):
    model = serializers.CharField()
    last_used_at = serializers.DateTimeField(allow_null=True)
    has_price = serializers.BooleanField()


class ModelSuggestionsResponseSerializer(serializers.Serializer[Any]):
    results = ModelSuggestionSerializer(many=True)


class MissingModelSerializer(serializers.Serializer[Any]):
    model = serializers.CharField()
    last_used_at = serializers.DateTimeField(allow_null=True)
    configured = serializers.BooleanField()


class MissingModelsResponseSerializer(serializers.Serializer[Any]):
    models = MissingModelSerializer(many=True)
    generated_at = serializers.DateTimeField()
