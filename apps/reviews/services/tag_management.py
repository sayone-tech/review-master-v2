"""Phase 25 — Canonical tag management services.

rename_canonical_tag: O(1) label update, rejects case-insensitive duplicates (D-03/D-04).
create_merge_job: validates and enqueues a user-directed merge (D-05/D-06/D-07).
merge_canonical_tags: executes the merge in transaction.atomic under per-org Redis lock (D-07).

Critical invariants (§29.2):
- review_count is NEVER incremented inline; refreshed only via _refresh_review_counts() aggregate.
- Rename touches ONLY OrgCanonicalTag.label — no ReviewTag fan-out.
- Merge re-points ReviewTag FKs in a SINGLE bulk UPDATE before source.delete().
- The user-chosen TARGET always wins (D-06 — do NOT delegate to _merge_group which picks by count).
- dispatch_notification is called AFTER the transaction.atomic block (Pitfall 4 — survives rollback).
"""

from __future__ import annotations

import logging

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.common.locks import distributed_lock
from apps.notifications.services.dispatch import dispatch_notification
from apps.reviews.models import OrgCanonicalTag, ReviewTag, TagMergeJob
from apps.reviews.services.finalise import _refresh_review_counts

logger = logging.getLogger(__name__)


def rename_canonical_tag(
    *,
    tag: OrgCanonicalTag,
    new_label: str,
    organisation_id: int,
) -> OrgCanonicalTag:
    """O(1) canonical tag label rename. Updates only OrgCanonicalTag.label (D-03).

    No ReviewTag rows are touched — rename is a single-row write.
    Title-Case normalization applied server-side (D-04).
    Rejects case-insensitive duplicates within the org (D-04, Pitfall 5).

    Raises:
        ValidationError: if new_label is empty/too long or case-insensitively duplicates
                         an existing label in the same org.
    """
    new_label = new_label.strip().title()

    if not (1 <= len(new_label) <= 100):
        raise ValidationError({"label": "Label must be 1-100 characters."})

    # Case-insensitive duplicate check — the DB UniqueConstraint is case-sensitive
    # so it does NOT prevent "Food Quality" and "food quality" from coexisting.
    # This guard is the authoritative collision defence (Pitfall 5, T-25-05).
    exists = (
        OrgCanonicalTag.objects.filter(
            organisation_id=organisation_id,
            label__iexact=new_label,
        )
        .exclude(pk=tag.pk)
        .exists()
    )
    if exists:
        raise ValidationError({"label": "A tag with that name already exists."})

    tag.label = new_label
    tag.save(update_fields=["label", "updated_at"])
    return tag


def create_merge_job(
    *,
    source_tag: OrgCanonicalTag,
    target_id: int,
    organisation_id: int,
) -> TagMergeJob:
    """Validate and create a TagMergeJob, then enqueue merge_canonical_tags_task.

    The user-chosen target is kept; source is deleted after FK re-point (D-06).
    Returns the newly created job.

    Raises:
        OrgCanonicalTag.DoesNotExist: if target_id doesn't exist in the caller's org.
        ValidationError: if target == source or an active job already exists (Pitfall 3 → HTTP 409).
    """
    # Fetch target within the same org (wrong org → DoesNotExist → caller maps to 404)
    target = OrgCanonicalTag.objects.get(pk=target_id, organisation_id=organisation_id)

    if source_tag.pk == target.pk:
        raise ValidationError({"target_id": "Source and target must be different tags."})

    # Reject if an active (PENDING/IN_PROGRESS) merge job already exists (Pitfall 3)
    active_exists = TagMergeJob.objects.filter(
        organisation_id=organisation_id,
        status__in=[TagMergeJob.Status.PENDING, TagMergeJob.Status.IN_PROGRESS],
        dismissed=False,
    ).exists()
    if active_exists:
        raise ValidationError(
            {
                "non_field_errors": (
                    "A merge is already in progress. Wait for it to complete before starting another."
                )
            }
        )

    # Denormalize labels at creation time — source_tag.label will be null after source.delete()
    job = TagMergeJob.objects.create(
        organisation_id=organisation_id,
        source_tag=source_tag,
        source_label=source_tag.label,  # Pitfall 6: must be set before source is deleted
        target_tag=target,
        target_label=target.label,
        status=TagMergeJob.Status.PENDING,
    )

    # Import inside function to avoid circular imports at module load (§12.3 pattern)
    from apps.reviews.tasks import merge_canonical_tags_task

    merge_canonical_tags_task.delay(job.pk)

    logger.info(
        "create_merge_job.created job_id=%s organisation_id=%s source=%r target=%r",
        job.pk,
        organisation_id,
        source_tag.label,
        target.label,
    )
    return job


