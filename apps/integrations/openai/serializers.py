"""Response serializers for the Superadmin AI Cost Explorer (Phase 34).

Shape-only: decimals render as strings with exactly six decimal places.
"""

from __future__ import annotations

from typing import Any

from rest_framework import serializers


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
