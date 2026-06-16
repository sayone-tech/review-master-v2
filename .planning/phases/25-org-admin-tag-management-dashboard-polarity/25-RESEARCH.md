# Phase 25: Org Admin Tag Management & Dashboard Polarity - Research

**Researched:** 2026-06-16
**Domain:** Django/DRF tag management API + React widget (data-table, modal, HTTP polling) + Recharts stacked bar dashboard extension
**Confidence:** HIGH — all critical codebase assets verified directly from source files

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Tags page at `/admin/org/tags/`, sidebar under Settings. Access: `ORG_ADMIN` only — `STAFF_ADMIN` cannot reach it. Enforce at BOTH view/permission layer (403) AND sidebar (nav item hidden for Staff).
- **D-02:** Tag list = paginated, query-count-bounded endpoint, sortable by column. Columns: Label, Polarity Type badge, Review Count, First Seen, Actions menu. React data-table widget reusing `audit-log`/`data-table` pattern.
- **D-03:** Rename updates ONLY `OrgCanonicalTag.label` — O(1) write. Raw `ReviewTag.label` rows NOT touched. Inline, synchronous save.
- **D-04:** Rename validation: 1–100 chars, reject case-insensitive duplicates within the org (clear inline error), NO silent merge, Title-Case normalization server-side, no ≤3-word cap for human admin renames.
- **D-05:** Merge UX: modal with searchable target picker and "re-maps N reviews, cannot be undone" warning. Irreversible.
- **D-06:** Merge result: user-chosen TARGET always kept. Source FKs re-point to target in single bulk UPDATE. Source tag deleted. `review_count` refreshed via aggregate (not naive sum). Target's `polarity_type` kept.
- **D-07:** Merge runs as batched `merge_canonical_tags(source_id, target_id)` Celery task on `tag-merge` queue, under `lock:tag_merge:org:{org_id}` per-org lock, reusing Phase 23 FK-repoint + count-refresh primitives. Posts completion notification. Whole merge is `transaction.atomic`.
- **D-08:** Merge progress tracked in new durable DB model `TagMergeJob` (organisation, source label denormalized, target FK/label, status PENDING/IN_PROGRESS/SUCCESS/FAILED, processed/total, error_message, timestamps). HTTP polling (~2s while in-progress) via GET endpoint keyed by job id. No new WebSocket consumer (§13.2). Org-scoped. UI: progress bar with dismiss, reload-survival, completion toast, failure path.
- **D-09:** Extend existing dashboard tag chart: always_positive/always_negative = single colored bar; mixed = stacked positive/negative segments from `ReviewTag.polarity` distribution.
- **D-10:** ALL canonical aggregation queries include only reviews where `canonical_tag IS NOT NULL`. Org-scoped, query-bounded.

### Claude's Discretion

- Exact React widget composition (reuse audit-log/data-table/modal/reports widgets + recharts).
- Poll interval exact value (~2s).
- Progress granularity (processed/total vs coarse states).
- Tags sidebar icon (lucide `tags` glyph).
- Whether rename/merge are DRF viewset actions vs dedicated endpoints.
- Whether list `review_count` reads denormalized column or bounded aggregate.
- Dashboard chart library/representation details (finalised in UI-SPEC).

### Deferred Ideas (OUT OF SCOPE)

- Merge undo / history beyond the TagMergeJob record.
- Bulk multi-tag merge / split.
- Superadmin data reset (Phase 26).
- Auto re-promotion of mixed tags.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| TMGT-01 | Org Admin and Manager can reach Tags page at `/admin/org/tags/` (sidebar under Settings); Staff cannot | `@org_admin_required` decorator + `{% if user.role != "STAFF_ADMIN" %}` sidebar guard — both patterns verified in codebase |
| TMGT-02 | Tag list: Label, Polarity badge, Review Count, First Seen, Actions menu; sortable, paginated, query-count-bounded | `OrgCanonicalTag` model verified (all 4 fields present); `OrderingFilter` + `DefaultPageNumberPagination` patterns available |
| TMGT-03 | Canonical tag renamed inline (1–100 chars, unique within org); save updates `OrgCanonicalTag.label` only | Model `label` field is `CharField(max_length=100)`; UniqueConstraint on `(organisation, label)`; rename is O(1) FK-only design |
| TMGT-04 | Tag merged into another via modal with searchable target picker and "re-maps N reviews, cannot be undone" warning | `MergeModal.tsx` pattern (two-step pick/confirm) verified; tag list available from existing canonical-tags selector |
| TMGT-05 | Merge: batched Celery task (tag-merge queue, per-org lock), re-points reviews, deletes source, refreshes count, posts notification | `_merge_group` and `_refresh_review_counts` primitives verified in `finalise.py`; `distributed_lock` helper verified; `dispatch_notification` API verified |
| TMGT-06 | Merge progress: HTTP polling, in-progress bar with dismiss, reload-survival, completion toast, failure rollback | `useNotifications` 60s polling pattern verified; `TagMergeJob` model must be created new (does not exist yet) |
| TDASH-01 | Dashboard tag chart: single bar for always_positive/always_negative; stacked positive/negative bar for mixed | Recharts `BarChart` + `<Bar stackId>` pattern verified in `TopPerformingSection.tsx` |
| TDASH-02 | Canonical aggregation queries include only reviews where `canonical_tag IS NOT NULL` | `ReviewTag.canonical_tag` is nullable FK; filter `canonical_tag__isnull=False` enforced in new dashboard selector |
</phase_requirements>

---

## Summary

Phase 25 is a well-bounded feature addition: a Tag Management page for Org Admins (list, rename, merge) and a polarity-aware extension to the existing dashboard. All foundational dependencies from Phases 22–24 are confirmed present in the codebase. The critical Phase 23 primitives (`_merge_group`, `_refresh_review_counts`) exist in `apps/reviews/services/finalise.py`. The `tag-merge` Celery queue is configured in `CELERY_TASK_ROUTES`. The `distributed_lock` helper is verified.

**Phase 25 must build from scratch:** (1) `TagMergeJob` model + migration; (2) `merge_canonical_tags_task` Celery task + service; (3) `merge_canonical_tags_task` entry in `CELERY_TASK_ROUTES`; (4) three API endpoints (canonical tags list/rename, merge start, job poll/dismiss); (5) a new `TAG_MERGE_COMPLETE` notification type; (6) `TagManagementWidget` React widget (7 new `.tsx`/`.ts` files) with entrypoint + Vite config entry; (7) `TagPolarityChart` dashboard section; (8) the Django template at `templates/org_admin/tags.html`; (9) the new `dashboard_tag_polarity` selector and dashboard view/URL.

