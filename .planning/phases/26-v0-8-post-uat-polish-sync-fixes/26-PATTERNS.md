# Phase 26: v0.8 Post-UAT Polish & Sync Fixes — Pattern Map

**Mapped:** 2026-06-24
**Files analyzed:** 9 new/modified files
**Analogs found:** 9 / 9

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `frontend/src/widgets/tag-management/useTagList.ts` | hook | request-response | `frontend/src/widgets/team-management/useTeam.ts` | exact |
| `frontend/src/widgets/tag-management/api.ts` | utility | request-response | `frontend/src/widgets/team-management/api.ts` | exact |
| `frontend/src/widgets/tag-management/TagManagementWidget.tsx` | component | request-response | `frontend/src/widgets/team-management/TeamTable.tsx` | exact |
| `frontend/src/widgets/review-management/ProgressModal.tsx` | component | event-driven | self (existing, surgical edit only) | self |
| `apps/reviews/selectors/canonical_tags.py` | selector | request-response | `apps/accounts/selectors/team.py` | exact |
| `apps/reviews/views.py` `OrgCanonicalTagViewSet` | controller | request-response | `apps/accounts/views.py` `TeamViewSet` | exact |
| `apps/reviews/services/sync.py` `fetch_and_persist_reviews` | service | event-driven | `apps/reviews/services/enrichment.py` `_emit_enrichment_progress` | role-match |
| `apps/reviews/services/progress.py` | service | event-driven | `apps/reviews/services/finalise.py` | role-match |
| `apps/reviews/migrations/0015_beat_incremental_6h.py` (new) | migration | batch | `apps/reviews/migrations/0002_periodic_tasks_seed.py` + `0013_periodic_task_seed_polarity_reclassify.py` | exact |

---

## Pattern Assignments

### TMGT-07 — `apps/reviews/selectors/canonical_tags.py` `list_canonical_tags_for_org` (selector, CRUD)

**Analog:** `apps/accounts/selectors/team.py` `list_team_members` (lines 8–48)

**Why closest:** Both are org-scoped list selectors backing a paginated DRF viewset list action. The team selector already has the `search` + `icontains` pattern to copy verbatim.

**Search filter pattern to add** (copy from `apps/accounts/selectors/team.py` lines 39–40):
```python
if search:
    qs = qs.filter(Q(full_name__icontains=search) | Q(email__icontains=search))
```
Adapt for tags:
```python
if search:
    qs = qs.filter(label__icontains=search)
```
No `Q` import needed (single field). Keep the rest of `list_canonical_tags_for_org` unchanged — org-scope filter and `order_by` are already correct. The `search: str = ""` keyword arg matches the team selector signature.

**Updated selector signature to copy:**
```python
def list_canonical_tags_for_org(
    *,
    organisation_id: int,
    search: str = "",
) -> QuerySet[OrgCanonicalTag]:
    qs = OrgCanonicalTag.objects.filter(organisation_id=organisation_id)
    if search:
        qs = qs.filter(label__icontains=search)
    return qs.order_by("-review_count", "label")
```

---

### TMGT-07 — `apps/reviews/views.py` `OrgCanonicalTagViewSet.get_queryset` (controller, request-response)

**Analog:** `apps/accounts/views.py` `TeamViewSet.get_queryset` (lines 96–109)

**Why closest:** `TeamViewSet.get_queryset` reads `search` from `query_params` and passes it to its selector — exactly the pattern `OrgCanonicalTagViewSet` must adopt. No FilterSet class needed: the team viewset uses manual `query_params.get` plus the selector handles the filter, which is simpler and query-count-safe.

**Core pattern** (`apps/accounts/views.py` lines 96–109):
```python
def get_queryset(self) -> Any:
    org_id = getattr(self.request.user, "organisation_id", None)
    if org_id is None:
        return User.objects.none()
    return list_team_members(
        organisation_id=org_id,
        search=self.request.query_params.get("search", ""),
        region_id=region_id,
        shop_id=shop_id,
    )
```
Adapt for `OrgCanonicalTagViewSet`:
```python
def get_queryset(self) -> QuerySet[OrgCanonicalTag]:
    org_id = getattr(self.request.user, "organisation_id", None)
    if org_id is None:
        return OrgCanonicalTag.objects.none()
    return list_canonical_tags_for_org(
        organisation_id=org_id,
        search=self.request.query_params.get("search", ""),
    )
```
No other change to the viewset. The `OrderingFilter` backend already present continues to handle `?ordering=`.

