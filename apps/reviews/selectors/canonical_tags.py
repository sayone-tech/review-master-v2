"""Phase 22/23 — Canonical tag selectors (read-only query helpers)."""

from __future__ import annotations

from django.db.models import Count, QuerySet
from django.db.models.functions import Lower

from apps.reviews.models import OrgCanonicalTag, ReviewTag


def get_org_vocabulary(*, organisation_id: int, limit: int) -> list[str]:
    """Return the org's top-N canonical labels ordered by ``-review_count``.

    D-02/CTAG-03: the caller passes ``limit=settings.CANONICAL_VOCAB_INJECT_LIMIT``
    so only the most-used vocabulary is injected into the single enrichment
    prompt. Read-only and fully bounded — a single query that exploits the
    ``orgcanon_org_count_idx`` index and slices to ``limit``.

    Settings are read by the caller, never inside the selector, so this stays a
    pure read helper (CLAUDE.md §5).
    """
    return list(
        OrgCanonicalTag.objects.filter(organisation_id=organisation_id)
        .order_by("-review_count")
        .values_list("label", flat=True)[:limit]
    )


def get_duplicate_canonical_tag_groups(*, organisation_id: int) -> list[str]:
    """Return lowercased labels that appear ≥2 times case-insensitively in the org.

    D-05: duplicate detection is case-insensitive label match only — no fuzzy or
    semantic comparison. Each returned string is a lowercase label that has two or
    more OrgCanonicalTag rows in the org (e.g. "food quality" matches rows with
    label "Food Quality", "food quality", "FOOD QUALITY").

    Read-only — no mutations (CLAUDE.md §5 selector rules).
    Org-scoped: only rows for ``organisation_id`` are examined (T-23-03).
    """
    return list(
        OrgCanonicalTag.objects.filter(organisation_id=organisation_id)
        .annotate(lower_label=Lower("label"))
        .values("lower_label")
        .annotate(count=Count("id"))
        .filter(count__gte=2)
        .values_list("lower_label", flat=True)
    )


def list_canonical_tags_for_org(*, organisation_id: int) -> QuerySet[OrgCanonicalTag]:
    """Return all org canonical tags for the paginated tag list endpoint (TMGT-02).

    One query — no prefetch needed (no nested FKs in the response shape).
    Default ordering: highest review_count first, then alphabetical by label.
    The viewset's OrderingFilter overrides ordering via ?ordering= query param.
    Query ceiling: 1 COUNT + 1 SELECT = 2 queries max for a paginated response (§6.9).
    """
    return OrgCanonicalTag.objects.filter(organisation_id=organisation_id).order_by(
        "-review_count", "label"
    )


def get_null_straggler_review_tags(*, organisation_id: int, limit: int) -> QuerySet[ReviewTag]:
    """Return ReviewTag rows with null canonical_tag whose review belongs to the org.

    Bounded by ``limit`` to prevent unbounded scans (T-23-05). Only reviews that
    are not soft-deleted are considered (``review__deleted_at__isnull=True``).

    Read-only — no mutations (CLAUDE.md §5 selector rules).
    Org-scoped: filters through ``review__organisation_id`` (T-23-03).
    """
    return (
        ReviewTag.objects.filter(
            canonical_tag__isnull=True,
            review__organisation_id=organisation_id,
            review__deleted_at__isnull=True,
        )
        .select_related("review")
        .order_by("id")[:limit]
    )
