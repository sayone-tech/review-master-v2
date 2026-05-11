from django.contrib import admin
from unfold.admin import ModelAdmin

from apps.organisations.models import Organisation


@admin.register(Organisation)
class OrganisationAdmin(ModelAdmin):  # type: ignore[misc]
    list_display = ("name", "org_type", "email", "status", "number_of_stores", "created_at")
    list_filter = ("status", "org_type")
    search_fields = ("name", "email")
    readonly_fields = ("created_at", "updated_at")
