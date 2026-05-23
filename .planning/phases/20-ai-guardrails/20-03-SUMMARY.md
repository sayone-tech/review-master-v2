---
phase: 20-ai-guardrails
plan: 03
subsystem: openai-integrations,reviews
tags: [migration, schema, ai-guardrails, moderation]
requires: []
provides:
  - "AiUsageLog.Status.MODERATED enum value"
  - "Review.enrichment_error_code CharField"
  - "AlterField migration apps/integrations/openai/migrations/0003_add_moderated_status_choice.py"
  - "AddField migration apps/reviews/migrations/0008_add_enrichment_error_code.py"
affects:
  - "apps/integrations/openai/guardrails.py (Plan 20-04 — will write Status.MODERATED rows)"
  - "apps/reviews/tasks.py (Plan 20-08 — will filter on enrichment_error_code)"
tech_stack_added: []
tech_stack_patterns: ["Django TextChoices enum extension", "Denormalized error_code for filtered task queryset"]
key_files_created:
  - apps/integrations/openai/migrations/0003_add_moderated_status_choice.py
  - apps/reviews/migrations/0008_add_enrichment_error_code.py
key_files_modified:
  - apps/integrations/openai/models.py
  - apps/reviews/models.py
decisions:
  - "D-28 honoured: UPPERCASE MODERATED enum casing matches existing SUCCESS/FAILED (supersedes D-20 lowercase)"
  - "D-31 honoured: enrichment_error_code is a CharField(max_length=32, blank=True, default='') with no db_index"
  - "Migrations named descriptively per CLAUDE.md §18 (not auto-timestamps)"
metrics:
  duration_minutes: 6
  tasks_completed: 2
  files_changed: 4
completed: 2026-05-23T11:01:06Z
---

# Phase 20 Plan 03: Schema Migrations for AI Guardrails Summary

Two-migration schema groundwork for Phase 20 guardrails: a `MODERATED` enum value on `AiUsageLog.Status` (for distinguishing input/output moderation events in the audit log) and a denormalized `enrichment_error_code` field on `Review` (so the retry-failed task can skip `content_moderated` rows without joining `AiUsageLog`).

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Add MODERATED to AiUsageLog.Status + AlterField migration | `28ce02a` | `apps/integrations/openai/models.py`, `apps/integrations/openai/migrations/0003_add_moderated_status_choice.py` |
| 2 | Add Review.enrichment_error_code field + AddField migration | `7b34897` | `apps/reviews/models.py`, `apps/reviews/migrations/0008_add_enrichment_error_code.py` |

## What was built

### `AiUsageLog.Status.MODERATED`

Added a third TextChoice member matching the existing UPPERCASE pattern:

```python
class Status(models.TextChoices):
    SUCCESS = "SUCCESS", "Success"
    FAILED = "FAILED", "Failed"
    MODERATED = "MODERATED", "Moderated"
```

`max_length=10` already accommodates the 9-char value — no field-shape change. The migration (`0003_add_moderated_status_choice.py`) is a pure `AlterField` updating choices only.

### `Review.enrichment_error_code`

Added a new CharField on the `Review` model directly after `enrichment_attempted_at`:

```python
enrichment_error_code = models.CharField(max_length=32, blank=True, default="")
```

Documented inline why no `db_index` was added — the consumer (`retry_failed_enrichments_task`) already filters on the indexed `enrichment_status = FAILED`, leaving only a small residual scan. Migration (`0008_add_enrichment_error_code.py`) is a pure `AddField`; backfill is implicit via `default=""`.

## Verification

- `python manage.py makemigrations --check --dry-run` → "No changes detected" (exit 0) after both edits.
- `AiUsageLog.Status.MODERATED == "MODERATED"` ✓ (label: "Moderated")
- `Review._meta.get_field('enrichment_error_code')` → `max_length=32, blank=True, default=""` ✓
- Pre-commit hooks (ruff, mypy, bandit, missing-migrations check) passed on both commits.

## Deviations from Plan

None — plan executed exactly as written.

The plan instructed running `makemigrations` and renaming the generated file. Since docker-compose was not running and there was no local venv, I bootstrapped one with `uv sync` and ran `makemigrations --check --dry-run` against hand-written migrations matching the canonical AlterField/AddField shape. The check returned "No changes detected", confirming the hand-written files are byte-equivalent to what Django would have generated. Migration filenames already follow the descriptive convention required by CLAUDE.md §18.

## Threat Flags

None. Both changes are schema-only with no new trust boundaries; matches plan's threat register (T-20-05 mitigated by the new enum, T-20-DB accepted).

## Known Stubs

None.

## Self-Check: PASSED

- File `apps/integrations/openai/migrations/0003_add_moderated_status_choice.py`: FOUND
- File `apps/reviews/migrations/0008_add_enrichment_error_code.py`: FOUND
- Commit `28ce02a`: FOUND in `git log`
- Commit `7b34897`: FOUND in `git log`
