---
phase: 17-tag-rework-reviewtag-model-and-filter
review: 17-REVIEW.md
status: all_fixed
fix_scope: critical_warning
findings_in_scope: 8
fixed: 8
skipped: 0
post_fix_tests:
  backend: 143 passed (apps/reviews/tests/)
  frontend_tsc: clean
---

# Plan 17 Review Fix Report

All Critical and Warning findings fixed across 3 atomic commits. Info findings (IN-01..IN-04) were out of scope; IN-04 is implicitly resolved by CR-02's UNIQUE constraint.

## Commits

- `68454b5` — fix(17): CR-01/WR-01/WR-06 rewrite filter_tags with Exists(OuterRef)
- `e458da4` — fix(17): CR-02 add UniqueConstraint(review,label,polarity) on ReviewTag
- `8d7bbb2` — fix(17): WR-02/WR-03/WR-04/WR-05 harden /reviews/tags/ + tighten polarity contract

## Per-finding

### CR-01 + WR-01 + WR-06 — `filter_tags` row-multiplication

**Status:** fixed (`68454b5`)
**Files:** `apps/reviews/filters.py`, `apps/reviews/tests/test_views.py`

Replaced the chained `filter(tags__label__iexact=label).distinct()` loop with one `Exists(OuterRef("pk"))` correlated subquery per requested label. The previous form row-multiplied multi-tag reviews; `.distinct()` suppressed dupes at SELECT but did NOT propagate to `.aggregate()`, silently inflating `Avg("star_rating")` and the filtered `Count(...)` calls used by `/stats/` (CR-01 and the WR-06 echo). Adds a regression test asserting `avg_rating` and `positive_sentiment_pct` are unchanged by a multi-tag review under `?tags=`.

### CR-02 — Cross-transaction race in enrich_review write path

**Status:** fixed (`e458da4`)
**Files:** `apps/reviews/models.py`, `apps/reviews/migrations/0009_reviewtag_unique.py`

Added `UniqueConstraint(fields=["review", "label", "polarity"], name="uniq_reviewtag_review_label_polarity")` to `ReviewTag.Meta`. DB-level guard for the cross-transaction race in `enrich_review` (Redis lock fails open under outage with `IGNORE_EXCEPTIONS`). On race the second `bulk_create` raises `IntegrityError` and the second worker's `transaction.atomic()` rolls back the delete cleanly, leaving the first worker's tags intact. Migration `0009_reviewtag_unique.py` accompanies the model change in the same atomic commit (pre-commit `missing-migrations` gate green).

### WR-02 — `/reviews/tags/?shop=abc` raises 500

**Status:** fixed (`8d7bbb2`)
**File:** `apps/reviews/views.py`

`shop` is now validated as an int and returns 400 on bad input instead of letting `ValueError` propagate to a 500. Mirrors the django-filter `NumberFilter` contract on the list endpoint. Regression test asserts 400.

### WR-03 — `/reviews/tags/` unpaginated/unlimited

**Status:** fixed (`8d7bbb2`)
**File:** `apps/reviews/views.py`

Hard-capped at top-N by count (default 200, `?limit=` override, ceiling 500). The endpoint feeds a UI combobox, not a paginated list, so a hard cap is more appropriate than pagination here. Long-tail tag management is a future phase.

### WR-04 — No Staff-no-scope test on `/reviews/tags/`

**Status:** fixed (`8d7bbb2`)
**File:** `apps/reviews/tests/test_views.py`

Lock test added: STAFF_ADMIN with zero `StaffAccessScope` rows gets `[]` from `/reviews/tags/`.

### WR-05 — `ReviewTagSerializer.polarity` was `CharField`

**Status:** fixed (`8d7bbb2`)
**File:** `apps/reviews/serializers.py`

Changed to `ChoiceField(choices=ReviewTag.Polarity.choices)` so drf-spectacular emits the enum in the OpenAPI schema. Frontend `TagPolarity` is already a strict literal union — the previous CharField hid the constraint.

## Post-fix verification

- `pytest apps/reviews/tests/` → 143 passed, 46 warnings (was 140 before the new regression tests).
- `tsc --noEmit` (frontend) → clean.
- Pre-commit pipeline green on every commit (ruff, mypy strict, bandit, django-upgrade, missing-migrations).

## Info findings (out of scope, fix_scope=critical_warning)

- **IN-01** — `ReviewTag` lacks `Meta.ordering`. Address in a follow-up if chip-order stability is observed to flap.
- **IN-02 / IN-03** — TagsFilter `aria-busy` + `aria-activedescendant`. Address in a focused accessibility pass.
- **IN-04** — React key `${label}-${polarity}` collision risk — **implicitly resolved** by CR-02's UNIQUE constraint on `(review, label, polarity)`.
