from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from apps.accounts.models import InvitationToken, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):  # type: ignore[type-arg]
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
    ordering = ("email",)
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal info", {"fields": ("full_name",)}),
        ("Role & organisation", {"fields": ("role", "organisation")}),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("Important dates", {"fields": ("last_login", "accepted_at")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "full_name", "role", "organisation", "password1", "password2"),
            },
        ),
    )


@admin.register(InvitationToken)
class InvitationTokenAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("organisation", "invited_user", "is_used", "expires_at", "created_at")
    list_filter = ("is_used",)
    search_fields = ("organisation__name", "invited_user__email")
