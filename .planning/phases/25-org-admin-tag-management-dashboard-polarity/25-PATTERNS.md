# Phase 25: Org Admin Tag Management & Dashboard Polarity - Pattern Map

**Mapped:** 2026-06-16
**Files analyzed:** 22 new/modified files
**Analogs found:** 22 / 22

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `apps/reviews/models.py` (add `TagMergeJob`) | model | CRUD | `apps/reviews/models.py` `Review.EnrichmentStatus` + `TimeStampedModel` | exact (same file, same TextChoices + FK pattern) |
| `apps/reviews/migrations/0014_tagmergejob.py` | migration | — | `apps/reviews/migrations/0013_periodic_task_seed_polarity_reclassify.py` | role-match |
| `apps/reviews/services/tag_management.py` (new) | service | CRUD | `apps/reviews/services/finalise.py` `_merge_group` + `_refresh_review_counts` | role-match (primitives reused, winner logic differs) |
| `apps/reviews/selectors/canonical_tags.py` (extend) | selector | CRUD | `apps/reviews/selectors/canonical_tags.py` `get_org_vocabulary` | exact (same file, same pattern) |
| `apps/reviews/tasks.py` (add `merge_canonical_tags_task`) | task | event-driven | `apps/reviews/tasks.py` `finalize_canonical_tags_task` | exact (same file, same queue, same thin-wrapper pattern) |
| `apps/reviews/serializers.py` (extend) | serializer | request-response | `apps/common/views.py` `AuditLogReadSerializer` (inferred from viewset) | role-match |
| `apps/reviews/views.py` (add `OrgCanonicalTagViewSet`, `TagMergeJobViewSet`) | controller | request-response | `apps/common/views.py` `AuditLogViewSet` | exact (same ListModelMixin + GenericViewSet, IsOrgAdmin, pagination) |
| `apps/reviews/urls.py` (extend) | route | request-response | existing `apps/reviews/urls.py` | exact |
| `apps/dashboard/selectors/aggregations.py` (add `dashboard_tag_polarity`) | selector | CRUD | `apps/dashboard/selectors/aggregations.py` `dashboard_kpis` / `dashboard_sentiment_distribution` | exact (same file, same grouped-annotate pattern) |
| `apps/dashboard/views.py` (add `DashboardTagPolarityView`) | controller | request-response | `apps/dashboard/views.py` `KpisView` / `SentimentView` subclasses of `DashboardApiView` | exact (same file, same subclass pattern) |
| `apps/dashboard/urls.py` (extend) | route | request-response | existing `apps/dashboard/urls.py` | role-match |
| `apps/notifications/models.py` (add `TAG_MERGE_COMPLETE`) | model | event-driven | `apps/notifications/models.py` `NotificationType.TextChoices` | exact (same file, same TextChoices extension) |
| `config/settings/base.py` (add Celery route) | config | — | `config/settings/base.py` `CELERY_TASK_ROUTES` block | exact |
| `templates/org_admin/tags.html` | template | request-response | `templates/org-admin/audit-log.html` (referenced in entrypoint) | role-match |
| `templates/partials/sidebar_org.html` (extend) | template | — | `templates/partials/sidebar_org.html` lines 30–41 existing `{% if user.role != "STAFF_ADMIN" %}` guards | exact |
| `frontend/vite.config.ts` (add entrypoint) | config | — | `frontend/vite.config.ts` `"audit-log"` entry (line 35) | exact |
| `frontend/src/entrypoints/tag-management.tsx` | entrypoint | — | `frontend/src/entrypoints/audit-log.tsx` | exact |
| `frontend/src/widgets/tag-management/TagManagementWidget.tsx` | component | request-response | `frontend/src/widgets/audit-log/AuditLogWidget.tsx` | exact (layout pattern) |
| `frontend/src/widgets/tag-management/TagMergeModal.tsx` | component | request-response | `frontend/src/widgets/action-items/MergeModal.tsx` | exact (two-step pick/confirm pattern) |
| `frontend/src/widgets/tag-management/useMergeProgress.ts` | hook | event-driven | `frontend/src/widgets/notif-bell/useNotifications.ts` | exact (setInterval + clearInterval cleanup pattern, 2s instead of 60s) |
| `frontend/src/widgets/tag-management/MergeProgressBanner.tsx` | component | event-driven | `frontend/src/widgets/notif-bell/useNotifications.ts` (hook) + UI-SPEC Surface 4 | role-match (no direct analog; composes hook + banner markup) |
| `frontend/src/widgets/dashboard/TagPolarityChart.tsx` | component | request-response | `frontend/src/widgets/dashboard/TopPerformingSection.tsx` | exact (ResponsiveContainer + BarChart + recharts pattern) |

---

## Pattern Assignments

---

### `apps/reviews/models.py` — add `TagMergeJob` (model, CRUD)

**Analog:** `apps/reviews/models.py` — `Review.EnrichmentStatus` TextChoices + FK pattern (lines 28–33); `TimeStampedModel` inheritance.

**Why closest:** Same file, same project. `Review` uses identical `TextChoices` for PENDING/IN_PROGRESS/SUCCESS/FAILED status tracking with `select_for_update` idempotency. `OrgCanonicalTag` already shows the FK + `on_delete=SET_NULL` pattern used for the source tag.

**TextChoices + TimeStampedModel pattern** (`apps/reviews/models.py` lines 20–33, 127–165):
```python
class Review(TimeStampedModel):
    class EnrichmentStatus(models.TextChoices):
        PENDING = "PENDING", "Pending"
        IN_PROGRESS = "IN_PROGRESS", "In Progress"
        SUCCESS = "SUCCESS", "Success"
        FAILED = "FAILED", "Failed"
```

