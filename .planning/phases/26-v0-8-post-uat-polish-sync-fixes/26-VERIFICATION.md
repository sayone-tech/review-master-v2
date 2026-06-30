---
phase: 26-v0-8-post-uat-polish-sync-fixes
verified: 2026-06-24T00:00:00Z
status: human_needed
score: 4/4 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Visit /admin/org/tags/ and type a partial label (e.g. 'food') in the search box; wait 300ms debounce"
    expected: "The tag list refreshes showing only tags whose label contains the typed substring; the 'Tags (N)' header count stays bound to the total count and 'Showing X–Y of N · Rows: N' footer updates"
    why_human: "Server-side search + debounce UX correctness, pagination footer arithmetic, and visual header count rendering cannot be verified by grep or TypeScript compilation alone"
  - test: "Trigger an initial sync for a store, then while it is in the 'Fetching Reviews' step, let an incremental sync fire (or call fetch_and_persist_reviews with trigger='incremental' in a shell)"
    expected: "The progress modal's fetched counter does NOT reset; the incremental sync completes silently with no modal change"
    why_human: "Race condition / concurrency behaviour between two in-flight Celery tasks cannot be verified statically; requires observing the running system"
  - test: "Complete a full initial sync for a store. Observe the completed ProgressModal."
    expected: "Step 1 label reads 'Fetching from Google' (not 'Fetched from Google'). When step 1 completes, it shows e.g. '120 reviews fetched · 5m 12s'. When the vocab step completes, it shows e.g. 'Building Tag Vocabulary · 1m 42s'. No 'NaN' or negative durations appear."
    why_human: "Real snapshot timing fields only populated during a live sync; requires end-to-end sync completion to verify the per-stage duration display"
  - test: "In Django admin (or via psql), check the PeriodicTask named 'enqueue_incremental_syncs' after running the migration"
    expected: "crontab is '0 */6 * * *' with timezone UTC; enabled=True"
    why_human: "Beat schedule state is in a django_celery_beat DB table; cannot be read without running migrations against a live DB — static file inspection alone is insufficient for the runtime state"
---

# Phase 26: v0.8 Post-UAT Polish & Sync Fixes Verification Report

**Phase Goal:** Close the small UX gaps and the one sync-progress defect surfaced while UAT-testing Phases 22–25 — Tags page search filter + header count + "Showing X–Y of N" footer; sync progress "Fetching from Google" label + per-stage completion timing; and the SEED-06 fix so an incremental sync can't reset an in-progress initial-sync modal.
**Verified:** 2026-06-24
**Status:** human_needed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | D-01 (TMGT-07): `list_canonical_tags_for_org` + `OrgCanonicalTagViewSet` apply an org-scoped `label__icontains` search; query-count ceiling ≤2 preserved; frontend widget has debounced search hitting `?search=` | ✓ VERIFIED | See below |
| 2 | D-02 (TMGT-08): tag-management widget shows "Tags (N)" header count + "Showing X–Y of N · Rows: N" footer with rows selector + page controls | ✓ VERIFIED | See below |
| 3 | D-03/D-04 (SEED-05): step-1 label reads "Fetching from Google"; per-stage durations render from snapshot timing fields (`fetch_duration_seconds`, `vocab_duration_seconds`) | ✓ VERIFIED | See below |
| 4 | D-05/D-06 (SEED-06): ALL progress writes/clears/emits in `fetch_and_persist_reviews` gated on `trigger == "initial"`; incremental emits nothing (regression test asserts 0 clear calls, no "fetching" snapshot write); Beat migration sets `0 */6 * * *` UTC + `enabled=True` | ✓ VERIFIED | See below |

