---
phase: 27-sync-progress-reliability
verified: 2026-06-24T00:00:00Z
status: passed
score: 7/7 must-haves verified
overrides_applied: 0
---

# Phase 27: Sync Progress Reliability — Verification Report

**Phase Goal:** The initial-sync ProgressModal stays accurate and live without manual reopening, and the Finalising step is visible (fires when bulk completes, not on a fixed countdown).
**Verified:** 2026-06-24
**Status:** passed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Authenticated user who can see a shop's sync gets 200 + snapshot dict | ✓ VERIFIED | `SyncProgressSnapshotView.get()` in `apps/reviews/views.py:657-671`; calls `read_progress_snapshot`; test `test_sync_progress_returns_snapshot_for_owner_org` asserts 200 + dict |
| 2 | Endpoint returns 404 when no snapshot exists | ✓ VERIFIED | `views.py:668-669`: `if snapshot is None: return Response(status=HTTP_404_NOT_FOUND)`; test `test_sync_progress_returns_404_when_no_snapshot` passes |
| 3 | User from another org gets 404 for that shop's snapshot (cross-tenant denial) | ✓ VERIFIED | `_user_can_access_shop` checks `shop.organisation_id != user_org_id` → returns `False` → 404 (T-27-03 shape); test `test_sync_progress_cross_tenant_denied` asserts 403/404 |
| 4 | Staff user gets 404 for a shop outside their StaffAccessScope | ✓ VERIFIED | `views.py:701-715`: STAFF_ADMIN path checks SHOP scope then REGION scope; without either → `False` → 404; test `test_sync_progress_staff_out_of_scope_denied` passes |
| 5 | finalize_canonical_tags_task self-reschedules while reviews are PENDING/IN_PROGRESS (bounded) | ✓ VERIFIED | `finalise.py:86-116`: gate queries `Review.objects.filter(..., enrichment_status__in=[PENDING, IN_PROGRESS]).exists()`; re-dispatches at `countdown=countdown_seconds`, queue `tag-merge`, `attempt+1`; bounded by `FINALISE_GATE_MAX_ATTEMPTS` default 30; tests `test_gate_redispatches_while_reviews_pending` + `test_gate_redispatches_while_reviews_in_progress` pass |
| 6 | Once all reviews are terminal, finalise runs dedup/backfill/count-refresh and emits sync.complete | ✓ VERIFIED | `finalise.py:127`: `return _run_finalise(...)` when gate is not triggered; test `test_gate_proceeds_when_all_reviews_terminal` asserts `_refresh_review_counts` called and `"rescheduled"` absent from result |
| 7 | ProgressModal polls snapshot GET endpoint (~4s) alongside retained WebSocket, merges forward-only, stops on terminal/close | ✓ VERIFIED | `ProgressModal.tsx:201-224`: second `useEffect` with `POLL_MS=4000`; forward-only merge by `Date.parse(last_update_at)` guard; gated on `snapshotStatus !== "success"|"failed"`; `clearInterval` on cleanup; WebSocket `useEffect` at lines 80-193 is untouched; 10 Vitest tests cover all behaviours |