**Complete `TagMergeJob` model to add** (after `OrgCanonicalTag` in `apps/reviews/models.py`):
```python
class TagMergeJob(TimeStampedModel):
    """Durable record of a user-initiated canonical tag merge (D-08).

    source_tag FK becomes null after the merge (on_delete=SET_NULL — source is deleted).
    source_label / target_label are denormalized for display after deletion.
    Poll endpoint filters by (organisation, dismissed, status) using tagmergejob_org_status_idx.
    """

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        IN_PROGRESS = "IN_PROGRESS", "In Progress"
        SUCCESS = "SUCCESS", "Success"
        FAILED = "FAILED", "Failed"

    organisation = models.ForeignKey(
        "organisations.Organisation",
        on_delete=models.CASCADE,
        db_index=True,
        related_name="tag_merge_jobs",
    )
    source_tag = models.ForeignKey(
        "reviews.OrgCanonicalTag",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    source_label = models.CharField(max_length=100)  # denormalized — source deleted on success
    target_tag = models.ForeignKey(
        "reviews.OrgCanonicalTag",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    target_label = models.CharField(max_length=100)  # denormalized for display
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    processed = models.PositiveIntegerField(default=0)
    total = models.PositiveIntegerField(default=0)
    error_message = models.TextField(blank=True, default="")
    dismissed = models.BooleanField(default=False, db_index=True)

    class Meta:
        indexes = [
            models.Index(
                fields=["organisation", "status"],
                name="tagmergejob_org_status_idx",
            ),
            models.Index(
                fields=["organisation", "-created_at"],
                name="tagmergejob_org_date_idx",
            ),
        ]
```

**Critical invariant** (from `apps/reviews/models.py:155` comment pattern on `OrgCanonicalTag.review_count`): never include `review_count` in `bulk_update` field lists unless inside `_refresh_review_counts`. Set `source_label` and `target_label` at `TagMergeJob` creation time (before the Celery task runs) — reading `source_tag.label` after the merge raises `RelatedObjectDoesNotExist`.

---

### `apps/reviews/services/tag_management.py` — new service (service, CRUD)

**Analog:** `apps/reviews/services/finalise.py` lines 194–231 (`_merge_group`), lines 285–313 (`_refresh_review_counts`).

**Why closest:** The FK re-point pattern (`ReviewTag.objects.filter(canonical_tag=loser).update(canonical_tag=winner)`) at line 221 is the exact operation the manual merge reuses. `_refresh_review_counts` at line 285 is called verbatim after FK re-point. **Critical difference:** `_merge_group` picks winner by `review_count` (line 216) — the manual merge must NOT call `_merge_group`. Use the FK re-point pattern directly with explicit source/target from `TagMergeJob`.

**FK re-point pattern to replicate** (`apps/reviews/services/finalise.py` lines 219–222):
```python
# Inside transaction.atomic(), after select_for_update() on candidates:
ReviewTag.objects.filter(canonical_tag=loser).update(canonical_tag=winner)
loser.delete()
```

**`_refresh_review_counts` exact signature** (`apps/reviews/services/finalise.py` lines 285–313):
```python
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

**`distributed_lock` exact signature** (`apps/common/locks.py` line 31):
```python
@contextlib.contextmanager
def distributed_lock(
    key: str,
    timeout: int = 300,
    blocking: bool = False,
) -> Generator[bool, None, None]:
    ...

# Usage (non-blocking — exit if lock held, §7.6):
with distributed_lock(f"lock:tag_merge:org:{org_id}", timeout=300, blocking=False) as acquired:
    if not acquired:
        return  # another worker holds the lock
```

**Core service structure** (adapts `_merge_group` pattern, winner = user-chosen target per D-06):
```python
# apps/reviews/services/tag_management.py
from __future__ import annotations
import logging
from django.core.exceptions import ValidationError
from django.db import transaction
from apps.reviews.models import OrgCanonicalTag, ReviewTag, TagMergeJob
from apps.reviews.services.finalise import _refresh_review_counts
from apps.common.locks import distributed_lock

logger = logging.getLogger(__name__)


def rename_canonical_tag(*, tag: OrgCanonicalTag, new_label: str,
                          organisation_id: int) -> OrgCanonicalTag:
    """O(1) label rename. Rejects case-insensitive duplicates (D-04).

    Title-Case normalization applied. No ReviewTag rows touched (D-03/FK-only).
    """
    new_label = new_label.strip().title()
    if not (1 <= len(new_label) <= 100):
        raise ValidationError({"label": "Label must be 1–100 characters."})
    # Case-insensitive duplicate check (Pitfall 5 — DB constraint is case-sensitive)
    exists = (
        OrgCanonicalTag.objects
        .filter(organisation_id=organisation_id, label__iexact=new_label)
        .exclude(pk=tag.pk)
        .exists()
    )
    if exists:
        raise ValidationError({"label": "A tag with that name already exists."})
    tag.label = new_label
    tag.save(update_fields=["label", "updated_at"])
    return tag


def create_merge_job(*, source_tag: OrgCanonicalTag, target_id: int,
                      organisation_id: int) -> TagMergeJob:
    """Create a TagMergeJob and enqueue the Celery task. Returns the job.

    Raises ValidationError on: target not in org, target == source, or
    an active (PENDING/IN_PROGRESS) job already exists (Pitfall 3 → HTTP 409).
    """
    ...  # validation + TagMergeJob.objects.create() + task.delay(job.pk)


