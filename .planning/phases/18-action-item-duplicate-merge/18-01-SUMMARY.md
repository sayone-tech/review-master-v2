---
phase: 18-action-item-duplicate-merge
plan: 01
subsystem: action_items
tags: [model, migration, foundation, duplicate-merge]
dependency_graph:
  requires: []
  provides:
    - "ActionItem.canonical self-FK (data foundation for duplicate merge)"
    - "Reverse accessor item.duplicates for fetching merged duplicates"
  affects:
    - apps/action_items/models.py
    - apps/action_items/migrations/
tech_stack:
  added: []
  patterns:
    - "Self-referential ForeignKey with SET_NULL cascade (safe-delete pattern)"
key_files:
  created:
    - apps/action_items/migrations/0003_actionitem_canonical.py
  modified:
    - apps/action_items/models.py
    - apps/action_items/tests/test_models.py
decisions:
  - "Used on_delete=SET_NULL (not CASCADE) so deleting a canonical item demotes its duplicates back to standalone rather than silently destroying them — preserves data and matches D-02"
  - "Field is nullable with no default — no data migration needed; all existing rows naturally have canonical=None"
  - "db_index=True on the ForeignKey is sufficient (Django auto-creates the index); no separate AddIndex op needed"
  - "Migration target uses 'action_items.actionitem' string (Django's resolved form of 'self') in migration output"
metrics:
  duration: "~5 minutes"
  completed: "2026-05-22"
  tasks_completed: 2
  files_modified: 3
requirements_completed: [D-01, D-02, D-04]
---

# Phase 18 Plan 01: ActionItem.canonical FK + Migration Summary

Added the `canonical` self-referential ForeignKey to `ActionItem` and shipped migration `0003_actionitem_canonical`, establishing the data foundation for the duplicate-merge feature (plans 18-02 through 18-04).

## What Was Built

- **`ActionItem.canonical`** — self-FK declared per D-01: `models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='duplicates', db_index=True)`. When set, marks the row as a merged duplicate pointing at its primary; when null, the row is standalone or canonical.
- **Reverse accessor `item.duplicates`** — `RelatedManager` returning every `ActionItem` whose `canonical_id == item.pk`. Used by plan 18-02's service layer.
- **Migration `0003_actionitem_canonical`** — single `AddField` op. Depends on `0002_actionitem_category`. Reversible (verified by Django migration framework's automatic reverse for `AddField`). `db_index=True` produces the FK index automatically — no separate `AddIndex` op.
- **Two new model tests** — `test_canonical_field_exists` (D-01 contract) and `test_canonical_set_null_on_delete` (D-02 cascade behavior).

## Deviations from Plan

None — plan executed exactly as written.

## Tasks Completed

| Task | Name | Commit |
| ---- | ---- | ------ |
| 1 | Add canonical FK to ActionItem + migration | 89ab681 |
| 2 | Wave 0 model tests — D-01 field + D-02 SET_NULL cascade | 7ab93f5 |

## Verification

- `uv run python manage.py makemigrations --check --dry-run` → "No changes detected" (model and migration agree)
- `uv run pytest apps/action_items/tests/test_models.py -x -q` → 8 passed, 1 skipped (partial-unique test is PG-only; pre-existing skip, not introduced by this plan)
- Field properties verified by direct introspection: `null=True, blank=True, related_name='duplicates', to=ActionItem, on_delete=SET_NULL, db_index=True`
- Pre-commit hooks (ruff-check, ruff-format, django-upgrade, mypy, bandit, gitleaks, missing-migrations) passed on both commits.

## Requirements Satisfied

- **D-01** — `ActionItem.canonical` FK declared exactly per spec.
- **D-02** — `test_canonical_set_null_on_delete` proves SET_NULL behavior (duplicate survives, `canonical` becomes `None`).
- **D-04** — Migration is reversible (standard `AddField` op; Django auto-generates reverse).

## Follow-ups Enabled

- **Plan 18-02** can now write `duplicate.canonical = primary; duplicate.save()` in the merge service.
- **Plan 18-02/03** can use the `duplicates` reverse accessor: `primary.duplicates.all()` to fetch merged children.
- **Plan 18-02** selector can exclude duplicates with `.filter(canonical__isnull=True)`.

## Self-Check: PASSED

- FOUND: apps/action_items/models.py (canonical field present)
- FOUND: apps/action_items/migrations/0003_actionitem_canonical.py
- FOUND: apps/action_items/tests/test_models.py (test_canonical_field_exists, test_canonical_set_null_on_delete)
- FOUND commit: 89ab681 (feat(18-01): add canonical FK to ActionItem + migration)
- FOUND commit: 7ab93f5 (test(18-01): add canonical FK field + SET_NULL cascade tests)
