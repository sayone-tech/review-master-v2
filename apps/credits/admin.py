"""Read-only Django admin for credit balances and the ledger (D-05).

View pages stay available; add/change/delete are denied even for superusers.
"""

from django.contrib import admin
from unfold.admin import ModelAdmin

from apps.credits.models import CreditTransaction, ShopCreditBalance


@admin.register(ShopCreditBalance)
class ShopCreditBalanceAdmin(ModelAdmin):  # type: ignore[misc]
    list_display = (
        "shop",
        "organisation",
        "period_year",
        "period_month",
        "allocated_credits",
        "bonus_credits",
        "consumed_credits",
        "updated_at",
    )
    list_filter = ("period_year", "period_month")
    search_fields = ("shop__name", "organisation__name")
    raw_id_fields = ("shop", "organisation")
    list_select_related = ("shop", "organisation")

    def has_add_permission(self, request) -> bool:  # type: ignore[no-untyped-def]
        return False

    def has_change_permission(self, request, obj=None) -> bool:  # type: ignore[no-untyped-def]
        return False

    def has_delete_permission(self, request, obj=None) -> bool:  # type: ignore[no-untyped-def]
        return False


@admin.register(CreditTransaction)
class CreditTransactionAdmin(ModelAdmin):  # type: ignore[misc]
    list_display = (
        "created_at",
        "transaction_type",
        "status",
        "credits_delta",
        "shop",
        "organisation",
        "actor",
    )
    list_filter = ("transaction_type", "status")
    search_fields = ("shop__name",)
    raw_id_fields = (
        "shop_credit_balance",
        "shop",
        "organisation",
        "review",
        "ai_usage_log",
        "actor",
    )
    list_select_related = ("shop", "organisation", "actor")

    def has_add_permission(self, request) -> bool:  # type: ignore[no-untyped-def]
        return False

    def has_change_permission(self, request, obj=None) -> bool:  # type: ignore[no-untyped-def]
        return False

    def has_delete_permission(self, request, obj=None) -> bool:  # type: ignore[no-untyped-def]
        return False
