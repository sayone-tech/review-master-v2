from django.contrib import admin
from unfold.admin import ModelAdmin

from apps.shops.models import Shop, ShopAuditLog


@admin.register(Shop)
class ShopAdmin(ModelAdmin):  # type: ignore[misc]
    list_display = (
        "name",
        "organisation",
        "region",
        "connection_status",
        "connection_method",
        "is_active",
        "created_at",
    )
    list_filter = ("connection_status", "connection_method", "is_active")
    search_fields = ("name", "organisation__name", "place_id")
    raw_id_fields = ("organisation", "region")
    readonly_fields = ("created_at", "updated_at")


@admin.register(ShopAuditLog)
class ShopAuditLogAdmin(ModelAdmin):  # type: ignore[misc]
    list_display = ("shop", "actor", "action", "created_at")
    list_filter = ("action",)
    search_fields = ("shop__name",)
    raw_id_fields = ("shop", "actor")
    readonly_fields = ("shop", "actor", "action", "created_at")

    def has_add_permission(self, request) -> bool:  # type: ignore[no-untyped-def]
        return False

    def has_delete_permission(self, request, obj=None) -> bool:  # type: ignore[no-untyped-def]
        return False
