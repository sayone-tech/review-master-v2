---
paths:
  - "apps/**/migrations/*.py"
---

# Migration Rules

Concise reminder — full detail in CLAUDE.md §6 (DB) + §18 (git/migrations).

- **Reversible.** Every migration must reverse cleanly — provide a `reverse_code` for `RunPython`; avoid one-way destructive ops. Verify the down-path, not just the up-path.
- **No silent data loss.** Guard destructive schema changes; keep **schema migrations separate from data migrations**. Don't backfill in the same migration that adds the column unless intentional and reversible.
- **One migration per PR** where possible. Descriptive name — never leave `0014_auto_20260101`.
- **Every new field = an explicit `db_index` decision.** Add `Meta.indexes` (incl. composite) for real filter/order/FK query shapes (§6.8).
- **Batch data migrations** — `bulk_create` / `bulk_update` / `update()` / `F()`; never a per-row `.save()` loop.
- Run `python manage.py makemigrations --check --dry-run` before committing (pre-commit enforces); seed Celery Beat schedules via a data migration (§12.5).
- Tenant-aware backfills stay org-scoped.
