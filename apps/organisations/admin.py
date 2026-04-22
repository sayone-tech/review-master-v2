from django.contrib import admin

from apps.organisations.models import Organisation


@admin.register(Organisation)
class OrganisationAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("name", "org_type", "email", "status", "number_of_stores", "created_at")
    list_filter = ("status", "org_type")
    search_fields = ("name", "email")
    readonly_fields = ("created_at", "updated_at")