**Query-count ceiling:** The existing ceiling is 1 COUNT + 1 SELECT = ≤2 queries. Adding `label__icontains` on the same queryset uses the existing `orgcanon_org_count_idx` via the `organisation_id` filter and a btree scan on `label` — no extra query. Extend the existing query-count test to pass `?search=foo` and assert the count stays ≤2.

---

### TMGT-07/TMGT-08 — `frontend/src/widgets/tag-management/useTagList.ts` (hook, request-response)

**Analog:** `frontend/src/widgets/team-management/useTeam.ts` (lines 1–81)

**Why closest:** `useTeam` is the exact pattern — manages filter state, debounces search, calls the API, holds `count` for header + pagination. `useTagList` already has `count`, `page`, `pageSize`, and pagination helpers but lacks `search` state + `setSearch`.

**Search state pattern to add** (copy from `useTeam.ts` lines 32–36):
```typescript
const setSearch = (search: string) => {
  const next = { ...filters, search, page: 1 };
  setFilters(next);
  void refresh(next);
};
```
`useTagList` uses a different internal structure (individual `useState` per param, no `filters` object). Adapt by adding:
```typescript
const [search, setSearchState] = useState("");

const setSearch = (s: string) => {
  setSearchState(s);
  setPage(1);
};
```
Then pass `search` to `fetchTags` in the `load` callback. The `count` field is already returned and stored; no change needed there.

---

### TMGT-07/TMGT-08 — `frontend/src/widgets/tag-management/api.ts` `fetchTags` (utility, request-response)

**Analog:** `frontend/src/widgets/team-management/api.ts` `buildQs` + `listTeam` (lines 41–58)

**Why closest:** `buildQs` in team/api.ts is the verbatim pattern for adding a `search` query param to the URL serialization.

**Search param pattern** (`team/api.ts` lines 41–50):
```typescript
function buildQs(params: TeamFilterParams): string {
  const u = new URLSearchParams();
  if (params.search) u.set("search", params.search);
  if (params.page) u.set("page", String(params.page));
  if (params.page_size) u.set("page_size", String(params.page_size));
  const qs = u.toString();
  return qs ? `?${qs}` : "";
}
```
`tag-management/api.ts` `fetchTags` already uses `URLSearchParams` inline. Add `if (params.search) qs.set("search", params.search);` inside the existing block. Also add `search?: string` to `FetchTagsParams` in `types.ts`.

---

### TMGT-08 — `frontend/src/widgets/tag-management/TagManagementWidget.tsx` (component, request-response)

**Analog:** `frontend/src/widgets/team-management/TeamTable.tsx` (full file)

**Why closest:** `TeamTableWidget` is the complete reference for both the search input + debounce pattern (lines 42–54) and the "Showing X–Y of N · Rows: N" pagination footer (lines 271–337). `TagManagementWidget` already has a pagination nav but uses "Page X of Y" — the team widget shows the richer "Showing X–Y of N" format with the Rows selector and numbered page buttons.

**Search input + debounce pattern** (`TeamTable.tsx` lines 42–54):
```typescript
const [searchInput, setSearchInput] = useState(filters.search ?? "");
const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

useEffect(() => {
  if (debounceRef.current) clearTimeout(debounceRef.current);
  debounceRef.current = setTimeout(() => setSearch(searchInput), 300);
  return () => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
  };
  // eslint-disable-next-line react-hooks/exhaustive-deps
}, [searchInput]);
```
Debounce interval: 300ms (matching team page, within the 250–300ms discretion range).

**Search input JSX** (`TeamTable.tsx` lines 220–227):
```tsx
<input
  type="search"
  placeholder="Search tags…"
  value={searchInput}
  onChange={(e) => setSearchInput(e.target.value)}
  className={`${inputCls} flex-1 min-w-[200px]`}
  data-testid="tag-search"
/>
```