**Primary recommendation:** Clone the `AuditLogViewSet` + `audit-log` widget composition pattern for the tags list (PageNumber pagination, `OrderingFilter`, `IsOrgAdmin` permission, `DefaultPageNumberPagination`, query-count test). Clone `TopPerformingSection.tsx` recharts pattern for the dashboard chart. Clone `useNotifications` hook for the 2s merge-progress poll. The `_merge_group`/`_refresh_review_counts` primitives in `finalise.py` must be adapted (not used as-is) because their current signatures are designed for automatic dedup (winner = highest `review_count`), not user-directed merge (winner = user-chosen target).

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Tag list (paginated, sorted) | API / Backend | Browser / Client | DRF ViewSet + selector; React renders |
| Rename (O(1) label update) | API / Backend | — | Single-row DB write via service; view validates |
| Merge job creation | API / Backend | — | Creates TagMergeJob + enqueues Celery; no client-side state needed |
| Merge execution (FK re-point, count refresh) | Celery worker | Database / Storage | Background task inside transaction.atomic |
| Merge progress polling | Browser / Client | API / Backend | React hook polls GET endpoint; backend reads TagMergeJob |
| Tag chart polarity aggregation | Database / Storage | API / Backend | Grouped aggregate query in selector; cached in view |
| Sidebar nav gating | Browser / Client | Frontend Server (SSR) | Django template conditional; view returns 403 independently |
| Notification dispatch on merge complete | Celery worker | — | Called from task after SUCCESS transition |

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Django + DRF | 6.0.x / latest | Tag list endpoint, rename/merge API, TagMergeJob model | Project standard |
| Celery | ^5.4.0 | `merge_canonical_tags_task` on `tag-merge` queue | Project standard (Phase 12+) |
| `rest_framework.filters.OrderingFilter` | bundled with DRF | Column sorting via `?ordering=` | Used in `ReviewViewSet`; correct choice for bounded column set |
| `DefaultPageNumberPagination` | `apps/common/pagination.py` | 25-per-page, `page_size_query_param`, `max_page_size=100` | Existing shared class — reuse |
| `distributed_lock` | `apps/common/locks.py` | Per-org lock for merge task | Verified in codebase |
| Recharts | already installed | `TagPolarityChart` stacked bar | Verified used in `TopPerformingSection.tsx` |
| lucide-react | already installed | Icons in tag widget | Verified across all existing widgets |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `django-filter` | already installed | FilterSet for canonical tags list (if search filter added) | Only if server-side label search is added; UI-SPEC opts for client-side search in modal |
| `dispatch_notification` | `apps/notifications/services/dispatch.py` | Post merge-complete notification | Called inside task after SUCCESS |
| `emitToast` | `frontend/src/lib/toast.ts` | Merge-complete toast in React | Already used by `MergeModal.tsx` |

**Version verification:** No new npm or PyPI packages required. All libraries are already installed. [VERIFIED: direct codebase inspection of `pyproject.toml` and `frontend/package.json` via `vite.config.ts` imports]

---

## Package Legitimacy Audit

No new packages are installed in this phase. All dependencies (`recharts`, `lucide-react`, `celery`, `django-filter`, DRF) are already present in the project.

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

---

## Architecture Patterns

### System Architecture Diagram

```
Org Admin browser
    │
    ├─ GET /admin/org/tags/ ──────────► Django template view (@org_admin_required)
    │                                         └─ renders tags.html (mounts #tag-management-root)
    │
    ├─ GET /api/v1/reviews/canonical-tags/
    │   ?ordering=-review_count&page=1 ──► OrgCanonicalTagViewSet.list()
    │                                         └─ list_canonical_tags_for_org() selector
    │                                              └─ OrgCanonicalTag.objects.filter(org) [1 query]
    │
    ├─ PATCH /api/v1/reviews/canonical-tags/{id}/rename/
    │   {label: "New Label"} ────────────► rename_canonical_tag() service
    │                                         └─ OrgCanonicalTag.label = title_case(label)
    │                                              └─ .save(update_fields=["label"]) [O(1)]
    │
    ├─ POST /api/v1/reviews/canonical-tags/{source_id}/merge/
    │   {target_id} ──────────────────────► merge service:
    │                                         ├─ create TagMergeJob(PENDING)
    │                                         ├─ merge_canonical_tags_task.delay(job_id)
    │                                         └─ return {job_id}  [201 Created]
    │
    ├─ GET /api/v1/reviews/tag-merge-jobs/active/ ──► TagMergeJobViewSet
    │   (2s poll while PENDING/IN_PROGRESS)               └─ most recent non-dismissed job for org
    │
    ├─ PATCH /api/v1/reviews/tag-merge-jobs/{id}/dismiss/ ──► mark dismissed=True
    │
    └─ GET /api/v1/dashboard/tag-polarity/ ──► DashboardTagPolarityView
                                                   └─ dashboard_tag_polarity() selector
                                                        └─ ReviewTag JOIN OrgCanonicalTag GROUP BY
                                                             [canonical_tag IS NOT NULL, 1-2 queries]

Celery worker (tag-merge queue):
    merge_canonical_tags_task(job_id)
        ├─ acquire lock:tag_merge:org:{org_id} (non-blocking → exit if held)
        ├─ job.status = IN_PROGRESS; job.save()
        ├─ transaction.atomic():
        │   ├─ ReviewTag.objects.filter(canonical_tag=source).update(canonical_tag=target) [bulk UPDATE]
        │   ├─ source.delete()
        │   └─ _refresh_review_counts(organisation_id) [1 aggregate + 1 bulk_update]
        ├─ job.status = SUCCESS; job.save()
        └─ dispatch_notification(notification_type="tag_merge_complete", ...)
```

### Recommended Project Structure

New files this phase must create:

```
apps/reviews/
├── models.py                          # ADD TagMergeJob model
├── migrations/
│   └── 0014_tagmergejob.py           # new migration (one per PR)
├── selectors/
│   └── canonical_tags.py             # ADD list_canonical_tags_for_org(), list_tag_polarity_for_org()
├── services/
│   └── tag_management.py             # NEW: rename_canonical_tag(), create_merge_job(), merge_canonical_tags()
├── serializers.py                     # ADD OrgCanonicalTagReadSerializer, TagMergeJobSerializer
├── views.py                           # ADD OrgCanonicalTagViewSet, TagMergeJobViewSet
├── urls.py                            # ADD tags page template view URL
└── tasks.py                           # ADD merge_canonical_tags_task

apps/dashboard/
├── selectors/aggregations.py          # ADD dashboard_tag_polarity()
├── views.py                           # ADD DashboardTagPolarityView
└── urls.py                            # ADD tag-polarity/ URL

apps/notifications/models.py           # ADD TAG_MERGE_COMPLETE to NotificationType

config/settings/base.py               # ADD merge_canonical_tags_task to CELERY_TASK_ROUTES

templates/
└── org_admin/
    └── tags.html                      # NEW Django template

frontend/
├── vite.config.ts                     # ADD "tag-management" entrypoint
└── src/
    ├── entrypoints/
    │   └── tag-management.tsx         # NEW
    └── widgets/
        ├── tag-management/            # NEW widget folder (7 files — see UI-SPEC)
        └── dashboard/
            └── TagPolarityChart.tsx   # NEW dashboard section
```

### Pattern 1: OrgCanonicalTagViewSet (tag list + rename + merge)