@transaction.atomic
def merge_canonical_tags(*, job_id: int) -> None:
    """Execute a user-initiated canonical tag merge. Called by merge_canonical_tags_task.

    Winner = user-chosen target (D-06 — NOT higher review_count; do NOT use _merge_group).
    Source FKs re-pointed in a single bulk UPDATE before source.delete() (§6.10, Pitfall 4).
    review_count refreshed via aggregate after FK re-point (D-03 derive-on-read, Pitfall 2).
    Whole operation is transaction.atomic — rollback on any failure (D-07, T-25-AC3).
    Per-org Redis lock acquired non-blocking — exits cleanly if another worker holds it (Pitfall 3).
    dispatch_notification is called AFTER the atomic block so it is not rolled back (Pitfall 4).

    Raises:
        TagMergeJob.DoesNotExist: if job_id is not found.
        OrgCanonicalTag.DoesNotExist: if source/target don't belong to the job's org (T-25-AC1).
    """
    # Acquire per-org lock before any DB work (non-blocking — exit if held)
    job_for_org = TagMergeJob.objects.get(pk=job_id)
    org_id = job_for_org.organisation_id

    with distributed_lock(f"lock:tag_merge:org:{org_id}", timeout=300, blocking=False) as acquired:
        if not acquired:
            logger.info(
                "merge_canonical_tags.lock_not_acquired job_id=%s org_id=%s",
                job_id,
                org_id,
            )
            return  # Another worker holds the lock; exit cleanly (Pitfall 3)

        _execute_merge(job_id=job_id, org_id=org_id)


def _execute_merge(*, job_id: int, org_id: int) -> None:
    """Inner merge body wrapped in transaction.atomic.

    Separated from the distributed_lock context so that the atomic block can be
    correctly rolled back when an exception is raised mid-merge, while the FAILED
    status save (outside the re-raise) persists to a non-atomic save.
    """
    source_label: str = ""
    target_label: str = ""
    notification_org_id: int = org_id

    try:
        with transaction.atomic():
            # Row-level lock on the job (§12.4 Layer 3)
            job = TagMergeJob.objects.select_for_update().get(pk=job_id)

            # Idempotent guard — if already in a terminal state, no-op
            if job.status not in (TagMergeJob.Status.PENDING, TagMergeJob.Status.IN_PROGRESS):
                logger.info(
                    "merge_canonical_tags.idempotent_noop job_id=%s status=%s",
                    job_id,
                    job.status,
                )
                return

            # Org-scoped fetch — wrong-org ids raise DoesNotExist (T-25-AC1).
            # source_tag_id / target_tag_id are nullable FKs but are always set at
            # job creation time. Guard against corruption with explicit ValueError.
            if job.source_tag_id is None or job.target_tag_id is None:
                raise ValueError(f"TagMergeJob {job_id} has null source/target FK — job corrupt")
            source = OrgCanonicalTag.objects.get(pk=job.source_tag_id, organisation_id=org_id)
            target = OrgCanonicalTag.objects.get(pk=job.target_tag_id, organisation_id=org_id)

            source_label = source.label
            target_label = target.label

            job.status = TagMergeJob.Status.IN_PROGRESS
            job.total = source.review_count  # snapshot before deletion
            job.save(update_fields=["status", "total", "updated_at"])

            logger.info(
                "merge_canonical_tags.start job_id=%s org_id=%s source=%r target=%r total=%s",
                job_id,
                org_id,
                source_label,
                target_label,
                job.total,
            )

            # Single bulk UPDATE — one query (§6.10). FK re-point BEFORE delete (Pitfall 4).
            # D-06: target (user-chosen) wins. Do NOT call _merge_group (picks by count).
            processed = ReviewTag.objects.filter(canonical_tag=source).update(canonical_tag=target)
            source.delete()

            # Aggregate refresh — NEVER naive sum (D-03/Pitfall 2)
            _refresh_review_counts(organisation_id=org_id)

            job.processed = processed
            job.status = TagMergeJob.Status.SUCCESS
            job.save(update_fields=["status", "processed", "updated_at"])

            logger.info(
                "merge_canonical_tags.success job_id=%s org_id=%s processed=%s",
                job_id,
                org_id,
                processed,
            )

    except Exception as exc:
        # Save FAILED status outside atomic block so it survives the rollback
        try:
            TagMergeJob.objects.filter(pk=job_id).update(
                status=TagMergeJob.Status.FAILED,
                error_message=str(exc)[:2000],
            )
        except Exception:
            logger.error(
                "merge_canonical_tags.failed_to_save_failure job_id=%s",
                job_id,
                exc_info=True,
            )
        logger.error(
            "merge_canonical_tags.error job_id=%s org_id=%s error=%r",
            job_id,
            org_id,
            exc,
            exc_info=True,
        )
        raise

    # Dispatch notification AFTER the atomic block — not rolled back on failure (Pitfall 4)
    try:
        dispatch_notification(
            organisation_id=notification_org_id,
            notification_type="tag_merge_complete",
            title=f'Tag "{source_label}" merged into "{target_label}"',
            target_url="/admin/org/tags/",
            org_admins_only=True,
        )
    except Exception:
        # Notification failure does not fail the merge (best-effort delivery)
        logger.warning(
            "merge_canonical_tags.notification_failed job_id=%s org_id=%s",
            job_id,
            org_id,
            exc_info=True,
        )