**Header count "Tags (N)"** — copy from `templates/team/team_list.html` lines 7–9 (template) and `TagManagementWidget.tsx` line 63 (component). The template approach:
```html
<h1 class="text-[20px] font-semibold text-ink">
  Tags
  <span class="text-muted font-normal text-[14px] ml-1">({{ count }})</span>
</h1>
```
In the React widget (no SSR context), drive it from `useTagList`'s `count`:
```tsx
<h1 className="text-[20px] font-semibold text-ink">
  Tags
  <span className="text-muted font-normal text-[14px] ml-1">({count})</span>
</h1>
```

**"Showing X–Y of N · Rows: N" footer** (`TeamTable.tsx` lines 209–337) — copy the full `<nav>` block. Derive `start`/`end` the same way:
```typescript
const start = count === 0 ? 0 : (page - 1) * pageSize + 1;
const end = Math.min(page * pageSize, count);
const totalPages = count > 0 ? Math.ceil(count / pageSize) : 1;
```
Copy `buildPageRange` helper (lines 24–29) verbatim — it handles ellipsis for long page ranges.

**Rows-per-page options:** match team page `[10, 25, 50, 100]` exactly.

---

### SEED-05 — `frontend/src/widgets/review-management/ProgressModal.tsx` (component, event-driven)

**Analog:** self (existing file, surgical edits only)

**Location of step labels** (`ProgressModal.tsx` lines 332–601):
- Step 1 label: line 336 `"Fetched from Google"` (pending) and line 348 `"Fetched from Google"` (complete) and line 367 `"Fetched from Google"` (active) — **D-03: all three occurrences must change to `"Fetching from Google"`**. The active-state aria-label on line 385 already uses "Fetching from Google" — only the `<label>` text needs updating.
- Step 2 label: `"Building Tag Vocabulary"` (lines 410, 421, 441) — keep as-is.
- Step 3 label: `"Analysing with Review Bee AI Engine"` (lines 479, 491, 510) — keep as-is.
- Step 4 label: `"Finalising"` (lines 540, 552, 570) — keep as-is.

**Per-step timing display pattern (D-04):**
The snapshot interface (`SnapshotState`, lines 5–24) must gain per-step timing fields. Pattern to follow for each completed step:
```typescript
// In SnapshotState interface — add:
fetch_started_at?: string | null;
vocab_started_at?: string | null;
enriching_started_at?: string | null;
finalising_started_at?: string | null;
fetch_duration_seconds?: number | null;
vocab_duration_seconds?: number | null;
enriching_duration_seconds?: number | null;
// finalising_duration_seconds already exists as duration_seconds on sync.complete
```

Display pattern when a step transitions to "complete" — show duration inline next to the step summary line. Reference the existing `duration_seconds` display on the success banner (lines 323–327) for the format:
```tsx
// Existing pattern (lines 323-327):
{snapshot?.duration_seconds != null
  ? ` in ${Math.round(snapshot.duration_seconds)}s`
  : ""}
```
For per-step timing, format as "· Xm Ys" on the complete-state summary line, e.g.:
```tsx
// In the vocabState === "complete" branch (line 419+), after the count:
{snapshot?.vocab_duration_seconds != null && (
  <span className="text-muted font-normal">
    {" · "}{formatDuration(snapshot.vocab_duration_seconds)}
  </span>
)}
```
where `formatDuration(s: number): string` converts seconds to "Xm Ys" (or just "Ys" if < 60s).

---

### SEED-05 — `apps/reviews/services/sync.py` + `apps/reviews/services/finalise.py` (service, event-driven)

**Analog for per-step timing:** `apps/reviews/services/finalise.py` lines 136 + 80–92

**Finalise already computes its own duration** (lines 136):
```python
duration_seconds = round(_time.monotonic() - _finalise_start, 1)
```
`_finalise_start = _time.monotonic()` is set at function entry (line 34 in finalise.py). Copy this exact pattern for each step transition in `sync.py` and `run_initial_backfill`.

**Where to record per-step start timestamps in the snapshot:**

In `fetch_and_persist_reviews` (`sync.py` line 310–322), the initial snapshot already records `started_at`. Add `fetch_started_at` here and compute `fetch_duration_seconds` when writing `fetch_end_snapshot` (line 500–510):
```python
# At sync start (line 310):
data={
    ...
    "fetch_started_at": started_at.isoformat(),
}

# At fetch-end (line 500-510), add:
import time as _time
fetch_duration = round((dj_timezone.now() - started_at).total_seconds(), 1)
fetch_end_snapshot = {
    ...
    "fetch_duration_seconds": fetch_duration,
}
```

