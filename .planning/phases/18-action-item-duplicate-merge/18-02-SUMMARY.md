---
phase: 18-action-item-duplicate-merge
plan: 02
subsystem: action_items
tags: [service, selector, serializer, view, api, duplicate-merge]
dependency_graph:
  requires:
    - "ActionItem.canonical self-FK (plan 18-01)"
  provides:
    - "merge_action_items() service"
    - "Read-only guards on transition_status / assign_action_item / add_note for merged duplicates"
    - "list_action_items() hides duplicates + annotates duplicate_count"
    - "ActionItemDuplicateSerializer + MergeSerializer + extended list/detail serializers"
    - "POST /api/v1/action-items/merge/ endpoint (Org Admin only)"
    - "D-17 guards on PATCH and transition-status for merged duplicates"
  affects:
    - apps/action_items/services/lifecycle.py
    - apps/action_items/selectors/items.py
    - apps/action_items/serializers.py
    - apps/action_items/views.py
    - apps/action_items/tests/test_services.py
    - apps/action_items/tests/test_selectors.py
    - apps/action_items/tests/test_views.py
tech_stack:
  added: []
  patterns:
    - "select_for_update with ascending PK ordering for multi-row deadlock-free locking"
    - "Re-parent sub-duplicates before bulk update to keep canonical chains flat (depth = 1)"
    - "Filter-then-annotate ordering so Count('duplicates') excludes already-merged rows"
    - "View-layer try/except mapping django ValidationError -> DRF ValidationError -> HTTP 400"
    - "get_permissions() override on a single ViewSet @action for per-action permissions"
    - "Prefetch on retrieve only (not list) — duplicate_count satisfies the list payload"
key_files:
  created: []
  modified:
    - apps/action_items/services/lifecycle.py
    - apps/action_items/selectors/items.py
    - apps/action_items/serializers.py
    - apps/action_items/views.py
    - apps/action_items/tests/test_services.py
    - apps/action_items/tests/test_selectors.py
    - apps/action_items/tests/test_views.py
decisions:
  - "Multi-row lock uses sorted PK order and filter(pk__in=all_ids, organisation_id=...) — one query validates IDOR ownership AND acquires all locks atomically"
  - "Re-parented sub-duplicates of selected duplicate_ids onto primary BEFORE marking selected duplicates — guarantees canonical chains stay at depth 1 and there is no transient inconsistent state visible to a parallel reader"
  - "View layer catches django.core.exceptions.ValidationError from service and re-raises as rest_framework.exceptions.ValidationError so it maps to HTTP 400 (the project has no global DRF exception handler that does this automatically)"
  - "Detail-route Prefetch on duplicates uses select_related('shop','source_review') so the nested ActionItemDuplicateSerializer is N+1-free even with many duplicates"
  - "MergeSerializer validates 'primary in duplicates' and 'unique duplicate_ids' at the serializer layer; service layer re-validates as defence-in-depth"
  - "PATCH on a merged duplicate may legitimately be 400 (guard fires) or 404 (selector hides duplicates from the queryset). The view test asserts (400, 404) to allow either implementation"
metrics:
  duration: "~25 minutes"
  completed: "2026-05-22"
  tasks_completed: 2
  files_modified: 7
requirements_completed:
  - D-03
  - D-05
  - D-06
  - D-07
  - D-08
  - D-09
  - D-10
  - D-11
  - D-12
  - D-14
  - D-15
  - D-16
  - D-17
---

# Phase 18 Plan 02: Backend Merge — Service, Selectors, Serializers, API Summary

Shipped the complete backend surface for duplicate merge: `merge_action_items()` service with full validation + atomic re-parenting, read-only guards on the three lifecycle mutators, list/detail selector and serializer extensions, and the `POST /api/v1/action-items/merge/` endpoint restricted to Org Admin. The wave-3 frontend plans now have a stable contract to bind against.

## What Was Built

### Service layer — `apps/action_items/services/lifecycle.py`

- **`merge_action_items(*, primary_id, duplicate_ids, actor, organisation_id) -> ActionItem`** — atomic, deadlock-safe merge implementation. Locks the primary plus all duplicates in ascending PK order via a single `select_for_update().filter(pk__in=sorted_ids, organisation_id=...)` query (IDOR-safe). Validates D-05 (same scope), D-06 (source=AI for all), D-08 (primary has no canonical). Re-parents sub-duplicates of the selected duplicates onto the primary FIRST (D-09 — keeps chain depth at 1), then bulk-updates `canonical_id` on the selected duplicates. Writes one `action_item.merged` AuditLog row with `after_data={"merged_ids": [...]}`. Returns the primary with `Prefetch('duplicates', queryset=...select_related('shop','source_review'))` already attached.
- **Read-only guards (D-03)** — added `if action_item.canonical_id is not None: raise ValidationError("Cannot modify a merged duplicate.")` at the top of `transition_status`, `assign_action_item`, and `add_note`. The guards fire BEFORE the `select_for_update` so a merged duplicate cannot be mutated even if the row exists.

### Selector — `apps/action_items/selectors/items.py`

- Added `Count` import and applied `qs.filter(canonical__isnull=True).annotate(duplicate_count=Count("duplicates"))` AFTER the role filter (Staff scope still wins) and BEFORE `order_by`. The filter-then-annotate ordering ensures Count only includes duplicates pointing AT the visible primaries, never the hidden duplicates themselves.
- `get_action_item()` is unchanged — the retrieve-time Prefetch for `duplicates` lives in `views.py` `get_queryset()` so the list selector stays narrow.