**Score:** 7/7 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `apps/reviews/views.py` | Org+shop-scoped GET snapshot view calling `read_progress_snapshot` | ✓ VERIFIED | `SyncProgressSnapshotView` at line 636; imports `read_progress_snapshot` at line 61 |
| `config/urls.py` | Versioned `/api/v1/reviews/sync-progress/<int:shop_id>/` route | ✓ VERIFIED | Registered at line 50 before the reviews router prefix; named `sync-progress-snapshot` |
| `config/settings/base.py` | `SYNC_PROGRESS_THROTTLE_RATE`, `FINALISE_GATE_COUNTDOWN_SECONDS`, `FINALISE_GATE_MAX_ATTEMPTS`; `sync_progress` in `DEFAULT_THROTTLE_RATES` | ✓ VERIFIED | All four present at lines 210-211 and 403 |
| `apps/reviews/services/finalise.py` | PENDING/IN_PROGRESS gate + bounded self-reschedule inside per-org lock | ✓ VERIFIED | Gate at lines 79-116 inside the `distributed_lock` context manager; returns `{"rescheduled": True}` on re-dispatch |
| `apps/reviews/services/sync.py` | Fixed `_finalise_countdown` heuristic removed; deferred-chord comment updated to D-04 | ✓ VERIFIED | No `_finalise_countdown =` assignment anywhere in file; comment at lines 745-751 documents self-reschedule as the chosen approach |
| `apps/reviews/tasks.py` | `finalize_canonical_tags_task` accepts `attempt: int = 1` kwarg, forwards to service | ✓ VERIFIED | Signature at line 246; passes `attempt=attempt` to `run_finalise_canonical_tags` at line 277 |
| `frontend/src/widgets/review-management/api.ts` | `fetchSyncProgress(shopId)` calling `/api/v1/reviews/sync-progress/{shopId}/` | ✓ VERIFIED | Lines 136-144; 404 → `null`; other errors → `handle()` |
| `frontend/src/widgets/review-management/ProgressModal.tsx` | Poll-fallback `useEffect` with forward-only merge alongside WebSocket | ✓ VERIFIED | Lines 196-224; `POLL_MS=4000`; WS effect at lines 80-193 unchanged |
| `frontend/src/widgets/review-management/ProgressModal.test.tsx` | 10 Vitest tests covering all poll behaviours | ✓ VERIFIED | 301-line file with 10 `it()` cases across 6 `describe` blocks |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `apps/reviews/views.py (SyncProgressSnapshotView)` | `apps/reviews/services/progress.py::read_progress_snapshot` | direct import + call | ✓ WIRED | `from apps.reviews.services.progress import read_progress_snapshot` at line 61; called at `views.py:667` |
| `apps/reviews/services/finalise.py (gate)` | `apps/reviews/tasks.py::finalize_canonical_tags_task` | lazy import + `apply_async` on `tag-merge` queue | ✓ WIRED | Lazy import at `finalise.py:105`; `apply_async` at lines 107-115 with `queue="tag-merge"`, `countdown=countdown_seconds`, `attempt+1` |
| `ProgressModal.tsx (poll effect)` | `GET /api/v1/reviews/sync-progress/{shopId}/` | `fetchSyncProgress` on 4s interval | ✓ WIRED | `fetchSyncProgress` imported at `ProgressModal.tsx:4`; called inside `setInterval` at line 208 |
| `ProgressModal poll merge` | `snapshot.last_update_at` | `Date.parse` comparison | ✓ WIRED | Lines 212-213: stale-or-equal poll is ignored; `return poll` only when strictly newer |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| SYNC-REL-01 | 27-01, 27-02 | ProgressModal stays current via org-scoped GET endpoint + frontend polling fallback merging with WebSocket | ✓ SATISFIED | Backend endpoint live at `/api/v1/reviews/sync-progress/<shop_id>/`; frontend poll effect in `ProgressModal.tsx`; 6 backend + 10 frontend tests |
| SYNC-REL-02 | 27-01 | `finalize_canonical_tags_task` is completion-gated; fires when bulk enrichment completes, not on fixed countdown | ✓ SATISFIED | Bounded self-reschedule gate in `finalise.py`; fixed `_finalise_countdown` heuristic removed from `sync.py`; 5 gate tests pass |

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| — | — | — | — | No debt markers (TBD/FIXME/XXX), no stub returns, no empty handlers found in phase-modified files |

Checked all 8 modified files for `TBD`, `FIXME`, `XXX`, `return null`, `return {}`, `return []`, placeholder comments. None found.

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| `_finalise_countdown` heuristic absent | `grep -n "_finalise_countdown" apps/reviews/services/sync.py` | Only appears in comment (line 745) as "has been REMOVED" — no assignment | ✓ PASS |
| Gate lives inside per-org lock | `finalise.py:70-116` structure | `with distributed_lock(...) as acquired:` wraps the gate at lines 79-116 | ✓ PASS |
| `sync_progress` throttle scope wired to rate | `config/settings/base.py:403` | `"sync_progress": SYNC_PROGRESS_THROTTLE_RATE` present in `DEFAULT_THROTTLE_RATES` | ✓ PASS |
| WebSocket effect not removed | `ProgressModal.tsx:80-193` | `new WebSocket(buildWsUrl(shopId))` at line 82; independent `useEffect` block | ✓ PASS |
| No new WebSocket consumer | `grep -r "class.*Consumer" apps/` | Only `SyncProgressConsumer` (pre-existing) in `apps/reviews/consumers.py` | ✓ PASS |

---

### Human Verification Required

None. All requirements can be verified programmatically from the codebase. Manual UAT (confirm modal self-heals on a dropped WS event in a live sync) is recommended but not a gate condition — the test coverage is comprehensive and the orchestrator confirmed the full backend suite and `tsc --noEmit` both passed.

---

### Gaps Summary

No gaps. All 7 must-have truths are VERIFIED, all artifacts are substantive and wired, both requirement IDs (SYNC-REL-01, SYNC-REL-02) are satisfied. The phase goal is achieved:

- The ProgressModal now has a 4s poll fallback alongside the WebSocket, merging forward-only by `last_update_at`, stopping on terminal state and close — so a dropped WS event no longer freezes the modal.
- `finalize_canonical_tags_task` is completion-gated with a bounded self-reschedule (default cap: 30 attempts at 20s each), replacing the fixed `max(300, min(1200, ...))` countdown heuristic.
- Cross-tenant and Staff-scope access controls mirror `SyncProgressConsumer._user_can_access_shop` exactly (§13.4).
- No new WebSocket consumer added (§13.2).

---

_Verified: 2026-06-24T00:00:00Z_
_Verifier: Claude (gsd-verifier)_