@transaction.atomic
def merge_canonical_tags(*, job_id: int) -> None:
    """Execute a user-initiated tag merge. Called by merge_canonical_tags_task.

    Winner = user-chosen target (D-06 — NOT higher review_count).
    Single bulk UPDATE for FK re-point (§6.10, no N+1).
    _refresh_review_counts() after deletion (D-03 derive-on-read invariant).
    """
    job = TagMergeJob.objects.select_for_update().get(pk=job_id)
    if job.status not in (TagMergeJob.Status.PENDING, TagMergeJob.Status.IN_PROGRESS):
        return  # idempotent no-op (§12.4 Layer 3)

    org_id = job.organisation_id
    source = OrgCanonicalTag.objects.get(pk=job.source_tag_id, organisation_id=org_id)
    target = OrgCanonicalTag.objects.get(pk=job.target_tag_id, organisation_id=org_id)

    job.status = TagMergeJob.Status.IN_PROGRESS
    job.total = source.review_count  # snapshot before deletion
    job.save(update_fields=["status", "total", "updated_at"])

    # Single bulk UPDATE — one query (§6.10). FK re-point BEFORE delete (Pitfall 4).
    processed = ReviewTag.objects.filter(canonical_tag=source).update(canonical_tag=target)
    source.delete()
    _refresh_review_counts(organisation_id=org_id)  # NOT naive sum (D-03)

    job.processed = processed
    job.status = TagMergeJob.Status.SUCCESS
    job.save(update_fields=["status", "processed", "updated_at"])
    # dispatch_notification(...) after atomic block succeeds
```

---

### `apps/reviews/selectors/canonical_tags.py` — extend (selector, CRUD)

**Analog:** `apps/reviews/selectors/canonical_tags.py` — `get_org_vocabulary` (lines 11–26), `get_duplicate_canonical_tag_groups` (lines 29–47).

**Why closest:** Same file. `get_org_vocabulary` shows the exact pattern: `OrgCanonicalTag.objects.filter(organisation_id=...)` with `.order_by()` and bounded slice — one query.

**Existing pattern to copy** (lines 11–26):
```python
def get_org_vocabulary(*, organisation_id: int, limit: int) -> list[str]:
    return list(
        OrgCanonicalTag.objects
        .filter(organisation_id=organisation_id)
        .order_by("-review_count")
        .values_list("label", flat=True)[:limit]
    )
```

**New `list_canonical_tags_for_org` to add** (queryset for `OrgCanonicalTagViewSet.get_queryset`):
```python
def list_canonical_tags_for_org(*, organisation_id: int) -> QuerySet[OrgCanonicalTag]:
    """Return all org canonical tags for the paginated list endpoint.

    One query (no prefetch needed — no nested FKs). Ordering is handled by
    OrderingFilter in the viewset; default ordering set on the QuerySet.
    Query ceiling: 1 COUNT + 1 SELECT = 2 queries max (§6.9).
    """
    return (
        OrgCanonicalTag.objects
        .filter(organisation_id=organisation_id)
        .order_by("-review_count", "label")
    )
```

---

### `apps/reviews/tasks.py` — add `merge_canonical_tags_task` (task, event-driven)

**Analog:** `apps/reviews/tasks.py` `finalize_canonical_tags_task` (lines 237–302).

**Why closest:** Same file, same `tag-merge` queue, same thin-wrapper pattern (`from apps.reviews.services.finalise import ...` inside the function body per §12.3). Also uses per-org `distributed_lock` in the service (not the task).

**Pattern to copy** (`finalize_canonical_tags_task` lines 237–302):
```python
@shared_task(  # type: ignore[misc]
    bind=True,
    max_retries=3,
    autoretry_for=(Exception,),
    retry_backoff=60,
    retry_backoff_max=600,
    retry_jitter=True,
)
def finalize_canonical_tags_task(
    self: Any, *, organisation_id: int, shop_id: int
) -> dict[str, Any]:
    from apps.reviews.services.finalise import run_finalise_canonical_tags
    task_id = self.request.id
    attempt = self.request.retries + 1
    logger.info(
        "finalize_canonical_tags_task.start task_id=%s organisation_id=%s ...",
        task_id, organisation_id, shop_id, attempt,
    )
    try:
        result = run_finalise_canonical_tags(organisation_id=organisation_id, shop_id=shop_id)
    except Exception as exc:
        logger.error("finalize_canonical_tags_task.error ...", exc_info=True)
        raise
    ...
    return result
```

**New task signature** (thin wrapper — business logic stays in service):
```python
@shared_task(  # type: ignore[misc]
    bind=True,
    max_retries=3,
    autoretry_for=(Exception,),
    retry_backoff=60,
    retry_backoff_max=600,
    retry_jitter=True,
)
def merge_canonical_tags_task(self: Any, job_id: int) -> None:
    """Phase 25 — User-directed canonical tag merge. Routes to tag-merge queue.

    Thin wrapper — all business logic in merge_canonical_tags() service.
    Per-org distributed_lock acquired inside the service (§7.6).
    job_id (not model instance) per §12.3.
    """
    from apps.reviews.services.tag_management import merge_canonical_tags
    task_id = self.request.id
    attempt = self.request.retries + 1
    logger.info(
        "merge_canonical_tags_task.start task_id=%s job_id=%s attempt=%s",
        task_id, job_id, attempt,
    )
    try:
        merge_canonical_tags(job_id=job_id)
    except Exception as exc:
        logger.error(
            "merge_canonical_tags_task.error task_id=%s job_id=%s attempt=%s error=%r",
            task_id, job_id, attempt, exc, exc_info=True,
        )
        raise
    logger.info(
        "merge_canonical_tags_task.success task_id=%s job_id=%s attempt=%s",
        task_id, job_id, attempt,
    )
