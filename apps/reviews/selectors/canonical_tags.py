"""Phase 22 — Canonical tag selectors (read-side query helpers)."""

from __future__ import annotations

from apps.reviews.models import OrgCanonicalTag


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