```python
# apps/reviews/views.py — new viewset
from rest_framework import mixins, viewsets, status
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter
from rest_framework.response import Response
from apps.accounts.permissions import IsOrgAdmin
from apps.common.pagination import DefaultPageNumberPagination
from apps.reviews.models import OrgCanonicalTag
from apps.reviews.serializers import OrgCanonicalTagReadSerializer, RenameSerializer
from apps.reviews.services.tag_management import rename_canonical_tag, create_merge_job
from apps.reviews.selectors.canonical_tags import list_canonical_tags_for_org

class OrgCanonicalTagViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsOrgAdmin]
    serializer_class = OrgCanonicalTagReadSerializer
    pagination_class = DefaultPageNumberPagination
    filter_backends = [OrderingFilter]
    ordering_fields = ["label", "review_count", "created_at"]
    ordering = ["-review_count"]  # default sort
    queryset = OrgCanonicalTag.objects.none()  # router introspection

    def get_queryset(self):
        org_id = self.request.user.organisation_id
        return list_canonical_tags_for_org(organisation_id=org_id)

    @action(detail=True, methods=["patch"], url_path="rename")
    def rename(self, request, pk=None):
        tag = self.get_object()
        serializer = RenameSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        updated = rename_canonical_tag(
            tag=tag,
            new_label=serializer.validated_data["label"],
            organisation_id=request.user.organisation_id,
        )
        return Response(OrgCanonicalTagReadSerializer(updated).data)

    @action(detail=True, methods=["post"], url_path="merge")
    def merge(self, request, pk=None):
        source = self.get_object()
        target_id = request.data.get("target_id")
        # Validation: target must exist, belong to same org, not be the source
        job = create_merge_job(
            source_tag=source,
            target_id=target_id,
            organisation_id=request.user.organisation_id,
        )
        return Response({"job_id": str(job.pk)}, status=status.HTTP_201_CREATED)
```

**Source:** [ASSUMED] — pattern derived from `AuditLogViewSet` (`apps/common/views.py:221`) and `ReviewViewSet` (`apps/reviews/views.py:61`) verified in codebase.

### Pattern 2: Merge Service and Task

The critical insight: `_merge_group` in `finalise.py` (line 194) is designed for **automatic dedup** where the winner is chosen by highest `review_count`. The manual merge in Phase 25 requires a **different signature** where the caller specifies the winner (target). Do NOT call `_merge_group` directly — write a new `merge_canonical_tags()` service function that uses the same FK-repoint + count-refresh primitives but with explicit source/target:

```python
# apps/reviews/services/tag_management.py
from django.db import transaction
from apps.reviews.models import OrgCanonicalTag, ReviewTag, TagMergeJob
from apps.reviews.services.finalise import _refresh_review_counts
from apps.common.locks import distributed_lock

@transaction.atomic
def merge_canonical_tags(*, job_id: int) -> None:
    """Execute a user-initiated tag merge. Called by merge_canonical_tags_task.

    Winner = user-chosen target (D-06 — NOT higher review_count).
    Source FKs re-pointed in a single bulk UPDATE (no N+1 — §6.10).
    review_count refreshed via aggregate (D-03 derive-on-read).
    """
    job = TagMergeJob.objects.select_for_update().get(pk=job_id)
    if job.status not in (TagMergeJob.Status.PENDING, TagMergeJob.Status.IN_PROGRESS):
        return  # idempotent no-op

    org_id = job.organisation_id
    source = OrgCanonicalTag.objects.get(pk=job.source_tag_id, organisation_id=org_id)
    target = OrgCanonicalTag.objects.get(pk=job.target_tag_id, organisation_id=org_id)

    job.status = TagMergeJob.Status.IN_PROGRESS
    job.total = source.review_count
    job.save(update_fields=["status", "total"])

    # Single bulk UPDATE — O(N reviews) but one query (§6.10)
    job.processed = ReviewTag.objects.filter(canonical_tag=source).update(canonical_tag=target)
    source.delete()
    _refresh_review_counts(organisation_id=org_id)

    job.status = TagMergeJob.Status.SUCCESS
    job.save(update_fields=["status", "processed"])
```

**Source:** [VERIFIED: codebase] — `_refresh_review_counts` signature at `apps/reviews/services/finalise.py:285` takes only `organisation_id: int`. `ReviewTag.objects.filter(canonical_tag=...).update(...)` pattern used at `finalise.py:221`.

### Pattern 3: HTTP Polling Hook (clone of useNotifications)

```typescript
// frontend/src/widgets/tag-management/useMergeProgress.ts
export function useMergeProgress() {
  const [job, setJob] = useState<TagMergeJobRow | null>(null);
  const [dismissed, setDismissed] = useState(false);

  const fetchJob = useCallback(async () => {
    try {
      const data = await fetchActiveJob();
      setJob(data);
    } catch { /* best-effort */ }
  }, []);

  useEffect(() => {
    void fetchJob();
    if (job?.status === "PENDING" || job?.status === "IN_PROGRESS") {
      const id = setInterval(() => void fetchJob(), 2_000);
      return () => clearInterval(id);
    }
  }, [job?.status, fetchJob]);
  // ...
}
```

**Source:** [VERIFIED: codebase] — `useNotifications.ts` at `frontend/src/widgets/notif-bell/useNotifications.ts:1`. Pattern uses `setInterval` with cleanup on `useEffect` return, same structure as UI-SPEC D-08.

### Pattern 4: Dashboard Tag Polarity Selector

```python
# apps/dashboard/selectors/aggregations.py — new function
from django.db.models import Count, Q
from apps.reviews.models import OrgCanonicalTag, ReviewTag

def dashboard_tag_polarity(*, organisation_id: int, limit: int = 10) -> dict:
    """Return top-N canonical tags with positive/negative split.

    TDASH-02: ONLY reviews where canonical_tag IS NOT NULL.
    No N+1: two queries total (1 aggregate, 1 OrgCanonicalTag metadata fetch).
    """
    # Single aggregate query: ReviewTag → canonical_tag → polarity → count
    rows = (
        ReviewTag.objects
        .filter(
            canonical_tag__organisation_id=organisation_id,
            canonical_tag__isnull=False,
        )
        .values("canonical_tag_id", "canonical_tag__label", "canonical_tag__polarity_type")
        .annotate(
            positive_count=Count("id", filter=Q(polarity="positive")),
            negative_count=Count("id", filter=Q(polarity="negative")),
            total_count=Count("id"),
        )
        .order_by("-total_count")[:limit + 1]  # fetch limit+1 to detect has_more
    )
    tags = list(rows)
    has_more = len(tags) > limit
    return {
        "tags": [
            {
                "label": r["canonical_tag__label"],
                "polarity_type": r["canonical_tag__polarity_type"],
                "positive_count": r["positive_count"],
                "negative_count": r["negative_count"],
                "total_count": r["total_count"],
            }
            for r in tags[:limit]
        ],
        "has_more": has_more,
    }
```

**Source:** [ASSUMED] — derived from `dashboard_kpis` selector pattern in `apps/dashboard/selectors/aggregations.py` (verified at line 49 test). The grouped-aggregate approach matches `_refresh_review_counts` pattern (verified at `finalise.py:285–298`).

### Anti-Patterns to Avoid

