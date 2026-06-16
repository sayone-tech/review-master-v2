---
name: feature-impact
description: >-
  Map every module a feature change affects and run the regressions, so nothing downstream is missed in this layered Django repo (model → migration → service → selector → view → serializer → url → permission → task → consumer → tests → docs/requirements). Uses the code-review-graph knowledge graph (get_impact_radius, get_affected_flows, detect_changes) to find callers/dependents, builds an update checklist, then runs the affected app tests + the FULL suite + makemigrations --check, and invokes orm-performance-auditor / tenant-security-auditor / test-author for the relevant surfaces. Use AFTER building a feature and BEFORE declaring it "done" / opening a PR, or when the user asks "check impact", "what else needs updating", "did I miss anything", "run regressions", "make sure nothing broke", or "is this complete".
---

# Feature Impact & Regression Check

Goal: prove a feature change is **complete across every affected layer** and **introduces no regression**. Anchored by the Phase-24 lesson — a change can break a *distant* module (e.g. test ordering / a shared model), so the **full suite** is run, not just the touched app.

## Workflow

0. **Requirements-first gate (CLAUDE.md §24).** Confirm the feature maps to a REQ-ID in `.planning/REQUIREMENTS.md` (or the active `docs/in-progress/` spec). If not, stop and add the requirement first — do not retro-justify.
1. **Identify the change set.** `git diff --name-only origin/main...HEAD` (or the working tree). If starting from a description rather than a diff, locate the entry points with `semantic_search_nodes` / Grep.
2. **Compute impact radius (prefer the graph).** For each changed symbol/file, use the code-review-graph MCP tools:
   - `get_impact_radius` — blast radius (callers + dependents).
   - `get_affected_flows` — which end-to-end execution paths are touched.
   - `query_graph` (callers_of / callees_of / imports_of / tests_for) — fill gaps.
   - Fall back to `Grep` for usages if the graph is unavailable.
3. **Walk the layer checklist** (below) for **each affected app** — verify every layer that *should* change actually did, and that downstream consumers of a changed contract are updated.
4. **Test coverage.** Ensure tests are added/updated for the new behavior; **query-count tests** for any list/aggregate change (§6.9); **cross-tenant tests** for any scoping change. Use `query_graph` pattern=`tests_for` to find existing coverage; invoke the **`test-author`** subagent to fill gaps.
5. **Run regressions (REQUIRED, in order):**
   - `python manage.py makemigrations --check --dry-run` (no missing migrations).
   - Affected app(s): `.venv/bin/pytest apps/<app> -q -p no:warnings`.
   - **Full suite:** `DJANGO_SETTINGS_MODULE=config.settings.test .venv/bin/pytest apps/ -q -p no:warnings` — catches cross-module regressions the scoped run hides.
   - Frontend (if `frontend/` touched): the project's vitest/jest run.
6. **Delegate auditors** for the surfaces touched (Agent tool):
   - queries/models/serializers/migrations → **`orm-performance-auditor`**.
   - auth/permissions/scoping/Channels/Celery-user-data → **`tenant-security-auditor`**.
   - general backend conventions → **`code-reviewer`**.
7. **Report:** affected modules (with graph evidence), a per-layer ✅/❌ table of what's updated vs missing, the regression results, and any coverage/audit gaps. Do **not** call the feature done while ❌ rows or failing tests remain.

## Layer checklist (per affected app)

- [ ] **Model** — fields + `db_index` decisions + indexes for new query shapes (§6.8).
- [ ] **Migration** — created, reversible, schema vs data separated, `makemigrations --check` clean.
- [ ] **Service** — write-side logic, `@transaction.atomic` for multi-step, typed; no logic left in views/tasks.
- [ ] **Selector** — read-only, `select_related`/`prefetch_related`, no N+1.
- [ ] **View / Serializer / URL** — thin view → service/selector; explicit permissions; pagination + throttling; serializer validates only; route wired; OpenAPI schema updated (`drf-spectacular`).
- [ ] **Permission** — new/changed surface has an explicit permission + tenant scope.
- [ ] **Celery task** — thin wrapper, correct queue, idempotent (§12.4), IDs not instances.
- [ ] **Channels consumer** — only if real-time; §13.2 discipline + auth on connect.
- [ ] **Downstream consumers of a changed contract** — every caller/dependent from the impact radius updated (signatures, serializer fields, event payloads, settings names).
- [ ] **Tests** — unit + query-count + cross-tenant as applicable; full suite green.
- [ ] **Docs/requirements** — REQ traceability updated; any spec/CLAUDE.md section affected (e.g. §29 invariants) kept in sync.

## Notes
- This is the lighter, per-change cousin of the GSD phase flow; for a whole phase, `/gsd-execute-phase` + `/gsd-verify-work` already enforce most of this. Use this skill for ad-hoc feature work outside a GSD phase.