**Score:** 4/4 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `apps/reviews/selectors/canonical_tags.py` | search-aware `list_canonical_tags_for_org` with `label__icontains` | ✓ VERIFIED | `search: str = ""` arg at line 52; `if search: qs = qs.filter(label__icontains=search)` at lines 67–68; org-scope filter unconditional |
| `apps/reviews/views.py` | `OrgCanonicalTagViewSet.get_queryset` passing `search` from query params | ✓ VERIFIED | Line 488: `search=self.request.query_params.get("search", "")` passed to selector |
| `apps/reviews/services/sync.py` | trigger-gated progress writes + per-step timing fields | ✓ VERIFIED | 4 gate sites confirmed: lines 310, 337, 466, 562; timing fields `fetch_started_at`/`fetch_duration_seconds` at lines 323, 477, 521–522; `vocab_started_at`/`vocab_duration_seconds`/`enriching_started_at` at lines 664, 709–710, 718–719 |
| `apps/reviews/migrations/0015_beat_incremental_6h.py` | 6-hourly + re-enabled Beat schedule | ✓ VERIFIED | `get_or_create(minute="0", hour="*/6", ... timezone="UTC")`; `update_or_create(name="enqueue_incremental_syncs", defaults={..., "enabled": True})`; `dependencies = [("reviews", "0014_tagmergejob")]`; named `reverse_code` (not noop) |
| `apps/reviews/tests/test_selectors.py` | query-count tests + search isolation tests | ✓ VERIFIED | 6 canonical-tag tests: search_returns_matching_label, case_insensitive, cross_org_isolation, empty_search_returns_all, query_count_without_search (≤2), query_count_with_search (≤2) |
| `apps/reviews/tests/test_services.py` | SEED-06 regression tests | ✓ VERIFIED | 3 tests: incremental_does_not_write_fetching_snapshot (asserts `mock_clear.call_count == 0` and no status="fetching" write), initial_writes_progress, initial_snapshot_has_timing_fields |
| `frontend/src/widgets/tag-management/types.ts` | `search?: string` in `FetchTagsParams` | ✓ VERIFIED | Line 36: `search?: string` |
| `frontend/src/widgets/tag-management/api.ts` | `fetchTags` appends `?search=` when set | ✓ VERIFIED | Line 39: `if (params.search) qs.set("search", params.search);` |
| `frontend/src/widgets/tag-management/useTagList.ts` | search state + `setSearch` resetting page to 1 | ✓ VERIFIED | Lines 24, 40–43: `const [search, setSearchState] = useState("")`; `setSearch` sets state and `setPage(1)`; `search` passed to `fetchTags` in `useCallback` deps |
| `frontend/src/widgets/tag-management/TagManagementWidget.tsx` | debounced search input + "Tags (N)" header + "Showing X–Y of N · Rows: N" footer | ✓ VERIFIED | `buildPageRange` helper at lines 16–21; `data-testid="tag-search"` input at line 114; 300ms debounce via `useEffect` + `useRef` (lines 50–57); header count at lines 93–96; Showing footer at lines 139–143; rows selector `[10, 25, 50, 100]` at line 154 |
| `frontend/src/widgets/review-management/ProgressModal.tsx` | "Fetching from Google" step-1 labels + `formatDuration` + per-stage timing display | ✓ VERIFIED | 3 `<label>` occurrences all read "Fetching from Google" (lines 351, 363, 387); `formatDuration` helper at lines 33–38; `fetch_duration_seconds` display at lines 367–370; `vocab_duration_seconds` display at lines 446–448 |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `OrgCanonicalTagViewSet.get_queryset` | `list_canonical_tags_for_org` | `search=self.request.query_params.get("search", "")` | ✓ WIRED | views.py line 486–489 |
| `TagManagementWidget.tsx` | `useTagList.ts setSearch` | 300ms debounce `useEffect` → `setSearch(searchInput)` | ✓ WIRED | lines 50–57 |
| `api.ts fetchTags` | `OrgCanonicalTagViewSet ?search=` | `qs.set("search", params.search)` | ✓ WIRED | api.ts line 39 |
| `fetch_and_persist_reviews` | `write_progress_snapshot`/`clear_progress_snapshot` | `if trigger == "initial":` at 4 sites | ✓ WIRED | sync.py lines 310, 337, 466, 562 |
| `ProgressModal.tsx` | snapshot timing fields | `snapshot?.fetch_duration_seconds` / `snapshot?.vocab_duration_seconds` | ✓ WIRED | ProgressModal.tsx lines 367, 446 |

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|--------------|--------|--------------------|--------|
| `TagManagementWidget.tsx` | `count` / `rows` | `useTagList` → `fetchTags` → `/api/v1/reviews/canonical-tags/?search=` → `OrgCanonicalTagViewSet` → `list_canonical_tags_for_org` | Yes — DB query against `OrgCanonicalTag` filtered by `organisation_id` and optionally `label__icontains` | ✓ FLOWING |
| `ProgressModal.tsx` timing display | `snapshot.fetch_duration_seconds` | WebSocket snapshot written by `fetch_and_persist_reviews` from real monotonic wall-clock | Yes — computed from `round(duration, 1)` where `duration = (dj_timezone.now() - started_at).total_seconds()` | ✓ FLOWING |
| `ProgressModal.tsx` timing display | `snapshot.vocab_duration_seconds` | WebSocket snapshot written by `run_initial_backfill` using `_time.monotonic()` | Yes — computed at sync.py line 709 | ✓ FLOWING |

---

### Behavioral Spot-Checks

Step 7b: SKIPPED (frontend requires a running browser + server; Django tests are confirmed passing at orchestrator level; no runnable CLI check feasible for these artifacts without starting services).