### Serializers — `apps/action_items/serializers.py`

- **`ActionItemDuplicateSerializer`** — slim payload for nested duplicates in the detail response: `id`, `title`, `shop_name` (from prefetched shop), `source_review_date` (`review_create_time.isoformat()`), `source_review_rating` (`star_rating`). All read-only.
- **`ActionItemListSerializer.duplicate_count`** — exposed as `IntegerField(read_only=True)` driven by the selector annotation.
- **`ActionItemReadSerializer.duplicates`** — nested `ActionItemDuplicateSerializer(many=True, read_only=True)` driven by the retrieve-time Prefetch.
- **`MergeSerializer`** — `primary_id: IntegerField`, `duplicate_ids: ListField(child=IntegerField, min_length=1)`, cross-field `validate()` that rejects primary in duplicate list and rejects duplicate ids in the list.

### Views — `apps/action_items/views.py`

- **`get_permissions()`** — returns `[IsOrgAdmin(), IsOrgScoped()]` when `self.action == "merge_action"`, otherwise the existing `[IsOrgScoped(), BrandScopeGuard()]`. Staff is rejected with HTTP 403 (D-16).
- **`get_queryset()` retrieve branch** — extended to `prefetch_related("notes__author", Prefetch("duplicates", queryset=ActionItem.objects.select_related("shop","source_review")))`.
- **`perform_update()` guard (D-17)** — raises `rest_framework.exceptions.ValidationError("Cannot modify a merged duplicate.")` when `serializer.instance.canonical_id is not None`. Maps to HTTP 400.
- **`transition_status_action` / `add_note_action`** — wrapped service calls in `try / except DjangoValidationError` and re-raise as DRF ValidationError so the service's D-03 guard surfaces as HTTP 400 rather than HTTP 500.
- **`merge_action` (`@action(detail=False, methods=["post"], url_path="merge")`)** — validates with `MergeSerializer`, calls `merge_action_items()`, catches `DjangoValidationError` -> HTTP 400, returns `ActionItemReadSerializer(primary).data` with 200 (D-16).

### Tests

- **`test_services.py` — +11 tests:** D-03 guards on the three mutators; merge happy path; sub-duplicate re-parenting (D-09); cross-scope rejection (D-05); manual-source rejection (D-06); already-merged primary rejection (D-08); empty `duplicate_ids`; primary in duplicate list; cross-org IDOR rejection.
- **`test_selectors.py` — +3 tests:** `test_list_hides_merged_duplicates` (D-10), `test_list_annotates_duplicate_count` (D-11), `test_list_query_count_with_duplicates` (5 primaries × 2 duplicates, ≤6 queries — no N+1).
- **`test_views.py` — +7 tests:** OrgAdmin can merge (200); Staff is forbidden (403, D-16); missing duplicate_ids returns 400; PATCH on merged duplicate returns 400/404 (D-17); transition-status on merged duplicate returns 400/404 (D-17); list serializer exposes `duplicate_count`; detail serializer exposes nested `duplicates`.

## Deviations from Plan

- **View-layer exception conversion was required, not optional.** The plan's `<action>` block assumed the project had a DRF exception handler converting `django.core.exceptions.ValidationError` to HTTP 400 automatically. Verified via `grep` that no custom handler exists. Applied **Rule 3 (auto-fix blocking issue)**: wrapped `transition_status_action`, `add_note_action`, and `merge_action` in `try/except DjangoValidationError` and re-raised as DRF `ValidationError`. Without this, the D-17 guard would have surfaced as HTTP 500. Tracked here for transparency; the test suite verifies the resulting 400 behavior.
- **Added `test_merge_rejects_cross_org_items`** — not in the plan's enumerated list, but the threat register (T-18-02-02 IDOR) calls this out explicitly. Added one extra test asserting that an action item from another organisation cannot be merged in by an actor who knows its ID. **Rule 2 (auto-add missing critical functionality)** for the IDOR mitigation's verifiability.

No architectural changes required.

## Tasks Completed

| Task | Name | Commit |
| ---- | ---- | ------ |
| 1 | Service — `merge_action_items()` + read-only guards + tests | `1db1f5b` |
| 2 | Selector + serializers + views + selector/view tests | `781902a` |

## Verification

- `uv run pytest apps/action_items/` → **80 passed, 1 skipped** (the skipped test predates this plan)
- New service tests: 11 — all pass
- New selector tests: 3 — all pass
- New view tests: 7 — all pass
- Pre-commit hooks (ruff-check, ruff-format, django-upgrade, mypy, bandit, missing-migrations) passed on both commits.

## Contract for Wave-3 Frontend

- `GET /api/v1/action-items/` rows include `duplicate_count: int` (0 when none).
- `GET /api/v1/action-items/{id}/` includes `duplicates: ActionItemDuplicate[]` where each entry has `{id, title, shop_name, source_review_date, source_review_rating}`.
- `POST /api/v1/action-items/merge/` accepts `{primary_id: int, duplicate_ids: int[]}`; returns the primary serialized via `ActionItemReadSerializer` (200) or 400/403 on failure.
- `PATCH /api/v1/action-items/{id}/` and `POST /api/v1/action-items/{id}/transition-status/` return 400 (or 404 via selector hiding) when the target is a merged duplicate.

## Self-Check: PASSED

- All claimed files exist and contain the claimed additions.
- Commits `1db1f5b` and `781902a` exist on the worktree branch.
- 80 tests pass; no regressions in pre-existing action_items tests.