- **Do NOT call `_merge_group` from the manual merge task.** `_merge_group` selects the winner by highest `review_count`, but D-06 mandates the user-chosen target always wins. Use the FK-repoint pattern directly in the new `merge_canonical_tags()` service.
- **Do NOT increment `review_count` inline during merge.** Call `_refresh_review_counts(organisation_id=org_id)` after the FK re-point. Never `target.review_count += source.review_count`.
- **Do NOT add a new WebSocket consumer for merge progress.** §13.2 is non-negotiable. HTTP polling at 2s intervals is the decided approach (D-08).
- **Do NOT use `audit_log_view`'s `@login_required` pattern for the Tags page.** The Tags page is ORG_ADMIN only (not Staff); use `@org_admin_required` (from `apps/accounts/permissions.py`, verified at line 44), which redirects Staff to login. The audit log uses `@login_required` because Staff can access it — tags cannot.
- **Do NOT denormalize `label` onto `ReviewTag`.** The FK-only design (D-03) means rename is O(1). Reads resolve through the JOIN. Never copy `OrgCanonicalTag.label` onto child rows.
- **Do NOT add `review_count` to `bulk_update` field lists** unless inside the `_refresh_review_counts` path. The model comment at `apps/reviews/models.py:155` documents this invariant explicitly.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Column-sortable list endpoint | Custom sort param parsing | `rest_framework.filters.OrderingFilter` with `ordering_fields` | Already used in `ReviewViewSet`; handles asc/desc, whitelisting |
| Page-number pagination | Custom pagination | `DefaultPageNumberPagination` from `apps/common/pagination.py` | Shared class; `page_size_query_param="page_size"`, `max_page_size=100` |
| Merge progress bar React component | Custom `<div>` with JS timer | Clone `useMergeProgress` hook mirroring `useNotifications` | Identical pattern; poll + auto-stop on terminal state |
| Stacked bar chart | Custom SVG | Recharts `<BarChart>` + two `<Bar stackId="a">` (verified in `TopPerformingSection.tsx`) | Already installed; exact pattern in codebase |
| Distributed lock | Redis `SET NX EX` raw | `apps/common/locks.py::distributed_lock` | Project standard; handles LockNotOwnedError cleanup |
| Completion notification | Django signals / custom email | `apps/notifications/services/dispatch.py::dispatch_notification` | Existing fan-out service; NOTF-05 enforcement built in |
| Title-Case normalization | Custom string fn | Python `str.title()` or `titlecase` lib (project uses `str.title()` in enrichment) | Simple built-in for server-side label normalization |

**Key insight:** Phase 23/24 built the atomic primitives; Phase 25 composes them. The only genuinely new infrastructure is `TagMergeJob` model and the manual-merge service (which differs from `_merge_group` in winner selection logic).

---

## Critical Verification Results

### Verification 1: Phase 23 Dependency Reality Check

**Status: CONFIRMED PRESENT** [VERIFIED: direct file reads]

| Asset | Exists? | Location | Notes |
|-------|---------|----------|-------|
| `tag-merge` Celery queue | YES | `config/settings/base.py:226` (`CELERY_QUEUE_NAMES`) and `:128` (`CELERY_TASK_ROUTES` for `finalize_canonical_tags_task`) | Queue exists and is routed |
| `merge_canonical_tags_task` | NO | — | Does NOT exist in `apps/reviews/tasks.py`. Phase 25 must add it. |
| `CELERY_TASK_ROUTES` entry for `merge_canonical_tags_task` | NO | — | Not in `config/settings/base.py:120–132`. Phase 25 must add: `"apps.reviews.tasks.merge_canonical_tags_task": {"queue": "tag-merge"}` |
| `_merge_group(*, organisation_id, lower_label)` | YES | `apps/reviews/services/finalise.py:194` | Signature takes `lower_label: str` (a label string, not IDs). Designed for auto-dedup (winner = highest review_count). **NOT directly reusable** for user-directed merge — winner selection logic differs. |
| `_refresh_review_counts(*, organisation_id)` | YES | `apps/reviews/services/finalise.py:285` | Signature takes only `organisation_id: int`. Single aggregate query + `bulk_update`. **Fully reusable** for post-merge count refresh. |
| `distributed_lock` helper | YES | `apps/common/locks.py:31` | Signature: `distributed_lock(key: str, timeout: int = 300, blocking: bool = False)`. Returns context manager yielding `bool`. |

**Conclusion on `_merge_group`:** Its internal logic (choosing winner by highest `review_count`, breaking ties by earliest `created_at`) conflicts with D-06 ("user-chosen target always wins"). The FK-repoint pattern inside `_merge_group` (`ReviewTag.objects.filter(canonical_tag=loser).update(canonical_tag=winner)`) is the correct approach, but it must be replicated in the new `merge_canonical_tags()` service with explicit source/target rather than delegating to `_merge_group`.

### Verification 2: Canonical Model Ground Truth

[VERIFIED: `apps/reviews/models.py`]

**`OrgCanonicalTag`** (table: `reviews_orgcanonicaltag`):
- `organisation`: FK → `organisations.Organisation` (CASCADE, `db_index=True`, `related_name="canonical_tags"`)
- `label`: `CharField(max_length=100)` — the canonical string
- `polarity_type`: `CharField(max_length=20, choices=PolarityType.choices)` — choices: `always_positive`, `always_negative`, `mixed`
- `polarity_reclassified_at`: `DateTimeField(null=True, blank=True)` — Phase 24 addition
- `review_count`: `PositiveIntegerField(default=0)` — denormalized cache, NEVER incremented inline
- `created_at` / `updated_at`: from `TimeStampedModel` — `created_at` is the "First Seen" column (TMGT-02)
- **UniqueConstraint:** `("organisation", "label")` — name: `"uniq_orgcanonicaltag_org_label"`
- **Index:** `("organisation", "-review_count")` — name: `"orgcanon_org_count_idx"` (good for default sort)

**`ReviewTag`** (table: `reviews_reviewtag`):
- `review`: FK → `reviews.Review` (CASCADE, `related_name="tags"`)
- `label`: `CharField(max_length=100, db_index=True)` — raw per-review tag (not the canonical label)
- `polarity`: `CharField(max_length=10, choices=Polarity.choices)` — choices: `positive`, `neutral`, `negative`
- `canonical_tag`: FK → `reviews.OrgCanonicalTag` (nullable, `on_delete=models.SET_NULL`, `db_index=True`, `related_name="review_tags"`)
- **UniqueConstraint:** `("review", "label", "polarity")` — race guard; `canonical_tag` intentionally excluded
- **Index:** `("review", "label")`

**Key for merge:** `ReviewTag.objects.filter(canonical_tag=source).update(canonical_tag=target)` is the correct bulk re-point. After `source.delete()`, all `ReviewTag.canonical_tag` FKs that pointed to source now point to target. Because `on_delete=SET_NULL`, any FK that isn't updated before the delete would be nulled — so the FK re-point MUST happen inside `transaction.atomic()` BEFORE `source.delete()`.

### Verification 3: React Widget Patterns

[VERIFIED: direct file reads]

**Entrypoint pattern** (from `frontend/src/entrypoints/audit-log.tsx`):
1. `readJson<T>(elementId, fallback)` reads `<script type="application/json" id="...">` elements for bootstrap data
2. `mount()` function: checks `#tag-management-root`, sets `dataset.mounted = "1"` guard, calls `createRoot(...).render()`
3. Both `mount()` immediately and on `document.addEventListener("turbo:load", mount)` for Turbo compatibility

**Bootstrap data handoff** (from UI-SPEC): TagManagementWidget needs NO bootstrap data beyond CSRF token (all data fetched via API). Template can be minimal — just `<div id="tag-management-root"></div>`.

**Widget layout** (from `AuditLogWidget.tsx`):
- Outer `<div className="space-y-4">`
- `<h1 className="text-[20px] font-semibold text-ink">Tags</h1>`
- `<div className="border border-line rounded-card overflow-hidden">` wrapping table + pagination nav
- Pagination footer: `bg-[#FBFBFB] border-t border-line px-4 py-3 text-[12px] text-muted`

**Vite config** (`frontend/vite.config.ts`): Add to `rollupOptions.input`:
```typescript
"tag-management": resolve(__dirname, "src/entrypoints/tag-management.tsx"),
```

**Recharts `<Bar stackId>` pattern** (from `TopPerformingSection.tsx`):
- Uses `ResponsiveContainer`, `BarChart`, `Bar`, `Cell`, `Tooltip`, `XAxis`, `YAxis`
- `radius={[4, 4, 0, 0]}` on top bar (top corners rounded)
- `role="img" aria-label="..."` on chart wrapper
- Loading skeleton: `bg-line-soft rounded-xl animate-[sk-pulse_1.6s_ease-in-out_infinite] h-[240px]`