```

**Celery route to add in `config/settings/base.py`** (alongside line 128 `finalize_canonical_tags_task` entry):
```python
"apps.reviews.tasks.merge_canonical_tags_task": {"queue": "tag-merge"},
```

---

### `apps/reviews/views.py` — add `OrgCanonicalTagViewSet` + `TagMergeJobViewSet` (controller, request-response)

**Analog:** `apps/common/views.py` `AuditLogViewSet` (lines 221–248).

**Why closest:** Identical composition — `mixins.ListModelMixin + viewsets.GenericViewSet`, `IsOrgAdmin`/`IsOrgScoped` permission, `DefaultPageNumberPagination`, `queryset = Model.objects.none()` for router introspection, `get_queryset()` calling a selector with `organisation_id`.

**Pattern to copy** (`apps/common/views.py` lines 221–248):
```python
class AuditLogViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsOrgScoped]  # noqa: RUF012
    serializer_class = AuditLogReadSerializer
    pagination_class = AuditLogCursorPagination
    filter_backends = [DjangoFilterBackend]  # noqa: RUF012
    filterset_class = AuditLogFilterSet
    throttle_scope = "audit_log_list"
    throttle_classes = [ScopedRateThrottle]  # noqa: RUF012
    queryset = AuditLog.objects.none()

    def get_queryset(self):
        user = self.request.user
        org_id = getattr(user, "organisation_id", None)
        if org_id is None:
            return AuditLog.objects.none()
        ...
        return list_audit_logs_for_org(organisation_id=org_id)
```

**New `OrgCanonicalTagViewSet`** (use `IsOrgAdmin` not `IsOrgScoped` — Staff excluded per D-01):
```python
from rest_framework import mixins, viewsets, status
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter
from rest_framework.response import Response
from apps.accounts.permissions import IsOrgAdmin
from apps.common.pagination import DefaultPageNumberPagination

class OrgCanonicalTagViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsOrgAdmin]  # noqa: RUF012  — Staff gets 403 (D-01)
    serializer_class = OrgCanonicalTagReadSerializer
    pagination_class = DefaultPageNumberPagination
    filter_backends = [OrderingFilter]  # noqa: RUF012
    ordering_fields = ["label", "review_count", "created_at"]
    ordering = ["-review_count"]
    queryset = OrgCanonicalTag.objects.none()

    def get_queryset(self):
        org_id = getattr(self.request.user, "organisation_id", None)
        if org_id is None:
            return OrgCanonicalTag.objects.none()
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
        job = create_merge_job(
            source_tag=source,
            target_id=request.data.get("target_id"),
            organisation_id=request.user.organisation_id,
        )
        return Response({"job_id": job.pk}, status=status.HTTP_201_CREATED)
```

**Permission class pattern** (`apps/accounts/permissions.py` lines 27–39):
```python
class IsOrgAdmin(BasePermission):
    message = "Organisation Admin role required."

    def has_permission(self, request: Request, view: APIView) -> bool:
        user = request.user
        if not user or not user.is_authenticated:
            return False
        return bool(
            getattr(user, "role", None) == User.Role.ORG_ADMIN
            and getattr(user, "organisation_id", None) is not None
        )
```

---

### `templates/org_admin/tags.html` + Django view function (template, request-response)

**Analog:** `apps/common/views.py` `audit_log_view` (lines 251–296); the template it renders (referenced via the entrypoint `audit-log.tsx` as `#audit-log-root`).

**Why closest:** The audit log view is the only ORG_ADMIN-only template view with a React widget root div + `<script type="application/json">` bootstrap data pattern. The Tags page is simpler (no bootstrap data beyond CSRF).

**Template view decorator pattern** (`apps/accounts/permissions.py` lines 42–65):
```python
@org_admin_required   # NOT @login_required — Staff must get 403, not just login redirect (D-01)
def tags_page_view(request: HttpRequest) -> HttpResponse:
    """Tags management page. ORG_ADMIN only — Staff redirected by @org_admin_required."""
    return render(request, "org_admin/tags.html", {})
```

**CRITICAL:** Use `@org_admin_required` (line 42), NOT `@login_required` (which is used by `audit_log_view` at line 251 because Staff can access it). `@org_admin_required` redirects any non-ORG_ADMIN to `/login/`.

**Template structure** (mirrors `audit-log.html` referenced by `audit-log.tsx`):
```html
{% extends "base.html" %}
{% block content %}
<div id="tag-management-root" data-mounted></div>
{% endblock %}
```

No `<script type="application/json">` bootstrap data needed — all data fetched via API (UI-SPEC Surface 1).

---

### `templates/partials/sidebar_org.html` — add Tags nav item (template, —)

**Analog:** `templates/partials/sidebar_org.html` lines 30–40 — the `{% if user.role != "STAFF_ADMIN" %}` guard blocks.

**Why closest:** The exact pattern for ORG_ADMIN-only nav items. Line 35 shows another `{% if %}` group. Line 41 shows the Activity Log item directly before where Tags should go.

**Existing guard pattern** (lines 30–31, 35–41):
```html
{% if user.role != "STAFF_ADMIN" %}
  {% include "partials/_nav_item.html" with href="/admin/org/shops/" icon="store" label="Shops" %}
{% endif %}
...
{% include "partials/_nav_item.html" with href="/admin/org/activity-log/" icon="clock" label="Activity Log" %}
```

**New Tags nav item to add after line 41** (Activity Log):
```html
{% if user.role != "STAFF_ADMIN" %}
  {% include "partials/_nav_item.html" with href="/admin/org/tags/" icon="tags" label="Tags" %}
{% endif %}
```

Icon: `tags` (lucide two-tags glyph, consistent with `icon="store"` / `icon="clock"` pattern).

---

### `apps/dashboard/selectors/aggregations.py` — add `dashboard_tag_polarity` (selector, CRUD)

