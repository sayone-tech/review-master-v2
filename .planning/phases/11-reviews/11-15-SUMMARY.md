---
phase: 11-reviews
plan: "15"
subsystem: reviews
tags: [model, migration, serializer, frontend, types, sentiment-badge, gap-closure]
dependency_graph:
  requires: []
  provides:
    - Review.tags JSONField (storage shape ready for Phase 12 enrichment)
    - ReviewReadSerializer tags field
    - ReviewTag TypeScript type
    - SentimentBadge tag chip rendering
  affects:
    - apps/reviews/models.py
    - apps/reviews/migrations/0003_review_tags.py
    - apps/reviews/serializers.py
    - frontend/src/widgets/review-management/types.ts
    - frontend/src/widgets/review-management/SentimentBadge.tsx
    - frontend/src/widgets/review-management/ReviewTable.tsx
    - .planning/REQUIREMENTS.md
tech_stack:
  added: []
  patterns:
    - JSONField with default=list for cross-DB compatible list-of-dicts storage
    - TAG_STYLES Record<TagPolarity, ...> for polarity-aware chip color tokens
    - MAX_TAGS = 5 enforced at render time (independent of model-level constraint)
key_files:
  created:
    - apps/reviews/migrations/0003_review_tags.py
  modified:
    - apps/reviews/models.py
    - apps/reviews/serializers.py
    - frontend/src/widgets/review-management/types.ts
    - frontend/src/widgets/review-management/SentimentBadge.tsx
    - frontend/src/widgets/review-management/ReviewTable.tsx
    - .planning/REQUIREMENTS.md
decisions:
  - JSONField chosen over ArrayField(JSONField()) — test DB is SQLite per config/settings/test.py; JSONField is cross-DB compatible; stores list-of-dicts natively in jsonb on Postgres
  - Storage shape: [{"label": str, "polarity": "positive"|"neutral"|"negative"}, ...] mirrors Phase 12 ENRCH-01 GPT response schema
  - MAX_TAGS=5 enforced at render time (UI cap); Phase 12 prompt enforces <=5 at write time independently
  - tags defaults to [] so all Phase 11 rows produce identical SentimentBadge output to pre-plan state (no visual regression)
  - REQUIREMENTS.md REVW-07 updated to reflect Phase 11 owns rendering; Phase 12 ENRCH-14 owns data population
metrics:
  duration_seconds: 149
  completed_date: "2026-05-02"
  tasks_completed: 2
  files_modified: 6
  files_created: 1
---

# Phase 11 Plan 15: REVW-07 Gap Closure — Tags Model + Rendering Scaffolding Summary

One-liner: Added Review.tags JSONField + migration + serializer field + TypeScript ReviewTag type + SentimentBadge tag chip rendering, closing the REVW-07 gap ahead of Phase 12 enrichment data.

## What Was Built

This plan closes the REVW-07 verification gap. The sentiment badge was already shipped (Phase 11 Plans 09–14), but the Review model had no `tags` field, so tag chips could not render. This plan delivers the full rendering scaffolding so that when Phase 12 enrichment populates `tags`, chips appear with no further frontend change.

### Task 1: Review.tags JSONField + Migration + Serializer

- Added `tags = models.JSONField(default=list, blank=True)` to `Review` model after `sentiment` field
- Generated migration `0003_review_tags.py` using a single `AddField` operation — reversible, cross-DB safe
- Added `"tags"` to `ReviewReadSerializer.Meta.fields` after `"sentiment"` (covered by `read_only_fields = fields`)
- All 15 existing review model and view tests pass with no changes

### Task 2: Frontend Type + Chip Rendering + REQUIREMENTS.md

- Added `TagPolarity` type alias and `ReviewTag` interface to `types.ts`
- Added `tags: ReviewTag[]` field to `ReviewRow` interface
- Updated `SentimentBadge.tsx` with `tags?: ReviewTag[]` prop, `TAG_STYLES` record, `MAX_TAGS = 5`, and chip render branch
- Updated `ReviewTable.tsx` to pass `tags={r.tags}` to `SentimentBadge`
- Updated `REQUIREMENTS.md` REVW-07 entry and traceability table row to reflect the Phase 11/12 split
- TypeScript type check passes with zero errors

## Design Decisions

### Why JSONField over ArrayField(JSONField())

PostgreSQL's `ArrayField` requires `django.contrib.postgres` and nests two Postgres-specific column types. The test suite uses SQLite (per `config/settings/test.py`), which does not support `ArrayField`. `JSONField` stores the list-of-dicts natively as `jsonb` on Postgres and as text JSON on SQLite — no test infrastructure changes needed.

### Storage Shape

```
[{"label": "fast service", "polarity": "positive"}, ...]
```

Mirrors the Phase 12 `Tag` Pydantic model from ENRCH-01:
```python
class Tag(BaseModel):
    label: str
    polarity: Literal["positive", "negative", "neutral"]
```

### MAX_TAGS = 5

Enforced at render time in `SentimentBadge` (`tags.slice(0, MAX_TAGS)`). This is a UI safety cap — Phase 12's GPT prompt will enforce ≤5 tags at write time. The two constraints operate independently, ensuring no chips overflow the badge regardless of data quality.

### SentimentBadge Behaviour Matrix

| `enrichment_status` | `tags`    | Rendered output |
|---------------------|-----------|-----------------|
| `FAILED`            | any       | Red AlertCircle icon (chips suppressed) |
| `PENDING`           | any       | "Analyzing..." amber pill (chips suppressed) |
| `IN_PROGRESS`       | any       | "Analyzing..." amber pill (chips suppressed) |
| `SUCCESS`           | `[]`      | Sentiment pill only — current Phase 11 production state |
| `SUCCESS`           | `[...]`   | Sentiment pill + up to 5 polarity-colored chips — Phase 12 production state |

The empty-tags case is the current state for all Phase 11 rows (enrichment has not run yet), so the badge output is visually identical to before this plan — no visual regression.

### REQUIREMENTS.md Update Rationale

REVW-07 was previously marked `Complete` in REQUIREMENTS.md but the verification file flagged it as partial (tag chips absent because the model had no `tags` field). This plan closes the rendering half. The data half (enrichment populating `tags`) is Phase 12 ENRCH-14. The REVW-07 entry and traceability row now accurately reflect this split, preventing future audit confusion about which phase owns which deliverable.

## Commits

| Hash | Message |
|------|---------|
| cb2afb9 | feat(11-15): add tags JSONField to Review model and migration; expose in serializer |
| ae3f0c2 | feat(11-15): add ReviewTag type, tag chip rendering in SentimentBadge, update REQUIREMENTS.md |

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check

Verified before writing this summary:
- `apps/reviews/models.py` contains `tags = models.JSONField(default=list, blank=True)` — FOUND
- `apps/reviews/migrations/0003_review_tags.py` exists — FOUND
- `apps/reviews/serializers.py` contains `"tags"` — FOUND
- `frontend/src/widgets/review-management/types.ts` contains `ReviewTag` — FOUND
- `frontend/src/widgets/review-management/SentimentBadge.tsx` contains `TAG_STYLES` and `MAX_TAGS = 5` — FOUND
- `frontend/src/widgets/review-management/ReviewTable.tsx` contains `tags={r.tags}` — FOUND
- `.planning/REQUIREMENTS.md` contains "rendering scaffolding delivered in Phase 11 plan 11-15" — FOUND
- 69 review tests pass (0 failures)
- TypeScript type check: 0 errors
- `makemigrations --check`: No changes detected