In `run_initial_backfill` (`sync.py` line 647+), vocab phase starts — record `vocab_started_at` in the snapshot written at line 661 and compute `vocab_duration_seconds` when writing `enriching_snapshot` at line 703+. Enriching phase starts at line 703 — record `enriching_started_at`; the finalising step's duration is already computed in `finalise.py`.

**Snapshot fields to add** (to be stored in Redis and read by the consumer):
```python
"fetch_started_at": ...,         # ISO timestamp, set at sync start
"fetch_duration_seconds": ...,   # set when fetch loop ends
"vocab_started_at": ...,         # ISO timestamp, set when vocab step begins
"vocab_duration_seconds": ...,   # set when enriching step begins
"enriching_started_at": ...,     # ISO timestamp, set when bulk dispatch begins
# enriching_duration_seconds computed by finalise.py on finalising start
```

---

### SEED-06 — `apps/reviews/services/sync.py` `fetch_and_persist_reviews` (service, event-driven)

**Analog for the silent-return gate:** `apps/reviews/services/enrichment.py` `_emit_enrichment_progress` (lines 396–421)

**The intent to mirror** (enrichment.py lines 418–421):
```python
snapshot = read_progress_snapshot(shop_id=shop_id)
if snapshot is None:
    # No live progress modal — no WebSocket event needed (e.g. incremental sync).
    return
```
This is exactly how incremental enrichments stay silent when no initial-sync modal is open.

**All call sites in `fetch_and_persist_reviews` that must be gated on `trigger == "initial"`:**

The CONTEXT.md lists approximate line numbers (309, 332, 469, 511, 524, 564 + paired emits). After reading the file, the exact sites are:

| Line | Call | Gate needed? |
|---|---|---|
| 309 | `clear_progress_snapshot(shop_id=shop_id)` | YES — gate on `trigger == "initial"` |
| 310–322 | `write_progress_snapshot(...)` — initial "fetching" snapshot | YES |
| 332–350 | `write_progress_snapshot(...)` — invalid_grant failure snapshot | YES |
| 341–350 | `emit_progress_event(...)` — sync.error (invalid_grant) | YES |
| 469 | `write_progress_snapshot(shop_id=shop_id, data=snapshot)` — per-page progress | YES |
| 470–478 | `emit_progress_event(...)` — sync.fetch.progress per page | YES |
| 511 | `write_progress_snapshot(shop_id=shop_id, data=fetch_end_snapshot)` — end of fetch (initial path) | Already inside `if trigger == "initial":` block — no change |
| 524 | `write_progress_snapshot(shop_id=shop_id, data=success_payload)` — incremental success | Already inside `else:` (non-initial) — write is harmless for incremental but emit is not |
| 525–533 | `emit_progress_event(...)` — sync.complete for incremental | Already in `else:` block — this is intentional for incremental, NOT gated |
| 564–572 | `write_progress_snapshot(...)` — quota/unreachable failure | YES — gate on `trigger == "initial"` |
| 573–581 | `emit_progress_event(...)` — sync.error (quota/unreachable) | YES |

**Gate pattern to apply** (wrap the ungated snapshot + emit pairs):
```python
# Before: (lines 309-322)
clear_progress_snapshot(shop_id=shop_id)
write_progress_snapshot(shop_id=shop_id, data={...})

# After:
if trigger == "initial":
    clear_progress_snapshot(shop_id=shop_id)
    write_progress_snapshot(shop_id=shop_id, data={...})
```
Apply the same `if trigger == "initial":` wrapper to all ungated call sites listed above (lines 309, 332, 341, 469, 470, 564, 573). The per-page emit at line 470 is the most impactful — without the gate, every incremental page wipes the modal's fetched count back to `total_persisted` for that page only.

---

### SEED-06 (D-05/D-06) — `apps/reviews/migrations/0015_beat_incremental_6h.py` (migration, batch)

**Analog:** `apps/reviews/migrations/0002_periodic_tasks_seed.py` (creates the task) + `apps/reviews/migrations/0013_periodic_task_seed_polarity_reclassify.py` (canonical pattern for naming, structure, reversibility)