---

### Probe Execution

Step 7c: No probe scripts declared in PLAN files. No `scripts/*/tests/probe-*.sh` files applicable to this phase. SKIPPED.

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|---------|
| TMGT-07 | 26-01, 26-02 | Tags page label search filter (server-side, debounced) | ✓ SATISFIED | Selector `label__icontains`, viewset wiring, frontend debounced input all verified |
| TMGT-08 | 26-02 | Tags page "Tags (N)" header + "Showing X–Y of N · Rows: N" footer | ✓ SATISFIED | `TagManagementWidget.tsx` header count and Showing footer verified |
| SEED-05 | 26-01, 26-02 | "Fetching from Google" label + per-stage completion timing | ✓ SATISFIED | All 3 `<label>` elements say "Fetching from Google"; timing fields in snapshot and ProgressModal display wired |
| SEED-06 | 26-01 | Incremental sync must not clobber initial-sync progress modal | ✓ SATISFIED | 4 trigger-gate sites in `fetch_and_persist_reviews`; regression test confirms 0 clears and no "fetching" snapshot on incremental; Beat migration re-enabled at 6h |

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `frontend/src/widgets/review-management/ProgressModal.tsx` | 404 | `aria-label` reads `"Fetched from Google: ${fetchPct}%"` | ℹ️ Info | This is an `aria-label` on a `<div role="progressbar">` describing the percentage complete state for screen readers — NOT a visible `<label>` element. D-03 required changing visible step-1 `<label>` text, which was done. The plan acceptance criteria (`grep -c "Fetched from Google" ... returns 0 in <label> text`) is met. The SUMMARY flagged this and judged it acceptable; the aria-label serves accessibility semantics distinct from the step label. Acceptable as-is. |

No `TBD`, `FIXME`, or `XXX` markers found in phase-modified files. No stubs or empty implementations detected.

---

### Human Verification Required

#### 1. Tag Search Box — Server-side filtering UX

**Test:** Visit `/admin/org/tags/` as an Org Admin, type a partial label substring (e.g. "food") in the search box, and wait approximately 300ms.
**Expected:** The tag list refreshes server-side, showing only tags whose label contains the typed string (case-insensitive). The "Tags (N)" count reflects the unfiltered total. "Showing X–Y of N" reflects the filtered result count. Clearing the search restores the full list.
**Why human:** Debounce timing, server round-trip, and filtered rendering are only observable in a running browser.

#### 2. SEED-06 Concurrency — Incremental cannot clobber in-progress modal

**Test:** Trigger an initial sync for a store. While it is in the "Fetching Reviews" step (step 1), simulate or observe an incremental sync firing (e.g. by calling `fetch_and_persist_reviews(shop_id=…, trigger="incremental")` in a Django shell in a separate process).
**Expected:** The ProgressModal's fetched counter does NOT reset to 0 or change. The incremental sync completes silently without touching the modal.
**Why human:** Verifying concurrent task non-interference requires a live Celery worker environment — static analysis cannot simulate the race.

#### 3. Per-stage Timing Display in ProgressModal

**Test:** Complete a full initial sync for a store and observe the ProgressModal at each stage transition.
**Expected:** (a) Step 1 label reads "Fetching from Google" in all three states (pending/active/complete). (b) When step 1 completes, it shows "N reviews fetched · Xm Ys" where the duration is non-zero and plausible. (c) When the vocab step completes, it shows "· Xm Ys" appended to the step summary. (d) No "NaN", negative, or zero durations when the steps did take time.
**Why human:** Requires a live sync that progresses through all four steps; snapshot timing fields are only non-null in a real enrichment run.

#### 4. Beat Schedule — `enqueue_incremental_syncs` at 6h

**Test:** After running `python manage.py migrate reviews 0015`, check the `PeriodicTask` row named "enqueue_incremental_syncs" in Django admin or via `PeriodicTask.objects.get(name="enqueue_incremental_syncs")` in a shell.
**Expected:** `crontab.hour == "*/6"`, `crontab.minute == "0"`, `crontab.timezone == "UTC"`, `enabled == True`.
**Why human:** The migration targets django_celery_beat DB tables; correct state only verifiable against a live DB with migrations applied.

---

### Gaps Summary

No gaps identified. All 4 must-haves are verified at the code level. The `aria-label` residual "Fetched from Google" (ProgressModal line 404) is an accessibility attribute on a progressbar div, not a visible step label — consistent with the plan's acceptance criteria and the SUMMARY's documented rationale. The 4 human verification items are standard runtime checks that pass static analysis but require a running system to confirm end-to-end behaviour.

---

_Verified: 2026-06-24_
_Verifier: Claude (gsd-verifier)_
