"""Phase 13 — ActionItem and ActionItemNote models.

ActionItem rows are created two ways:
1. AI extraction — promoted from Review.extracted_action_items JSON after enrichment
   succeeds. The partial unique constraint on (source_review, title, scope) WHERE
   source = 'AI' makes promotion idempotent: re-enrichment uses
   bulk_create(ignore_conflicts=True) and duplicates are silently dropped.
2. Manual creation — Org Admin or Staff create rows directly via the API.

ActionItemNote rows are append-only (CONTEXT.md decision): no edit, no delete,
ordered oldest-first.
"""

from __future__ import annotations

from typing import ClassVar

from django.conf import settings
from django.db import models

from apps.common.models import TimeStampedModel


class ActionItem(TimeStampedModel):
    class Status(models.TextChoices):
        TODO = "TODO", "To Do"
        IN_PROGRESS = "IN_PROGRESS", "In Progress"
        COMPLETE = "COMPLETE", "Complete"
        WONT_DO = "WONT_DO", "Won't Do"

    class Scope(models.TextChoices):
        SHOP = "SHOP", "Shop"
        BRAND = "BRAND", "Brand"

    class Priority(models.TextChoices):
        HIGH = "HIGH", "High"
        MEDIUM = "MEDIUM", "Medium"
        LOW = "LOW", "Low"

    class Source(models.TextChoices):
        AI = "AI", "AI Extracted"
        MANUAL = "MANUAL", "Manual"

    organisation = models.ForeignKey(
        "organisations.Organisation",
        on_delete=models.CASCADE,
        db_index=True,
        related_name="action_items",
    )
    title = models.CharField(max_length=200)
    status = models.CharField(
        max_length=15, choices=Status.choices, default=Status.TODO, db_index=True
    )
    scope = models.CharField(max_length=10, choices=Scope.choices, db_index=True)
    priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.MEDIUM)
    source = models.CharField(
        max_length=10, choices=Source.choices, default=Source.MANUAL, db_index=True
    )
    shop = models.ForeignKey(
        "shops.Shop",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="action_items",
    )
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assigned_action_items",
    )
    due_date = models.DateField(null=True, blank=True, db_index=True)
    source_review = models.ForeignKey(
        "reviews.Review",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="action_items",
    )

    class Meta:
        db_table = "action_items_actionitem"
        ordering: ClassVar[list[str]] = ["-created_at"]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(
                fields=["organisation", "status", "scope"],
                name="ai_org_status_scope_idx",
            ),
            models.Index(fields=["organisation", "due_date"], name="ai_org_due_idx"),
            models.Index(fields=["organisation", "assignee"], name="ai_org_assignee_idx"),
        ]
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=["source_review", "title", "scope"],
                condition=models.Q(source="AI"),
                name="ai_unique_per_review_title_scope",
            ),
        ]

    def __str__(self) -> str:
        return f"ActionItem({self.pk}, {self.title!r}, {self.status})"


class ActionItemNote(TimeStampedModel):
    action_item = models.ForeignKey(ActionItem, on_delete=models.CASCADE, related_name="notes")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    body = models.TextField(max_length=2000)

    class Meta:
        db_table = "action_items_actionitemnote"
        ordering: ClassVar[list[str]] = ["created_at"]  # oldest-first per CONTEXT.md

    def __str__(self) -> str:
        return f"ActionItemNote({self.pk}, action_item={self.action_item_id})"
