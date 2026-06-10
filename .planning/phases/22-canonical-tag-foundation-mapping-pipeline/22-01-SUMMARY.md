---
phase: 22
plan: "01"
subsystem: reviews/models
tags: [models, migration, factories, tests, canonical-tags]
requirements: [CTAG-01, CTAG-02, CTAG-08]

dependency_graph:
  requires: []
  provides:
    - OrgCanonicalTag model (apps/reviews/models.py)
    - ReviewTag.canonical_tag nullable FK (apps/reviews/models.py)
    - Migration 0011 (apps/reviews/migrations/)
    - OrgCanonicalTagFactory (apps/reviews/tests/factories.py)
  affects:
    - apps/reviews/models.py (new model + FK field on ReviewTag)
    - apps/reviews/migrations/ (new migration 0011)
    - apps/reviews/tests/factories.py (new OrgCanonicalTagFactory)
    - apps/reviews/tests/test_models.py (new TestOrgCanonicalTagModel)

tech_stack:
  added: []
  patterns:
    - TimeStampedModel inheritance for OrgCanonicalTag
    - TextChoices enum for PolarityType (always_positive/always_negative/mixed)
    - ClassVar-typed Meta with UniqueConstraint + Index (mypy strict)
    - Nullable SET_NULL FK (D-04: FK-only storage, no denormalized label)
    - OrgCanonicalTagFactory with SubFactory(OrganisationFactory)

key_files:
  created:
    - apps/reviews/migrations/0011_orgcanonicaltag_reviewtag_canonical_tag.py
  modified:
    - apps/reviews/models.py
    - apps/reviews/tests/factories.py
    - apps/reviews/tests/test_models.py

decisions:
  - "review_count field is a denormalized cache column defaulting to 0, never incremented in the enrichment hot path (D-03 — refreshed only by Phase 24 weekly job / Phase 25 merge)"
  - "canonical_tag FK excluded from uniq_reviewtag_review_label_polarity constraint to preserve the delete-then-bulk_create race guard (Phase 17 CR-02)"
  - "OrgCanonicalTag defined before ReviewTag in models.py so the forward reference in ReviewTag.canonical_tag FK resolves without string quoting issues"

metrics:
  duration: "~8 minutes"
  completed: "2026-06-10"
  tasks_completed: 3
  files_changed: 4
---

# Phase 22 Plan 01: OrgCanonicalTag Foundation Summary

Per-org canonical tag data layer: `OrgCanonicalTag` model + nullable `ReviewTag.canonical_tag` FK + single non-backfilling migration.

## What Was Built

### OrgCanonicalTag model (`apps/reviews/models.py`)

- Inherits `TimeStampedModel` for `created_at`/`updated_at` — no fields redeclared
- `PolarityType(TextChoices)`: `ALWAYS_POSITIVE`, `ALWAYS_NEGATIVE`, `MIXED`
- `organisation` FK to `organisations.Organisation` with `db_index=True` (tenant scoping per CLAUDE.md §9)
- `label = CharField(max_length=100)`
- `polarity_type = CharField(max_length=20, choices=PolarityType.choices)`
- `review_count = PositiveIntegerField(default=0)` — denormalized cache only (D-03)
- `Meta.db_table = "reviews_orgcanonicaltag"`
- `Meta.constraints`: `uniq_orgcanonicaltag_org_label` on `(organisation, label)`
- `Meta.indexes`: `orgcanon_org_count_idx` on `(organisation, -review_count)`
- `ClassVar[list[...]]` typed Meta per mypy strict conventions (CLAUDE.md §17)

### ReviewTag.canonical_tag FK (`apps/reviews/models.py`)

- `canonical_tag = ForeignKey("reviews.OrgCanonicalTag", null=True, blank=True, on_delete=SET_NULL, related_name="review_tags", db_index=True)`
- `uniq_reviewtag_review_label_polarity` constraint unchanged — still `["review", "label", "polarity"]` only

### Migration 0011 (`apps/reviews/migrations/0011_orgcanonicaltag_reviewtag_canonical_tag.py`)

- Single migration: CreateModel OrgCanonicalTag + AddField ReviewTag.canonical_tag + AddIndex + AddConstraint
- No RunPython backfill (CTAG-08 — pre-phase rows retain `canonical_tag=NULL`)
- Dependencies: `organisations.0002_organisation_allow_custom_sync_depth`, `reviews.0010_add_enrichment_error_code`

### OrgCanonicalTagFactory (`apps/reviews/tests/factories.py`)

- `organisation = SubFactory(OrganisationFactory)`
- `label = Sequence(lambda n: f"Canonical {n}")`
- `polarity_type = OrgCanonicalTag.PolarityType.MIXED`
- `review_count = 0`
- `ReviewTagFactory` updated with `canonical_tag = None` default

### TestOrgCanonicalTagModel (`apps/reviews/tests/test_models.py`)

6 tests covering CTAG-01, CTAG-02, CTAG-08:
1. `test_canonical_tag_creation_and_timestamps` — pk, label, polarity_type, review_count, timestamps
2. `test_canonical_tag_polarity_type_mixed` — all three PolarityType values
3. `test_canonical_tag_unique_org_label_constraint` — same (org, label) raises IntegrityError
4. `test_canonical_tag_cross_org_same_label_allowed` — different orgs share label
5. `test_null_canonical_tag_review_tag_valid` — ReviewTag with null canonical_tag is valid
6. `test_review_tag_with_canonical_tag_resolves_fk` — FK resolution via select_related

## Commits

| Hash | Type | Description |
|------|------|-------------|
| de89cee | feat(22-01) | OrgCanonicalTag model + nullable ReviewTag.canonical_tag FK + factory + tests |
| 556680f | chore(22-01) | Migration 0011 for OrgCanonicalTag + ReviewTag.canonical_tag FK |

## Deviations from Plan

### Auto-resolved: factory needed before GREEN tests

The TDD tasks 1 and 3 share a single commit because `OrgCanonicalTagFactory` was required for the model tests to run (the factory import would fail otherwise). Factory and model were committed together in one `feat` commit, migration in a separate `chore` commit.

No other deviations.

## Known Stubs

None — this plan creates only the data layer foundation. No UI, no API endpoints, no wired data sources.

## Threat Flags

None — no new network endpoints or auth paths introduced. The `OrgCanonicalTag` model has a direct `organisation` FK enforcing tenant isolation at the schema level (T-22-01 mitigated). `ReviewTag.canonical_tag` uses `SET_NULL` so deleting a canonical tag cannot cascade-destroy review tags (T-22-02 mitigated).

## Self-Check

- [x] `apps/reviews/models.py` contains `class OrgCanonicalTag(TimeStampedModel)`
- [x] `apps/reviews/migrations/0011_orgcanonicaltag_reviewtag_canonical_tag.py` exists
- [x] `apps/reviews/tests/factories.py` contains `class OrgCanonicalTagFactory`
- [x] `apps/reviews/tests/test_models.py` contains `class TestOrgCanonicalTagModel`
- [x] Migration has no RunPython backfill
- [x] `uniq_reviewtag_review_label_polarity` still on `["review", "label", "polarity"]` only
- [x] Commits de89cee and 556680f exist in git log
- [x] Pre-commit hooks passed (ruff, mypy, bandit, migration check)

## Self-Check: PASSED
