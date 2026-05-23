"""Phase 12 — AiPricing (time-versioned) + AiUsageLog (immutable per-call record).

Per CLAUDE.md §14.3 and §14.4:
  - cost is computed at log time using the active AiPricing row
  - historical AiUsageLog.estimated_cost_usd is never recomputed
  - new pricing rows close the previous row by setting effective_to
"""

from __future__ import annotations

from decimal import Decimal
from typing import ClassVar

from django.db import models
from django.utils import timezone


class AiPricingQuerySet(models.QuerySet["AiPricing"]):
    def get_active(self, *, model: str) -> AiPricing:
        """Return the active pricing row for a model.

        Active = effective_to IS NULL. There must be exactly one active row
        per model at any time (the seed migration enforces this; admin actions
        that close one row and open another must use select_for_update).
        """
        return self.get(model=model, effective_to__isnull=True)


class AiPricing(models.Model):
    model = models.CharField(max_length=100)
    input_token_price_per_1m = models.DecimalField(max_digits=12, decimal_places=8)
    output_token_price_per_1m = models.DecimalField(max_digits=12, decimal_places=8)
    cached_token_price_per_1m = models.DecimalField(max_digits=12, decimal_places=8)
    effective_from = models.DateTimeField()
    effective_to = models.DateTimeField(null=True, blank=True)

    objects: ClassVar[AiPricingQuerySet] = AiPricingQuerySet.as_manager()  # type: ignore[assignment]

    class Meta:
        db_table = "openai_ai_pricing"
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=["model", "effective_from"],
                name="ai_pricing_model_from_uniq",
            ),
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=["model", "effective_from"], name="ai_pricing_lookup_idx"),
        ]

    def __str__(self) -> str:
        return f"AiPricing(model={self.model}, from={self.effective_from})"


class AiUsageLog(models.Model):
    class Status(models.TextChoices):
        SUCCESS = "SUCCESS", "Success"
        FAILED = "FAILED", "Failed"
        MODERATED = "MODERATED", "Moderated"

    organisation = models.ForeignKey(
        "organisations.Organisation",
        on_delete=models.CASCADE,
        related_name="ai_usage_logs",
        db_index=True,
    )
    review = models.ForeignKey(
        "reviews.Review",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ai_usage_logs",
    )
    request_type = models.CharField(max_length=32, default="enrichment")
    model = models.CharField(max_length=100)

    prompt_tokens = models.PositiveIntegerField(null=True, blank=True)
    completion_tokens = models.PositiveIntegerField(null=True, blank=True)
    cached_tokens = models.PositiveIntegerField(null=True, blank=True, default=0)
    total_tokens = models.PositiveIntegerField(null=True, blank=True)

    estimated_cost_usd = models.DecimalField(max_digits=12, decimal_places=8, default=Decimal("0"))
    latency_ms = models.PositiveIntegerField(null=True, blank=True)
    langsmith_trace_id = models.CharField(max_length=64, blank=True)

    status = models.CharField(max_length=10, choices=Status.choices)
    error_code = models.CharField(max_length=64, blank=True)
    error_message = models.TextField(blank=True)

    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        db_table = "openai_ai_usage_log"
        ordering: ClassVar[list[str]] = ["-created_at"]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=["organisation", "created_at"], name="ai_usage_org_created_idx"),
            models.Index(fields=["review"], name="ai_usage_review_idx"),
            models.Index(fields=["status"], name="ai_usage_status_idx"),
        ]

    def __str__(self) -> str:
        return f"AiUsageLog(model={self.model}, status={self.status})"