**Modal pattern** (from `MergeModal.tsx`):
- Imports `Modal` from `../modal/Modal`
- Two-step state machine: `useState<"pick" | "confirm">("pick")`
- Reset on `open` transition via `useEffect([open])`
- `emitToast` from `../../lib/toast` for success notification

**`DataTable` component:** Located at `frontend/src/widgets/data-table/DataTable.tsx`. Used by multiple widgets. The Tags table renders as `DataTable<OrgCanonicalTagRow>` with the `renderRowActions` prop for the three-dot actions menu.

**`lib/toast.ts`:** `emitToast(detail: ToastDetail)` dispatches `CustomEvent("app:toast")` on `window`. Picked up by Alpine.js listener in `templates/components/toasts.html`.

### Verification 4: DRF List Endpoint Pattern

[VERIFIED: codebase — `apps/action_items/tests/test_views.py:193` and `apps/common/views.py:221`]

**Query-count test shape** (from `test_list_query_count_org_admin_le_5`):
```python
@pytest.mark.django_db
def test_canonical_tags_list_query_count(client, org_admin_user, org):
    OrgCanonicalTagFactory.create_batch(20, organisation=org)
    client.force_login(org_admin_user)
    with CaptureQueriesContext(connection) as ctx:
        resp = client.get("/api/v1/reviews/canonical-tags/", {"page_size": 20})
    assert resp.status_code == 200
    assert len(ctx.captured_queries) <= 3, [q["sql"] for q in ctx.captured_queries]
    # Expected: 1 auth/session + 1 count + 1 data = 3 queries maximum
```

**Two-serializer pattern:** `OrgCanonicalTagReadSerializer` (output shape) is sufficient — rename input uses a separate `RenameSerializer(label=CharField(max_length=100))`.