**Why closest:** Both use `CrontabSchedule.objects.get_or_create` + `PeriodicTask.objects.update_or_create` with a `remove_*` reverse function. Migration 0002 is the exact task being updated (`enqueue_incremental_syncs`).

**Pattern to copy** (from `0002_periodic_tasks_seed.py` lines 9–50):
```python
def seed_periodic_tasks(apps, schema_editor) -> None:
    CrontabSchedule = apps.get_model("django_celery_beat", "CrontabSchedule")
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")

    crontab, _ = CrontabSchedule.objects.get_or_create(
        minute="0",
        hour="*/6",       # D-06: every 6h instead of hourly "*"
        day_of_week="*",
        day_of_month="*",
        month_of_year="*",
        timezone="UTC",
    )
    PeriodicTask.objects.update_or_create(
        name="enqueue_incremental_syncs",
        defaults={
            "task": "apps.reviews.tasks.enqueue_incremental_syncs_task",
            "crontab": crontab,
            "interval": None,
            "enabled": True,        # D-05: re-enable (was disabled as UAT mitigation)
            "queue": "google-sync",
            "args": json.dumps([]),
            "kwargs": json.dumps({}),
            "description": (
                "Phase 26 SEED-06/D-06: 6-hourly fan-out (was hourly). "
                "Re-enabled after SEED-06 trigger gate fix. "
                "Aligns with INCREMENTAL_SYNC_INTERVAL_HOURS=6 setting."
            ),
        },
    )
```

**Reverse function** — restores the old hourly crontab + disabled state:
```python
def revert_to_hourly_disabled(apps, schema_editor) -> None:
    CrontabSchedule = apps.get_model("django_celery_beat", "CrontabSchedule")
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")
    # Re-create the hourly schedule and set enabled=False
    crontab, _ = CrontabSchedule.objects.get_or_create(
        minute="0", hour="*", day_of_week="*",
        day_of_month="*", month_of_year="*", timezone="UTC",
    )
    PeriodicTask.objects.filter(name="enqueue_incremental_syncs").update(
        crontab=crontab, enabled=False
    )
```

**Migration dependency chain:** latest reviews migration is `0014_tagmergejob`. New migration is `0015_beat_incremental_6h` with dependency `("reviews", "0014_tagmergejob")`.

---

## Shared Patterns

### Org-scoped tenant guard in viewsets
**Source:** `apps/reviews/views.py` `OrgCanonicalTagViewSet.get_queryset` (lines 482–486)
**Apply to:** all viewset changes in Phase 26
```python
org_id = getattr(self.request.user, "organisation_id", None)
if org_id is None:
    return OrgCanonicalTag.objects.none()
```

### Query-count test pattern
**Source:** `apps/accounts/tests/test_selectors.py` (query-count ceiling test, §6.9)
**Apply to:** the extended `list_canonical_tags_for_org` — add `?search=foo` case to the existing query-count test. The ceiling must stay ≤2 (1 COUNT + 1 SELECT). Use `django.test.utils.CaptureQueriesContext`.

### Celery Beat data migration structure
**Source:** `apps/reviews/migrations/0013_periodic_task_seed_polarity_reclassify.py`
**Apply to:** `0015_beat_incremental_6h.py`
- Always provide a `reverse_code` — use `update()` or `delete()` not silent no-ops.
- Use `CrontabSchedule.objects.get_or_create` (idempotent).
- Use `PeriodicTask.objects.update_or_create` (idempotent on re-run).
- Description string must reference the phase + requirement ID.

### Frontend debounce pattern
**Source:** `frontend/src/widgets/team-management/TeamTable.tsx` lines 42–54
**Apply to:** `TagManagementWidget.tsx` search input
- 300ms timeout via `useRef<ReturnType<typeof setTimeout>>`.
- `eslint-disable-next-line react-hooks/exhaustive-deps` comment on the `useEffect` to suppress the `setSearch` stale-closure warning (intentional — debounce must not restart on every render).

---

## No Analog Found

All 9 files have close analogs. No files require falling back to RESEARCH.md patterns.

---

## Metadata

**Analog search scope:** `apps/accounts/`, `apps/reviews/`, `frontend/src/widgets/team-management/`, `frontend/src/widgets/tag-management/`, `frontend/src/widgets/review-management/`, `apps/reviews/migrations/`
**Files read:** 20
**Pattern extraction date:** 2026-06-24
