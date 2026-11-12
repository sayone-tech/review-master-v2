"""Phase 12 — Django admin registration for AiPricing and AiUsageLog.

CONTEXT.md decision: AiPricing managed via Django admin only in Phase 12; no
custom Superadmin UI. AiUsageLog is read-only — historical records must NOT
be edited (ENRCH-09).
"""

from __future__ import annotations

from django.contrib import admin
from unfold.admin import ModelAdmin

from apps.integrations.openai.models import AiPricing, AiUsageLog, PlatformAuditLog


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
    list_filter = ("model", "source")
    search_fields = ("model",)
    readonly_fields = (
        "model",
        "input_token_price_per_1m",
        "output_token_price_per_1m",
        "cached_token_price_per_1m",
        "effective_from",
        "effective_to",
        "source",
        "created_by",
    )

    def has_add_permission(self, request) -> bool:  # type: ignore[no-untyped-def]
        return False

    def has_change_permission(self, request, obj=None) -> bool:  # type: ignore[no-untyped-def]
        return False

    def has_delete_permission(self, request, obj=None) -> bool:  # type: ignore[no-untyped-def]
        return False


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


@admin.register(PlatformAuditLog)
class PlatformAuditLogAdmin(ModelAdmin):  # type: ignore[misc]
    list_display = ("created_at", "action", "actor", "entity_id")
    readonly_fields = (
        "organisation",
        "actor",
        "entity_type",
        "entity_id",
        "action",
        "before_data",
        "after_data",
        "created_at",
        "updated_at",
    )

    def get_queryset(self, request):  # type: ignore[no-untyped-def]
        return (
            super()
            .get_queryset(request)
            .filter(organisation__isnull=True, entity_type="ai_pricing")
            .select_related("actor")
        )

    def has_add_permission(self, request) -> bool:  # type: ignore[no-untyped-def]
        return False

    def has_change_permission(self, request, obj=None) -> bool:  # type: ignore[no-untyped-def]
        return False

    def has_delete_permission(self, request, obj=None) -> bool:  # type: ignore[no-untyped-def]
        return False
