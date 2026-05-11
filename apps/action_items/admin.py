"""Phase 13 — ActionItem admin registrations."""

from __future__ import annotations

from django.contrib import admin
from unfold.admin import ModelAdmin

from apps.action_items.models import ActionItem, ActionItemNote


@admin.register(ActionItem)
class ActionItemAdmin(ModelAdmin):  # type: ignore[misc]
    list_display = (
        "id",
        "title",
        "status",
        "scope",
        "source",
        "organisation",
        "created_at",
    )
    list_filter = ("status", "scope", "source", "priority")
    search_fields = ("title",)
    readonly_fields = ("source_review", "source")
    raw_id_fields = ("organisation", "shop", "assignee", "source_review")


@admin.register(ActionItemNote)
class ActionItemNoteAdmin(ModelAdmin):  # type: ignore[misc]
    list_display = ("id", "action_item", "author", "created_at")
    readonly_fields = ("action_item", "author", "body")
    raw_id_fields = ("action_item", "author")