**Analog:** `apps/dashboard/selectors/aggregations.py` lines 65–70 `dashboard_kpis` + lines 28–57 `_base_qs` / `_date_only_qs` helpers.

**Why closest:** Same file. All dashboard selectors use single grouped `values().annotate()` queries — no Python loops over querysets. The `_base_qs` pattern shows the canonical `Review.objects.active().filter(organisation_id=org_id)` base. The tag polarity query starts from `ReviewTag`, not `Review`, but uses the same grouped-annotate-with-Q-filter approach verified in `finalise.py:_refresh_review_counts`.

**Grouped annotate pattern from the file** (`dashboard_kpis` uses `aggregate()`, but `_refresh_review_counts` in `finalise.py` lines 292–298 shows `values().annotate()` for multi-row grouped aggregates):
```python
counts = (
    ReviewTag.objects.filter(canonical_tag__organisation_id=organisation_id)
    .values("canonical_tag_id")
    .annotate(cnt=Count("id"))
)
```

**New `dashboard_tag_polarity` selector**:
```python
from django.db.models import Count, Q
from apps.reviews.models import OrgCanonicalTag, ReviewTag

def dashboard_tag_polarity(*, organisation_id: int, limit: int = 10) -> dict[str, Any]:
    """Return top-N canonical tags with positive/negative split (TDASH-01, TDASH-02).

    TDASH-02: canonical_tag__organisation_id=org_id already implies IS NOT NULL.
    No N+1: one ReviewTag aggregate query (1 query total, ≤2 with cache write).
    query_count ceiling: ≤2 (data query + optional cache write).
    """
    rows = list(
        ReviewTag.objects
        .filter(canonical_tag__organisation_id=organisation_id)
        .values(
            "canonical_tag_id",
            "canonical_tag__label",
            "canonical_tag__polarity_type",
        )
        .annotate(
            positive_count=Count("id", filter=Q(polarity="positive")),
            negative_count=Count("id", filter=Q(polarity="negative")),
            total_count=Count("id"),
        )
        .order_by("-total_count")[: limit + 1]
    )
    has_more = len(rows) > limit
    return {
        "tags": [
            {
                "label": r["canonical_tag__label"],
                "polarity_type": r["canonical_tag__polarity_type"],
                "positive_count": r["positive_count"],
                "negative_count": r["negative_count"],
                "total_count": r["total_count"],
            }
            for r in rows[:limit]
        ],
        "has_more": has_more,
    }
```

---

### `apps/dashboard/views.py` — add `DashboardTagPolarityView` (controller, request-response)

**Analog:** `apps/dashboard/views.py` `KpisView` (lines 60–66) subclassing `DashboardApiView` (lines 27–57).

**Why closest:** Exact same file. All dashboard API views are one-line subclasses of `DashboardApiView` that override `_fetch`. `DashboardApiView.get()` handles org scoping, cache read/write, and `IsOrgScoped` permission automatically.

**Pattern to copy** (lines 27–66):
```python
class DashboardApiView(APIView):
    permission_classes = [IsOrgScoped]  # noqa: RUF012
    endpoint_name: str = ""

    def get(self, request: Request) -> Response:
        user: User = request.user
        org_id: int = user.organisation_id
        key = dashboard_cache_key(
            endpoint=self.endpoint_name,
            org_id=org_id, user_id=int(user.pk), params=params,
        )
        cached = cache_get(key)
        if cached is not None:
            return Response(cached)
        data = self._fetch(org_id=org_id, params=params, user=user)
        cache_set(key, data, ttl=DASHBOARD_TTL_SECONDS)
        return Response(data)

class KpisView(DashboardApiView):
    endpoint_name = "kpis"

    def _fetch(self, *, org_id, params, user):
        return dashboard_kpis(org_id=org_id, params=params)
```

