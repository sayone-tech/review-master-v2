"""Phase 12 — AiPricing (time-versioned) + AiUsageLog (immutable per-call record).

Per CLAUDE.md §14.3 and §14.4:
  - cost is computed at log time using the active AiPricing row
  - historical AiUsageLog.estimated_cost_usd is never recomputed
  - new pricing rows close the previous row by setting effective_to
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import ClassVar

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.common.models import AuditLog


class AiPricingQuerySet(models.QuerySet["AiPricing"]):
    def active_at(self, at: datetime) -> AiPricingQuerySet:
        """Rows whose window covers ``at``: effective_from <= at < coalesce(effective_to, inf)."""
        return self.filter(Q(effective_to__isnull=True) | Q(effective_to__gt=at)).filter(
            effective_from__lte=at
        )

    def get_active(self, *, model: str, at: datetime | None = None) -> AiPricing:
        """Return the pricing row for ``model`` that is active at ``at`` (default: now).

        Time-window lookup, so a scheduled (future) row never prices current
        usage. If windows ever overlap (e.g. a hand edit), the row with the latest
        ``effective_from`` wins instead of raising ``MultipleObjectsReturned``.
        Raises ``AiPricing.DoesNotExist`` when no row covers the time.
        """
        row = (
            self.active_at(at or timezone.now())
            .filter(model=model)
            .order_by("-effective_from", "-pk")
            .first()
        )
        if row is None:
            raise self.model.DoesNotExist(f"No AiPricing row active for model {model!r}.")
        return row


class AiPricing(models.Model):
    class Source(models.TextChoices):
        MANUAL = "manual", "Manual"
        SYNC = "sync", "Sync"
        SEED = "seed", "Seed"

    model = models.CharField(max_length=100)
    input_token_price_per_1m = models.DecimalField(max_digits=12, decimal_places=8)
    output_token_price_per_1m = models.DecimalField(max_digits=12, decimal_places=8)
    cached_token_price_per_1m = models.DecimalField(max_digits=12, decimal_places=8)
    effective_from = models.DateTimeField()
    effective_to = models.DateTimeField(null=True, blank=True)
    source = models.CharField(
        max_length=10, choices=Source.choices, default=Source.MANUAL, db_index=False
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        db_index=True,  # FK default, kept: SET_NULL on user delete scans by created_by
    )

    objects: ClassVar[AiPricingQuerySet] = AiPricingQuerySet.as_manager()  # type: ignore[assignment]

    class Meta:
        db_table = "openai_ai_pricing"
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=["model", "effective_from"],
                name="ai_pricing_model_from_uniq",
            ),
            models.UniqueConstraint(
                fields=["model"],
                condition=Q(effective_to__isnull=True),
                name="ai_pricing_one_open_row_per_model",
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
            models.Index(
                fields=["organisation", "status", "created_at"],
                name="ai_usage_org_stat_cr_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"AiUsageLog(model={self.model}, status={self.status})"


class AiPricingSyncConfig(models.Model):
    """Singleton (pk=1) holding the LiteLLM pricing auto-sync switch and last-run state."""

    class Status(models.TextChoices):
        NEVER = "never", "Never run"
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"

    enabled = models.BooleanField(default=False)
    last_run_at = models.DateTimeField(null=True, blank=True)
    last_success_at = models.DateTimeField(null=True, blank=True)
    last_status = models.CharField(max_length=10, choices=Status.choices, default=Status.NEVER)
    last_error = models.TextField(blank=True)
    last_summary = models.JSONField(default=dict, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "openai_ai_pricing_sync_config"
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.CheckConstraint(condition=Q(pk=1), name="ai_pricing_sync_config_singleton"),
        ]

    def __str__(self) -> str:
        return f"AiPricingSyncConfig(enabled={self.enabled})"

    @classmethod
    def load(cls) -> AiPricingSyncConfig:
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class PlatformAuditLog(AuditLog):
    """Proxy exposing platform-level (organisation NULL) pricing audit rows in admin."""

    class Meta:
        proxy = True
        app_label = "openai"
        verbose_name = "platform audit log"
