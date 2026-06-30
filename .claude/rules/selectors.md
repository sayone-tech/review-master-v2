---
paths:
  - "apps/**/selectors/*.py"
---

# Selector Rules (read-side)

Concise reminder — full rationale in CLAUDE.md §5 (services/selectors) + §6 (no-N+1).

- **Read-only. No mutations, ever** — selectors return data/querysets; never `.create()`/`.save()`/`.update()`/`.delete()`.
- **No N+1 (blocker-level, §6):** `select_related` for forward FK/OneToOne, `prefetch_related` for reverse FK / M2M, `Prefetch(...)` for filtered/ordered inner querysets.
- Counts via `annotate(Count(...))` — **never** `len(queryset)`.
- `.only()` / `.defer()` when serializing wide tables with few columns.
- Keyword-only args (`def get_x(*, ...)`). Prefer reusable custom `QuerySet`/manager methods over ad-hoc filters.
- **Tenant scope:** org/staff reads filter by `organisation_id` (and Staff `StaffAccessScope` / brand-vs-shop) — §9/§22.
- Every list-backing selector needs a query-count test (`CaptureQueriesContext`, fixed ceiling) — §6.9.