**New view** (tag polarity takes no filter params — it aggregates across the org's full canonical vocabulary):
```python
class DashboardTagPolarityView(DashboardApiView):
    endpoint_name = "tag-polarity"

    def _fetch(
        self, *, org_id: int, params: DashboardFilterParams, user: User
    ) -> dict[str, Any] | None:
        return dashboard_tag_polarity(organisation_id=org_id)
```

Note: `params` is passed by the base class — `dashboard_tag_polarity` ignores date/shop filters per TDASH-02 (aggregates the full canonical vocabulary, not a filtered window).

---

### `apps/notifications/models.py` — add `TAG_MERGE_COMPLETE` (model, event-driven)

**Analog:** `apps/notifications/models.py` lines 22–26 `NotificationType.TextChoices`.

**Why closest:** Exact same file. Extending a `TextChoices` class is a one-line addition.

**Existing pattern** (lines 22–27):
```python
class Notification(TimeStampedModel):
    class NotificationType(models.TextChoices):
        NEW_REVIEW = "new_review", "New Review"
        NEW_ACTION_ITEM = "new_action_item", "New Action Item"
        ACTION_ITEM_ASSIGNED = "action_item_assigned", "Action Item Assigned"
```

**Addition:**
```python
        TAG_MERGE_COMPLETE = "tag_merge_complete", "Tag Merge Complete"
```

Requires migration `0015_notification_type_tag_merge_complete.py` (separate from `TagMergeJob` migration per Open Question 2 resolution — clean reversibility). Django generates this migration for the Python choices layer even though it's a no-op DB constraint change.

**`dispatch_notification` call pattern** (`apps/notifications/services/dispatch.py` lines 25–37):
```python
dispatch_notification(
    organisation_id=job.organisation_id,
    notification_type="tag_merge_complete",
    title=f'Tag "{job.source_label}" merged into "{job.target_label}"',
    target_url="/admin/org/tags/",
    org_admins_only=True,  # merge is ORG_ADMIN-only feature (D-01)
)
```

Call this AFTER the `transaction.atomic()` block in `merge_canonical_tags()` — notifications are outside the merge transaction to avoid rollback on notification failure.

---

### `frontend/vite.config.ts` — add `tag-management` entrypoint (config, —)

**Analog:** `frontend/vite.config.ts` line 35 `"audit-log"` entry.

**Pattern to copy** (lines 35–36):
```typescript
"audit-log": resolve(__dirname, "src/entrypoints/audit-log.tsx"),
```

**Addition** (after the `"audit-log"` line):
```typescript
"tag-management": resolve(__dirname, "src/entrypoints/tag-management.tsx"),
```

---

### `frontend/src/entrypoints/tag-management.tsx` (entrypoint, —)

**Analog:** `frontend/src/entrypoints/audit-log.tsx` (entire file, 33 lines).

**Why closest:** Exact pattern. `mount()` function checks `#<widget>-root`, sets `dataset.mounted = "1"`, calls `createRoot(...).render()`. Registers on both `mount()` immediately and `document.addEventListener("turbo:load", mount)`.

**Full pattern to clone** (`frontend/src/entrypoints/audit-log.tsx` lines 1–33):
```typescript
// Phase 21-04 — Audit log entrypoint.
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { AuditLogWidget } from "../widgets/audit-log/AuditLogWidget";
import type { ActorOption } from "../widgets/audit-log/types";

function readJson<T>(elementId: string, fallback: T): T {
  const el = document.getElementById(elementId);
  if (!el || !el.textContent) return fallback;
  try {
    return JSON.parse(el.textContent) as T;
  } catch {
    return fallback;
  }
}

function mount() {
  const root = document.getElementById("audit-log-root");
  if (!root || root.dataset.mounted) return;
  root.dataset.mounted = "1";
  const userRole = root.dataset.userRole ?? "STAFF_ADMIN";
  const actors = readJson<ActorOption[]>("audit-log-actors-data", []);
  createRoot(root).render(
    <StrictMode>
      <AuditLogWidget userRole={userRole} actors={actors} />
    </StrictMode>,
  );
}

mount();
document.addEventListener("turbo:load", mount);
```

**Adaptation for tag-management** — `readJson` can be retained (future use) or omitted since the Tags page needs no bootstrap data. Replace `#audit-log-root` with `#tag-management-root`, import `TagManagementWidget`:
```typescript
function mount() {
  const root = document.getElementById("tag-management-root");
  if (!root || root.dataset.mounted) return;
  root.dataset.mounted = "1";
  createRoot(root).render(
    <StrictMode>
      <TagManagementWidget />
    </StrictMode>,
  );
}
mount();
document.addEventListener("turbo:load", mount);
```

---

### `frontend/src/widgets/tag-management/TagManagementWidget.tsx` + `TagTable.tsx` (component, request-response)

**Analog:** `frontend/src/widgets/audit-log/AuditLogWidget.tsx` (layout and pagination pattern).

**Why closest:** RESEARCH.md Verification 3 confirms this is the explicit layout model. The outer `<div className="space-y-4">` + `<h1 className="text-[20px] font-semibold text-ink">` + border card pattern is described as "mirrors AuditLogWidget exactly" in UI-SPEC Surface 1.

**Layout pattern** (from RESEARCH.md Verification 3 + UI-SPEC):
```tsx
// TagManagementWidget.tsx outer shell
<div className="space-y-4">
  <h1 className="text-[20px] font-semibold text-ink">Tags</h1>
  <div className="border border-line rounded-card overflow-hidden">
    <TagTable ... />
    <nav aria-label="Pagination"
         className="bg-[#FBFBFB] border-t border-line px-4 py-3 text-[12px] text-muted">
      {/* prev/next pagination */}
    </nav>
  </div>
  {/* MergeProgressBanner above the table card — only when active job exists */}
</div>
```

**DataTable usage pattern** (from RESEARCH.md — `DataTable<OrgCanonicalTagRow>` with `renderRowActions`):
```tsx
import { DataTable } from "../data-table/DataTable";
// DataTable component located at frontend/src/widgets/data-table/DataTable.tsx
<DataTable<OrgCanonicalTagRow>
  columns={columns}
  rows={rows}
  renderRowActions={(row) => <TagActionsMenu row={row} ... />}
  aria-label="Canonical tags"
/>
```

---

### `frontend/src/widgets/tag-management/TagMergeModal.tsx` (component, request-response)

**Analog:** `frontend/src/widgets/action-items/MergeModal.tsx` (entire file).

**Why closest:** Identical two-step pick/confirm state machine (`useState<"pick" | "confirm">("pick")`), `useEffect([open])` reset, `Modal` wrapper with `dismissible={!saving}`, `emitToast` on success, error banner with `role="alert"`.

**State machine pattern** (`MergeModal.tsx` lines 33–47):
```typescript
const [primaryId, setPrimaryId] = useState<number | null>(null);
const [step, setStep] = useState<"pick" | "confirm">("pick");
const [saving, setSaving] = useState(false);
const [error, setError] = useState<string | null>(null);

// Reset on open:
useEffect(() => {
  if (open) {
    setPrimaryId(null);
    setStep("pick");
    setSaving(false);
    setError(null);
  }
}, [open]);
```

**Error banner pattern** (`MergeModal.tsx` lines 120–129):
```tsx
{error && (
  <div role="alert" className="flex items-start gap-2 border-l-4 border-red bg-red-tint
                               text-red rounded-md px-4 py-2 mb-4">
    <AlertCircle size={16} className="mt-0.5 shrink-0" aria-hidden="true" />
    <span className="text-[13px]">{error}</span>
  </div>
)}
```

**Footer button pattern** (`MergeModal.tsx` lines 69–108):
```tsx
// Step 1 proceed button:
<button disabled={primaryId === null}
        className="px-4 py-2 text-[14px] bg-yellow text-black font-semibold rounded-md
                   hover:bg-yellow-hover disabled:opacity-50 disabled:cursor-not-allowed">
  Merge items
</button>
// Step 2 confirm button (in-flight state):
{saving ? "Merging…" : "Merge items"}
```

**Adaptation for tag merge:** Replace `primaryId` with `targetId`; add `searchQuery` state for the search filter; add the `radio` list inside the scrollable container. Import `Modal` from `../modal/Modal` (same path pattern as `MergeModal.tsx` line 3).

---

### `frontend/src/widgets/tag-management/useMergeProgress.ts` (hook, event-driven)

**Analog:** `frontend/src/widgets/notif-bell/useNotifications.ts` (entire file, 66 lines).

**Why closest:** Identical structure — `useCallback` for the fetch function, `useEffect` that calls fetch immediately then sets up `setInterval`, returns `clearInterval` as cleanup. The 2s interval for merge progress is the same mechanism as 60s for notifications.

**Full pattern to adapt** (`useNotifications.ts` lines 5–29):
```typescript
export function useNotifications() {
  const [count, setCount] = useState(0);
  const [items, setItems] = useState<NotificationRow[]>([]);
  const [loaded, setLoaded] = useState(false);

  const fetchBell = useCallback(async () => {
    try {
      const data = await getBell();
      setCount(data.unread_count);
      setItems(data.items);
      setLoaded(true);
    } catch {
      // Bell is best-effort — silently swallow transient errors.
    }
  }, []);

  // Initial fetch BEFORE setting up the interval — avoids flash at count=0.
  useEffect(() => {
    void fetchBell();
    const id = setInterval(() => {
      void fetchBell();
    }, 60_000);
    return () => clearInterval(id);
  }, [fetchBell]);
```

**Key adaptation for `useMergeProgress`** — auto-stop polling on terminal status (unlike bell which always polls):
```typescript
export function useMergeProgress() {
  const [job, setJob] = useState<TagMergeJobRow | null>(null);

  const fetchJob = useCallback(async () => {
    try {
      const data = await fetchActiveJob();
      setJob(data);
    } catch { /* best-effort */ }
  }, []);

  useEffect(() => {
    void fetchJob();
    // Only poll while non-terminal — stops automatically on SUCCESS/FAILED
    if (job?.status === "PENDING" || job?.status === "IN_PROGRESS") {
      const id = setInterval(() => void fetchJob(), 2_000);  // 2s (not 60s)
      return () => clearInterval(id);
    }
  }, [job?.status, fetchJob]);
  // ...
}
```

---

### `frontend/src/widgets/dashboard/TagPolarityChart.tsx` (component, request-response)

**Analog:** `frontend/src/widgets/dashboard/TopPerformingSection.tsx` (entire file, 267 lines).

**Why closest:** Same file directory. Uses identical recharts import set, `ResponsiveContainer`, `BarChart`, `XAxis`/`YAxis` config, loading skeleton pattern, error pattern, `role="img" aria-label="..."` wrapper, and card section structure.

**Recharts import pattern** (`TopPerformingSection.tsx` lines 1–10):
```typescript
import {
  Bar,
  BarChart,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
```

**Addition for `TagPolarityChart`** — add `Legend` (already in recharts, not in `TopPerformingSection`):
```typescript
import {
  Bar, BarChart, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
```

**BarChart config pattern** (`TopPerformingSection.tsx` lines 193–238):
```tsx
<div role="img" aria-label="Best and worst performing outlets bar chart">
  <ResponsiveContainer width="100%" height={280}>
    <BarChart data={chartData} barCategoryGap="30%" margin={{ bottom: 40 }}>
      <XAxis
        dataKey="shop_name"
        tick={{ fontSize: 10, fill: "#71717A" }}
        interval={0}
        tickFormatter={(name: string) => truncate(name, 12)}
        axisLine={{ stroke: "#E4E4E7" }}
        tickLine={false}
        angle={-35}
        textAnchor="end"
        height={60}
      />
      <YAxis
        tick={{ fontSize: 11, fill: "#A1A1AA" }}
        axisLine={false}
        tickLine={false}
        width={24}
      />
      <Tooltip content={<CustomTooltip />} cursor={{ fill: "rgba(0,0,0,0.03)" }} />
      <Bar dataKey="avg_rating" radius={[4, 4, 0, 0]} ... >
        {chartData.map((bar) => <Cell key={bar.shop_id} fill={barColor(bar.avg_rating)} />)}
      </Bar>
    </BarChart>
  </ResponsiveContainer>
</div>
```

**Stacked bar adaptation** (two `<Bar>` with `stackId="a"` — UI-SPEC Surface 5):
```tsx
<div role="img" aria-label="Tag distribution by polarity bar chart">
  <ResponsiveContainer width="100%" height={240}>
    <BarChart data={tags} barCategoryGap="35%" margin={{ bottom: 48 }}>
      <XAxis
        dataKey="label"
        tick={{ fontSize: 12, fill: "#71717A" }}
        tickFormatter={(name: string) => name.length > 14 ? name.slice(0, 13) + "…" : name}
        angle={-35}
        textAnchor="end"
        height={56}
        axisLine={{ stroke: "#E4E4E7" }}
        tickLine={false}
        interval={0}
      />
      <YAxis tick={{ fontSize: 12, fill: "#A1A1AA" }} axisLine={false} tickLine={false} width={28} />
      <Tooltip content={<TagPolarityTooltip />} cursor={{ fill: "rgba(0,0,0,0.03)" }} />
      <Legend verticalAlign="top" height={28} iconSize={8} iconType="circle"
              formatter={(value) => <span style={{ fontSize: 12, color: "#71717A" }}>{value}</span>} />
      {/* Stack positive on bottom (no radius), negative on top (rounded top corners) */}
      <Bar dataKey="positive_count" name="Positive" stackId="a" fill="#16A34A" radius={[0,0,0,0]} />
      <Bar dataKey="negative_count" name="Negative" stackId="a" fill="#DC2626" radius={[4,4,0,0]} />
    </BarChart>
  </ResponsiveContainer>
</div>
```

**Loading skeleton pattern** (`TopPerformingSection.tsx` lines 103–108):
```tsx
<section className="bg-white border border-line rounded-[14px] p-5">
  <div className="bg-line-soft rounded-xl animate-[sk-pulse_1.6s_ease-in-out_infinite] h-[280px]" />
</section>
```

**Section card pattern** (`TopPerformingSection.tsx` line 160):
```tsx
<section className="bg-white border border-line rounded-[14px] p-5">
```

---

## Shared Patterns

### Authentication / Permission — ORG_ADMIN enforcement

**Source:** `apps/accounts/permissions.py` lines 27–65
**Apply to:** `OrgCanonicalTagViewSet`, `TagMergeJobViewSet`, `tags_page_view`, sidebar guard

**API permission** (lines 27–39):
```python
class IsOrgAdmin(BasePermission):
    message = "Organisation Admin role required."

    def has_permission(self, request: Request, view: APIView) -> bool:
        user = request.user
        if not user or not user.is_authenticated:
            return False
        return bool(
            getattr(user, "role", None) == User.Role.ORG_ADMIN
            and getattr(user, "organisation_id", None) is not None
        )
```

**Template view decorator** (lines 42–65):
```python
@org_admin_required   # → @login_required wraps it; wrong-role gets HttpResponseForbidden
def tags_page_view(request):
    ...
```

**Sidebar guard** (lines 30–31):
```html
{% if user.role != "STAFF_ADMIN" %}
  {% include "partials/_nav_item.html" with ... %}
{% endif %}
```

### Tenant Scoping

**Source:** `apps/reviews/selectors/canonical_tags.py` line 22; `apps/common/views.py` lines 241–248
**Apply to:** All new selectors, viewset `get_queryset()`, merge service, task cross-org check

Every queryset filters by `organisation_id`. The task fetches source/target with `OrgCanonicalTag.objects.get(pk=..., organisation_id=org_id)` — a wrong org raises `DoesNotExist` (→ 404, not a data leak).

### Query-count Tests

**Source:** `apps/action_items/tests/test_views.py` lines 193–207
**Apply to:** canonical tag list endpoint, TagMergeJob poll endpoint, dashboard tag polarity endpoint

```python
def test_list_query_count_org_admin_le_5(org_admin_setup) -> None:
    client, _user, org = org_admin_setup
    OrgCanonicalTagFactory.create_batch(20, organisation=org)
    with CaptureQueriesContext(connection) as ctx:
        resp = client.get("/api/v1/reviews/canonical-tags/", {"page_size": 20})
    assert resp.status_code == 200
    assert len(ctx.captured_queries) <= 3, [q["sql"] for q in ctx.captured_queries]
    # Expected ceiling: 1 session/auth + 1 COUNT + 1 SELECT = 3
```

### Distributed Lock (merge task)

**Source:** `apps/common/locks.py` line 31
**Apply to:** `merge_canonical_tags()` service, tested with a mock in `test_services.py`

```python
with distributed_lock(f"lock:tag_merge:org:{org_id}", timeout=300, blocking=False) as acquired:
    if not acquired:
        return  # Pitfall 3: another worker holds the lock; exit cleanly
```

### Celery Task Thin-wrapper (tag-merge queue)

**Source:** `apps/reviews/tasks.py` lines 237–302 (`finalize_canonical_tags_task`)
**Apply to:** `merge_canonical_tags_task`

Key properties: `bind=True`, `max_retries=3`, `retry_backoff=60`, `retry_jitter=True`, business logic imported inside the function body (avoids circular imports), structured log records with `task_id`/`job_id`/`attempt`.

### `review_count` Derive-on-read Invariant

**Source:** `apps/reviews/services/finalise.py` lines 285–313 (`_refresh_review_counts`)
**Apply to:** `merge_canonical_tags()` service; any `bulk_update` call on `OrgCanonicalTag`

```python
# CORRECT — call after FK re-point and source.delete():
_refresh_review_counts(organisation_id=org_id)

# WRONG — naive sum violates D-03:
# target.review_count += source.review_count  ← NEVER do this
```

The `bulk_update` call inside `_refresh_review_counts` uses `["review_count"]` as the field list. Any other `bulk_update` on `OrgCanonicalTag` MUST exclude `review_count` from its field list.

### React `emitToast` Pattern

**Source:** `frontend/src/widgets/action-items/MergeModal.tsx` line 5, 60
**Apply to:** `MergeProgressBanner.tsx` on SUCCESS, `RenameInput.tsx` is silent (no toast — label change is visible in-place per UI-SPEC)

```typescript
import { emitToast } from "../../lib/toast";
emitToast({ kind: "success", title: "Merge complete" });
```

---

## No Analog Found

All files have analogs. No entries in this section.

---

## Metadata

**Analog search scope:** `apps/reviews/`, `apps/dashboard/`, `apps/notifications/`, `apps/accounts/`, `apps/common/`, `apps/action_items/`, `frontend/src/widgets/`, `frontend/src/entrypoints/`, `templates/partials/`, `config/settings/`
**Files scanned (via targeted reads):** 18 source files
**Pattern extraction date:** 2026-06-16