**Filterset:** Not needed for initial list (no server-side search — the merge modal's search is client-side). The `OrderingFilter` covers column sorting.

**Ceiling for tag list:** Expected 3 queries maximum (session auth + COUNT for pagination + SELECT for page). The `OrgCanonicalTag` model has no nested relations to prefetch.

### Verification 5: Tenant Scoping + RBAC Pattern

[VERIFIED: `apps/accounts/permissions.py` and `templates/partials/sidebar_org.html`]

**Template view (Tags page):** Use `@org_admin_required` decorator (verified at `apps/accounts/permissions.py:44`). This grants access only to `ORG_ADMIN` with a non-null `organisation_id`. Superadmins are redirected to their area. Staff are redirected to login (effectively 403 for the template layer).

**API endpoints:** Use `IsOrgAdmin` DRF permission class (verified at `apps/accounts/permissions.py:27`). Returns 403 for Staff and unauthenticated users.

**Sidebar guard:** `{% if user.role != "STAFF_ADMIN" %}` pattern confirmed at `templates/partials/sidebar_org.html:30,35`. The Tags nav item goes in the same pattern, after "Activity Log". Note that Activity Log itself is NOT wrapped — it's accessible to both roles. Tags is ORG_ADMIN-only, so wrap it in this conditional.

**Sidebar item placement:** Currently the sidebar has "Activity Log" (`href="/admin/org/activity-log/"`) as the last item before the footer (line 41). "Tags" should go **after** Activity Log in the `{% if user.role != "STAFF_ADMIN" %}` block (per UI-SPEC).

**User.Role values:** `ORG_ADMIN = "ORG_ADMIN"` and `STAFF_ADMIN = "STAFF_ADMIN"` — template comparison `user.role != "STAFF_ADMIN"` confirmed working pattern.

### Verification 6: Notification Dispatch + HTTP Poll Precedent

[VERIFIED: `apps/notifications/services/dispatch.py` and `apps/notifications/models.py`]

**`dispatch_notification` signature:**
```python
def dispatch_notification(
    *,
    organisation_id: int,
    notification_type: str,
    title: str,
    target_url: str,
    shop: Shop | None = None,
    action_item: ActionItem | None = None,
    review: Review | None = None,
    recipient_ids: list[int] | None = None,
    exclude_recipient_ids: list[int] | None = None,
    org_admins_only: bool = False,
) -> int:
```

**Existing `NotificationType` choices** (from `apps/notifications/models.py:23`):
- `NEW_REVIEW = "new_review"`
- `NEW_ACTION_ITEM = "new_action_item"`
- `ACTION_ITEM_ASSIGNED = "action_item_assigned"`

**Phase 25 must add:** `TAG_MERGE_COMPLETE = "tag_merge_complete"` to the `NotificationType.TextChoices`. This requires a migration (the field uses `choices=NotificationType.choices`). Note: Django's `choices` parameter doesn't add a DB constraint — the migration is for the Python model layer only. But adding choices to `TextChoices` does require documenting in migrations to keep the schema in sync.

**Merge notification call pattern:**
```python
dispatch_notification(
    organisation_id=job.organisation_id,
    notification_type="tag_merge_complete",
    title=f'Tag "{job.source_label}" merged into "{job.target_tag.label}"',
    target_url="/admin/org/tags/",
    org_admins_only=True,  # merge is ORG_ADMIN-only feature
)
```

**HTTP poll pattern** (`useNotifications.ts`): 60s interval; initial fetch before interval setup; `setInterval` / `clearInterval` in `useEffect`. The merge-progress hook uses the same structure at 2s interval, stopping when status is SUCCESS or FAILED.

**Bell poll endpoint** for reference: `GET /api/v1/notifications/bell/` returns `{unread_count, items[]}`. The merge-progress endpoint follows the same pattern: `GET /api/v1/reviews/tag-merge-jobs/active/` returns the single active job or null.

### Verification 7: Dashboard Tag Chart — Current State

[VERIFIED: `apps/dashboard/views.py`, `frontend/src/widgets/dashboard/`]

**Existing dashboard views** (from `apps/dashboard/views.py:27–96`):
- `DashboardApiView` (base) — uses `IsOrgScoped`, reads `dashboard_cache_key`, `cache_get`/`cache_set`
- `KpisView`, `SentimentView`, `TopPerformingView`, `HighlightsView`, `YourStoreView`
- **No canonical tag chart exists yet.** Phase 25 adds `DashboardTagPolarityView`.

**Dashboard React composition** (`DashboardWidget.tsx:206–263`):
- Renders `TopPerformingSection` OR `YourStore`, plus `SentimentDonut`, in a CSS grid
- The new `TagPolarityChart` should be added as a third card below the two-column grid, OR inserted into the grid as a third column

**Recharts import pattern** (verified in `TopPerformingSection.tsx:1–10`):
```typescript
import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
```
Phase 25 needs `Legend` in addition: `import { ..., Legend } from "recharts"` — `Legend` is part of recharts core, already installed.

**Tag polarity aggregation query** — No existing query exists. The cleanest no-N+1 approach is a single `ReviewTag` aggregate query with `annotate(positive_count=Count(..., filter=Q(polarity="positive")), negative_count=Count(..., filter=Q(polarity="negative")))` grouped by `canonical_tag_id`. This is 1 query for the data + optionally 1 cache write = ≤2 queries.

**Dashboard caching:** Existing views use `DashboardApiView.get()` which calls `dashboard_cache_key` + `cache_get`/`cache_set`. The new `DashboardTagPolarityView` should follow the same pattern. Cache key must include `org_id` (and `user_id` for isolation per the v0.4 DASH-C1 decision noted in STATE.md).

**TDASH-02 enforcement:** The aggregate query filters `canonical_tag__isnull=False` at the `ReviewTag` level — this means only `ReviewTag` rows with a canonical FK set are counted. Equivalently: `ReviewTag.objects.filter(canonical_tag__organisation_id=org_id, canonical_tag__isnull=False)`. The double filter is not needed — `canonical_tag__organisation_id=org_id` already implies `canonical_tag IS NOT NULL`.

### Verification 8: TagMergeJob Model Placement

[VERIFIED: `apps/reviews/models.py` is the correct location]

**Rationale:** `TagMergeJob` references `OrgCanonicalTag` (FK) which lives in `apps/reviews/models.py`. Placing `TagMergeJob` in the same file avoids cross-app FK imports. The `reviews` app already owns all canonical tag machinery.

**Migration considerations:**
- Next migration number: `0014_tagmergejob.py` (current latest is `0013_periodic_task_seed_polarity_reclassify.py`, verified)
- One migration per PR (§18)
- Index decisions for `TagMergeJob`:
  - `(organisation, status)` — for the `active/` endpoint query (find PENDING/IN_PROGRESS jobs for org)
  - `(organisation, created_at)` — for history ordering
  - `dismissed` field with `db_index=True` — for filtering dismissed jobs

**`TagMergeJob` model fields:**
```python
class TagMergeJob(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        IN_PROGRESS = "IN_PROGRESS", "In Progress"
        SUCCESS = "SUCCESS", "Success"
        FAILED = "FAILED", "Failed"

    organisation = models.ForeignKey("organisations.Organisation", on_delete=CASCADE, db_index=True)
    source_tag = models.ForeignKey(OrgCanonicalTag, null=True, on_delete=SET_NULL,
                                    related_name="+")  # null after source is deleted
    source_label = models.CharField(max_length=100)     # denormalized — source label before deletion
    target_tag = models.ForeignKey(OrgCanonicalTag, null=True, on_delete=SET_NULL,
                                    related_name="+")
    target_label = models.CharField(max_length=100)     # denormalized — for display after task runs
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    processed = models.PositiveIntegerField(default=0)
    total = models.PositiveIntegerField(default=0)
    error_message = models.TextField(blank=True, default="")
    dismissed = models.BooleanField(default=False, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=["organisation", "status"], name="tagmergejob_org_status_idx"),
            models.Index(fields=["organisation", "-created_at"], name="tagmergejob_org_date_idx"),
        ]
```

**Note on `source_tag` FK:** After the merge task runs, `source.delete()` is called. The `source_tag` FK uses `on_delete=SET_NULL` so the job record survives the deletion. The denormalized `source_label` field preserves the source name for display in the completed job record (used in completion toast and activity log).

---

## Common Pitfalls

### Pitfall 1: Using `_merge_group` directly for user-directed merge

**What goes wrong:** `_merge_group` always picks the winner as the row with the highest `review_count` (tie-broken by `created_at`). If the user-chosen target happens to have fewer reviews than the source, the wrong tag survives.

**Why it happens:** The function was written for Phase 23's automatic dedup, where "highest count = best representative" is the correct heuristic. D-06 mandates the opposite convention for human-directed merges.

**How to avoid:** Write a new `merge_canonical_tags(job_id)` service in `apps/reviews/services/tag_management.py`. Reuse the `ReviewTag.objects.filter(canonical_tag=source).update(canonical_tag=target)` FK-repoint pattern and `_refresh_review_counts` for count refresh, but pass explicit source/target IDs from the `TagMergeJob`.

**Warning signs:** If the merge service calls `_merge_group` with a label string, it's the wrong abstraction.

### Pitfall 2: `review_count` double-counting after merge

**What goes wrong:** Task sets `target.review_count = target.review_count + source.review_count` after the FK re-point. This double-counts because `_refresh_review_counts` counts the actual `ReviewTag` rows, not the old cached values.

**Why it happens:** The model comment (`apps/reviews/models.py:155`) warns against this, but it's tempting to do a quick naive sum.

**How to avoid:** Call `_refresh_review_counts(organisation_id=org_id)` after FK re-point and deletion. It recomputes from actual `ReviewTag` FK counts. Never add the old counts together.

### Pitfall 3: Race condition — concurrent merge jobs for same org

**What goes wrong:** Two admins trigger merges simultaneously. Both `TagMergeJob` rows are created, both tasks run concurrently, and the FK re-points conflict.

**Why it happens:** The Celery task is dispatched asynchronously; there's a window between job creation and lock acquisition.

**How to avoid:** (1) In the merge endpoint, check for active (PENDING/IN_PROGRESS) jobs before creating a new one — return HTTP 409 Conflict if one exists. (2) In the task, acquire `distributed_lock(f"lock:tag_merge:org:{org_id}", timeout=300, blocking=False)` before proceeding; if lock not acquired, exit and let the job retry.

**Warning signs:** Duplicate `ReviewTag.canonical_tag` assignments; `review_count` mismatch after merge completes.

### Pitfall 4: `ReviewTag` FK SET_NULL race if task fails mid-merge

**What goes wrong:** The task re-points FKs, then crashes before calling `source.delete()`. The source tag still exists, but some `ReviewTag` rows already point to the target. State is inconsistent.

**How to avoid:** Wrap the entire sequence (`FK re-point` + `source.delete()` + `_refresh_review_counts`) in `transaction.atomic()`. If any step fails, the transaction rolls back and the `TagMergeJob.status` stays as whatever it was before the atomic block (or is rolled back to FAILED if you update status inside the block after the FK work).

**Note:** `_refresh_review_counts` calls `bulk_update` which must be inside the same transaction so counts are consistent with the FK state.

### Pitfall 5: Rename silent-merge via case-insensitive collision

**What goes wrong:** User renames "Food Quality" to "food quality". The `UniqueConstraint` on `(organisation, label)` is case-sensitive at the DB level (PostgreSQL default text collation). Two distinct rows can exist — "Food Quality" and "food quality" — bypassing the uniqueness intent.

**Why it happens:** The database constraint uses the default case-sensitive equality.

**How to avoid:** The rename service must perform a case-insensitive duplicate check BEFORE saving:
```python
exists = OrgCanonicalTag.objects.filter(
    organisation_id=organisation_id,
    label__iexact=new_label,
).exclude(pk=tag.pk).exists()
if exists:
    raise ValidationError({"label": "A tag with that name already exists."})
```
Return HTTP 400 with the duplicate error message from D-04. NEVER silently merge.

### Pitfall 6: `TagMergeJob.source_tag` FK is null after task runs

**What goes wrong:** Polling code tries to read `job.source_tag.label` after the merge completes (source was deleted). This raises `RelatedObjectDoesNotExist` or returns `None`.

**Why it happens:** `source_tag = models.ForeignKey(..., on_delete=SET_NULL)` becomes null once `source.delete()` runs.

**How to avoid:** The `source_label` and `target_label` denormalized fields exist precisely for this reason. The serializer must use these fields for display, not the FK's label. Set them at `TagMergeJob` creation time (before the task runs).

### Pitfall 7: Dashboard query selecting ALL ReviewTag rows (N+1 risk)

**What goes wrong:** Dashboard selector iterates over canonical tags and fetches review counts per tag in a loop — N+1 queries.

**Why it happens:** Naive implementation: `for tag in OrgCanonicalTag.objects.filter(org=org): tag.review_tags.count()`.

**How to avoid:** Use a single grouped aggregate:
```python
ReviewTag.objects.filter(canonical_tag__organisation_id=org_id)
    .values("canonical_tag_id", ...)
    .annotate(positive_count=Count(...), negative_count=Count(...))
    .order_by("-total_count")[:10]
```
Add a `CaptureQueriesContext` test asserting ≤2 queries for the dashboard tag polarity endpoint.

---

## Code Examples

### `_refresh_review_counts` exact current signature

```python
# apps/reviews/services/finalise.py:285 [VERIFIED]
def _refresh_review_counts(*, organisation_id: int) -> None:
    counts = (
        ReviewTag.objects.filter(canonical_tag__organisation_id=organisation_id)
        .values("canonical_tag_id")
        .annotate(cnt=Count("id"))
    )
    count_map: dict[int, int] = {row["canonical_tag_id"]: row["cnt"] for row in counts}
    tags_to_update = []
    for tag in OrgCanonicalTag.objects.filter(organisation_id=organisation_id):
        tag.review_count = count_map.get(tag.pk, 0)
        tags_to_update.append(tag)
    if tags_to_update:
        OrgCanonicalTag.objects.bulk_update(tags_to_update, ["review_count"])
```

### `distributed_lock` exact signature

```python
# apps/common/locks.py:31 [VERIFIED]
@contextlib.contextmanager
def distributed_lock(
    key: str,
    timeout: int = 300,
    blocking: bool = False,
) -> Generator[bool, None, None]:
    # Usage:
    with distributed_lock(f"lock:tag_merge:org:{org_id}", timeout=300, blocking=False) as acquired:
        if not acquired:
            return  # another worker holds the lock
        # ... do work
```

### Existing factories to reuse for tests

```python
# apps/reviews/tests/factories.py [VERIFIED]
OrgCanonicalTagFactory(organisation=org, label="Food Quality",
                       polarity_type=OrgCanonicalTag.PolarityType.MIXED, review_count=10)
ReviewTagFactory(review=review, label="food quality", polarity="positive", canonical_tag=tag)
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| N/A — no manual merge existed | User-directed merge via Celery task (D-06) | Phase 25 (new) | Admin controls vocabulary without developer intervention |
| `review_count` incremented inline per-review | Aggregate refresh only via `_refresh_review_counts` | Phase 22 (D-03) | No double-counting on delete-then-bulk_create paths |
| N/A — no canonical FK | `ReviewTag.canonical_tag` nullable FK; rename is O(1) | Phase 22 (D-04) | All reads of canonical label resolve through JOIN; rename = 1 row update |
| Bar chart (all polarity) | Stacked bar: mixed tags show positive/negative split | Phase 25 (new) | Dashboard surfaces polarity nuance per canonical tag |

**Deprecated/outdated:**
- REQUIREMENTS.md `TMGT-03` wording ("update all mapped ReviewTag rows synchronously") is the superseded JSONB-era wording. The FK-only design (D-03) makes this a single `OrgCanonicalTag.label` update — the CONTEXT.md D-03 decision overrides the requirement text.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.3.3 + pytest-django 4.9.0 |
| Config file | `pyproject.toml:[tool.pytest.ini_options]` — `--ds=config.settings.test` |
| Quick run command | `pytest apps/reviews/tests/ apps/dashboard/tests/ -x -q` |
| Full suite command | `pytest --cov=apps --cov-fail-under=85 -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| TMGT-01 | Staff GET /admin/org/tags/ → redirect | unit | `pytest apps/reviews/tests/test_views.py::test_tags_page_staff_redirected -x` | ❌ Wave 0 |
| TMGT-01 | ORG_ADMIN GET /admin/org/tags/ → 200 | unit | `pytest apps/reviews/tests/test_views.py::test_tags_page_org_admin_ok -x` | ❌ Wave 0 |
| TMGT-02 | canonical tags list query count ≤ 3 | unit | `pytest apps/reviews/tests/test_views.py::test_canonical_tags_list_query_count -x` | ❌ Wave 0 |
| TMGT-02 | ordering by column works | unit | `pytest apps/reviews/tests/test_views.py::test_canonical_tags_ordering -x` | ❌ Wave 0 |
| TMGT-03 | rename updates only OrgCanonicalTag.label | unit | `pytest apps/reviews/tests/test_services.py::test_rename_updates_canonical_tag_label -x` | ❌ Wave 0 |
| TMGT-03 | rename rejects case-insensitive duplicate | unit | `pytest apps/reviews/tests/test_services.py::test_rename_rejects_iexact_duplicate -x` | ❌ Wave 0 |
| TMGT-03 | rename applies Title-Case normalization | unit | `pytest apps/reviews/tests/test_services.py::test_rename_title_case -x` | ❌ Wave 0 |
| TMGT-04 | merge endpoint returns 409 when active job exists | unit | `pytest apps/reviews/tests/test_views.py::test_merge_409_when_active_job -x` | ❌ Wave 0 |
| TMGT-05 | merge task FK re-point is single UPDATE | unit | `pytest apps/reviews/tests/test_services.py::test_merge_bulk_update_no_n_plus_one -x` | ❌ Wave 0 |
| TMGT-05 | merge task transaction.atomic rollback on failure | unit | `pytest apps/reviews/tests/test_services.py::test_merge_rollback_on_error -x` | ❌ Wave 0 |
| TMGT-05 | cross-org scoping: org A cannot merge org B tags | unit | `pytest apps/reviews/tests/test_services.py::test_merge_cross_org_blocked -x` | ❌ Wave 0 |
| TMGT-05 | dispatch_notification called on SUCCESS | unit | `pytest apps/reviews/tests/test_services.py::test_merge_dispatches_notification -x` | ❌ Wave 0 |
| TMGT-06 | poll endpoint returns active job for org | unit | `pytest apps/reviews/tests/test_views.py::test_tag_merge_job_active_endpoint -x` | ❌ Wave 0 |
| TMGT-06 | dismiss endpoint marks dismissed=True | unit | `pytest apps/reviews/tests/test_views.py::test_tag_merge_job_dismiss -x` | ❌ Wave 0 |
| TDASH-01 | tag polarity endpoint returns stacked counts | unit | `pytest apps/dashboard/tests/test_aggregations.py::test_tag_polarity_basic -x` | ❌ Wave 0 |
| TDASH-02 | aggregation excludes ReviewTag rows with null canonical_tag | unit | `pytest apps/dashboard/tests/test_aggregations.py::test_tag_polarity_excludes_null_canonical -x` | ❌ Wave 0 |
| TDASH-02 | tag polarity query count ≤ 2 | unit | `pytest apps/dashboard/tests/test_aggregations.py::test_tag_polarity_query_count -x` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `pytest apps/reviews/tests/ apps/dashboard/tests/ -x -q`
- **Per wave merge:** `pytest --cov=apps --cov-fail-under=85 -q`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `apps/reviews/tests/test_services.py` — extend with rename/merge service tests
- [ ] `apps/reviews/tests/test_views.py` — extend with canonical tag viewset + tag merge job tests
- [ ] `apps/reviews/tests/factories.py` — add `TagMergeJobFactory` (model not yet created)
- [ ] `apps/dashboard/tests/test_aggregations.py` — add tag polarity tests (extend existing file)
- [ ] No new `conftest.py` needed — existing `apps/dashboard/tests/conftest.py` provides org/shop fixtures

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | `@org_admin_required` on template view; `IsOrgAdmin` on API |
| V3 Session Management | no | Reuses existing session; no new auth token |
| V4 Access Control | yes | `IsOrgAdmin` permission; Staff 403 at view + sidebar; cross-org tag access blocked in service/selector |
| V5 Input Validation | yes | DRF serializer validates rename `label` (1–100 chars); explicit `target_id` validation in merge endpoint |
| V6 Cryptography | no | No new secrets or credentials |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Org A admin merges Org B's tags via direct API | Elevation of Privilege | Selector/service filters by `organisation_id`; `IsOrgAdmin` validates the user's own org |
| Staff user accesses Tags page via direct URL | Elevation of Privilege | `@org_admin_required` redirects Staff; `IsOrgAdmin` DRF permission returns 403 on API |
| Concurrent merge jobs corrupt FK state | Tampering | 409 Conflict check at job creation + `distributed_lock` in task; `transaction.atomic()` wrapping all FK mutations |
| Invalid `target_id` (wrong org) in merge payload | Tampering | Service fetches target with `organisation_id` filter; returns 404 if not found in caller's org |
| Rename silently merges duplicate label | Tampering | Case-insensitive duplicate check before save; HTTP 400 with clear error if collision found |
| Dismiss endpoint dismisses another org's job | Elevation of Privilege | `TagMergeJobViewSet` filters by `request.user.organisation_id`; `get_object()` returns 404 if wrong org |

---

## Environment Availability

Step 2.6: SKIPPED — no external tools or CLI utilities beyond the project's own codebase. Recharts and lucide-react are already installed. PostgreSQL and Redis are pre-existing project dependencies.

---

## Open Questions

1. **Dashboard placement of TagPolarityChart**
   - What we know: `DashboardWidget.tsx` has a two-column grid with `TopPerformingSection` (or `YourStore`) + `SentimentDonut`. The new chart is a third card.
   - What's unclear: Should it be a full-width third row below the grid, or inserted as a third column that collapses to a new row on narrower viewports?
   - Recommendation: Full-width third row (simplest, avoids breaking the existing grid's responsive behavior). The planner should specify placement in the implementation task.

2. **`TAG_MERGE_COMPLETE` notification type migration**
   - What we know: Adding a value to `TextChoices` changes the Python-layer enum but doesn't add a DB constraint. Django will generate a migration but it's a no-op at the DB level.
   - What's unclear: The migration file will still be generated (Django detects the change). Should it be combined with the `TagMergeJob` migration or kept separate?
   - Recommendation: Keep as separate migration (`0015_notification_type_tag_merge_complete.py`) for clean reversibility and clarity. Combine would save one migration file but obscures the purpose.

3. **Merge progress: `processed`/`total` granularity during task execution**
   - What we know: The UI expects `processed/total` counters. The single `ReviewTag.objects.filter(...).update(...)` call in the service runs as one SQL UPDATE — there is no per-row callback.
   - What's unclear: How to provide intermediate progress counts when the entire FK re-point is one atomic SQL statement?
   - Recommendation: Set `total = source.review_count` (known before the UPDATE) and `processed = result_of_update` (the count returned by `.update()`) in a single write after the UPDATE completes. The UI will show 0% while the task is running (indeterminate bar), then 100% when the job reaches SUCCESS. This matches the UI-SPEC's PENDING state treatment. If chunked progress is needed in future, split the UPDATE into batches — but that adds complexity and is out of scope for D-07.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `dashboard_tag_polarity` selector uses `ReviewTag` aggregate (not `OrgCanonicalTag.review_count`) for polarity split counts | Architecture Patterns §Pattern 4 | If `review_count` denormalized cache is used instead, the positive/negative split would be lost (it only stores total) |
| A2 | `TagPolarityChart` is added as a full-width third row in `DashboardWidget` below the existing two-column grid | Open Questions §1 | Minor layout change if planner chooses a different grid position |
| A3 | `TAG_MERGE_COMPLETE` notification type is added as a separate migration | Open Questions §2 | If combined, both migrations ship together — functionally equivalent |
| A4 | The merge service writes `processed = ReviewTag.objects.filter(...).update(...)` count (post-hoc) rather than batching | Open Questions §3 | If the API is expected to show real intermediate progress, the entire task architecture would need chunked batches |

---

## Sources

### Primary (HIGH confidence)

- `apps/reviews/models.py` — `OrgCanonicalTag` and `ReviewTag` field definitions, constraints, indexes [VERIFIED]
- `apps/reviews/services/finalise.py:194,285` — `_merge_group` and `_refresh_review_counts` exact signatures and logic [VERIFIED]
- `apps/common/locks.py:31` — `distributed_lock` signature [VERIFIED]
- `apps/reviews/tasks.py` — confirmed `merge_canonical_tags_task` does NOT yet exist [VERIFIED]
- `apps/reviews/selectors/canonical_tags.py` — existing selectors; no tag polarity or list selector yet [VERIFIED]
- `config/settings/base.py:120–132` — `CELERY_TASK_ROUTES`; `merge_canonical_tags_task` not yet registered [VERIFIED]
- `apps/notifications/models.py:23` — `NotificationType` choices; no `TAG_MERGE_COMPLETE` yet [VERIFIED]
- `apps/notifications/services/dispatch.py` — `dispatch_notification` signature [VERIFIED]
- `apps/accounts/permissions.py:27,44` — `IsOrgAdmin` and `org_admin_required` [VERIFIED]
- `templates/partials/sidebar_org.html:30,35` — `{% if user.role != "STAFF_ADMIN" %}` guard pattern [VERIFIED]
- `frontend/src/widgets/dashboard/TopPerformingSection.tsx` — Recharts `BarChart` import pattern [VERIFIED]
- `frontend/src/widgets/notif-bell/useNotifications.ts` — HTTP polling hook pattern [VERIFIED]
- `frontend/src/entrypoints/audit-log.tsx` — Vite entrypoint + bootstrap-data pattern [VERIFIED]
- `frontend/src/widgets/audit-log/AuditLogWidget.tsx` — layout pattern [VERIFIED]
- `frontend/src/widgets/action-items/MergeModal.tsx` — two-step modal pattern [VERIFIED]
- `frontend/vite.config.ts` — entrypoint registration pattern [VERIFIED]
- `apps/reviews/tests/factories.py:38,48` — `OrgCanonicalTagFactory`, `ReviewTagFactory` definitions [VERIFIED]
- `apps/reviews/migrations/` — latest migration is `0013_periodic_task_seed_polarity_reclassify.py` [VERIFIED]
- `apps/dashboard/views.py` — no canonical tag view exists yet [VERIFIED]
- `.planning/config.json` — `nyquist_validation: true`, `security_enforcement` not present (defaults to enabled) [VERIFIED]

### Secondary (MEDIUM confidence)

- `REQUIREMENTS.md TMGT-03` wording vs `CONTEXT.md D-03` — CONTEXT.md supersedes requirement text for rename scope (FK-only, not all ReviewTag rows) [CITED: project docs]

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries verified installed; no new packages
- Architecture: HIGH — all primitives verified in codebase; patterns confirmed
- Pitfalls: HIGH — traced from actual code logic (merge winner selection, review_count invariant, SET_NULL race)
- Testing: HIGH — existing query-count test shape verified from `test_views.py:193`

**Research date:** 2026-06-16
**Valid until:** 2026-07-16 (stable project; 30-day validity)
