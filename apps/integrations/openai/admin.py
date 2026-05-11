"""Phase 12 — Django admin registration for AiPricing and AiUsageLog.

CONTEXT.md decision: AiPricing managed via Django admin only in Phase 12; no
custom Superadmin UI. AiUsageLog is read-only — historical records must NOT
be edited (ENRCH-09).
"""

from __future__ import annotations

from django.contrib import admin
from unfold.admin import ModelAdmin

from apps.integrations.openai.models import AiPricing, AiUsageLog


@admin.register(AiPricing)
class AiPricingAdmin(ModelAdmin):  # type: ignore[misc]
    list_display = (
        "model",
        "input_token_price_per_1m",
        "output_token_price_per_1m",
        "cached_token_price_per_1m",
        "effective_from",
        "effective_to",
    )
    list_filter = ("model",)
    search_fields = ("model",)


@admin.register(AiUsageLog)
class AiUsageLogAdmin(ModelAdmin):  # type: ignore[misc]
    list_display = (
        "created_at",
        "organisation",
        "request_type",
        "model",
        "status",
        "estimated_cost_usd",
        "latency_ms",
    )
    list_filter = ("status", "model", "request_type")
    search_fields = ("langsmith_trace_id", "error_code")
    readonly_fields = (
        "organisation",
        "review",
        "request_type",
        "model",
        "prompt_tokens",
        "completion_tokens",
        "cached_tokens",
        "total_tokens",
        "estimated_cost_usd",
        "latency_ms",
        "langsmith_trace_id",
        "status",
        "error_code",
        "error_message",
        "created_at",
    )

    def has_add_permission(self, request) -> bool:  # type: ignore[no-untyped-def]
        return False

    def has_delete_permission(self, request, obj=None) -> bool:  # type: ignore[no-untyped-def]
        return False
