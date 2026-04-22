from django.contrib import admin

from apps.accounts.models import InvitationToken, User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = (
        "email",
        "full_name",
        "role",
        "organisation",
        "is_active",
        "is_staff",
        "created_at",
    )
    list_filter = ("role", "is_active", "is_staff")
    search_fields = ("email", "full_name")
    raw_id_fields = ("organisation",)


@admin.register(InvitationToken)
class InvitationTokenAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("organisation", "invited_user", "is_used", "expires_at", "created_at")
    list_filter = ("is_used",)
    search_fields = ("organisation__name", "invited_user__email")
