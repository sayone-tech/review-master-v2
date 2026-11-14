from django.contrib import admin
from unfold.admin import ModelAdmin

from apps.insights.models import InsightSnapshot


@admin.register(InsightSnapshot)
class InsightSnapshotAdmin(ModelAdmin):  # type: ignore[misc]
    list_display = ("organisation", "computed_for", "window_from", "window_to", "updated_at")
    list_filter = ("computed_for",)
    search_fields = ("organisation__name",)
    raw_id_fields = ("organisation",)
    list_select_related = ("organisation",)

    def has_add_permission(self, request) -> bool:  # type: ignore[no-untyped-def]
        return False

    def has_change_permission(self, request, obj=None) -> bool:  # type: ignore[no-untyped-def]
        return False

    def has_delete_permission(self, request, obj=None) -> bool:  # type: ignore[no-untyped-def]
        return False
