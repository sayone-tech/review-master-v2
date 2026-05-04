"""Phase 12 — One-time backfill management command (ENRCH-13).

Enqueues `enrich_review_task` for every Review currently in PENDING state
that is NOT soft-deleted. Operators run this once per environment after
Phase 12 deploys to drain the Phase 11 backlog. After this command runs,
the live pipeline (Plan 04 sync wiring + retry_failed_enrichments_task)
handles every subsequent enrichment.

Idempotent: re-running this command is safe. Plan 04's enrich_review()
exits cleanly when a review's status is already IN_PROGRESS or SUCCESS
(three-layer idempotency, ENRCH-02), so duplicate dispatches are no-ops.

Flags:
  --dry-run    Print the count without dispatching any tasks.
  --limit N    Cap the number of reviews enqueued in this invocation.

Conventions: CLAUDE.md §10 (thin management command — calls the service
layer, no business logic in the command body).
"""

from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand, CommandParser

from apps.reviews.models import Review
from apps.reviews.tasks import enrich_review_task


class Command(BaseCommand):
    help = "Enqueue enrichment for all PENDING reviews (post-Phase 11 backfill)."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help=(
                "Print the count of reviews that would be enqueued without "
                "calling enrich_review_task.delay()."
            ),
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help=("Cap the number of reviews enqueued in this run. Defaults to no cap."),
        )

    def handle(self, *args: Any, **options: Any) -> None:
        limit: int | None = options.get("limit")
        dry_run: bool = bool(options.get("dry_run"))

        qs = (
            Review.objects.filter(
                enrichment_status=Review.EnrichmentStatus.PENDING,
                deleted_at__isnull=True,
            )
            .order_by("id")
            .values_list("id", flat=True)
        )
        if limit is not None:
            qs = qs[:limit]
        ids = list(qs)

        if not dry_run:
            for review_id in ids:
                enrich_review_task.delay(review_id)

        prefix = "[dry-run] " if dry_run else ""
        self.stdout.write(f"{prefix}Enqueued {len(ids)} reviews for enrichment.")
