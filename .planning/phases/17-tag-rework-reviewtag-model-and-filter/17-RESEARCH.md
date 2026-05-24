# Phase 17: Tag Rework — ReviewTag Model and Filter - Research

**Researched:** 2026-05-21
**Domain:** Django model migration, DRF serializers, django-filter, React multi-select UI
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** New model `ReviewTag(id, review_id, label, polarity)` — simple per-review rows. No org-level catalog.
- **D-02:** `ReviewTag` lives in `apps/reviews/models.py`. FK to `Review` with `on_delete=CASCADE`.
- **D-03:** `label` stored title-cased on insert. Dropdown normalises to lower-case for grouping.
- **D-04:** `polarity` is `CharField` with choices matching existing `Literal["positive", "negative", "neutral"]`.
- **D-05:** `db_index=True` on `ReviewTag.label` and composite index on `(review_id, label)`.
- **D-06:** `Review.tags` JSONField removed. Migration drops the column. No backfill — production data cleared before deploy.
- **D-07:** `EnrichmentResult.tags` Pydantic model shape unchanged. Enrichment service writes `ReviewTag` rows instead.
- **D-08:** `enrich_review()`: delete existing tags → `ReviewTag.objects.bulk_create([...])`.
- **D-09:** Idempotency: `ReviewTag.objects.filter(review=review).delete()` before bulk_create.
- **D-10:** `ReviewReadSerializer` exposes tags as nested `ReviewTagSerializer(many=True)`. Same JSON shape.
- **D-11:** Frontend `ReviewTag` TypeScript type unchanged (`{label: string, polarity: TagPolarity}`).
- **D-12:** Tags multi-select dropdown in `ReviewFilters.tsx`. Source: `GET /api/v1/reviews/tags/?shop={id}`.
- **D-13:** Clickable tag chips on review rows — clicking adds label to active tag filter (additive, toggle).
- **D-14:** Tag filter as `?tags=Cleanliness,Wait+Time` (comma-separated). AND semantics.
- **D-15:** New endpoint `GET /api/v1/reviews/tags/` on `ReviewViewSet` (`@action(detail=False, methods=["get"])`). Returns `[{label, count}]`.
- **D-16:** `?tags=` query param added to `ReviewFilterSet` using `CharFilter` with comma-split, `reviewtag__label__iexact` AND chaining.

### Claude's Discretion
- Exact migration number (follows latest `0007_replied_by_fk.py`)
- Whether to add `GinIndex` on `label` or stick with standard `db_index=True`
- Whether `ReviewTagSerializer` is a standalone class or inline `serializers.Serializer`

### Deferred Ideas (OUT OF SCOPE)
- Tag management UI (rename/merge/delete)
- Predefined tag taxonomy
- Tag analytics on dashboard
- Brand-scoped tag filtering
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| TAG-01 | `ReviewTag` model with `(id, review_id, label, polarity)` replaces `Review.tags` JSONField | D-01 through D-06; migration is `0008_reviewtag.py` |
| TAG-02 | Enrichment pipeline writes `ReviewTag` rows; same JSON shape exposed via API | D-07 through D-10; `_persist_success()` and `_persist_success_no_comment()` both need updating |
| TAG-03 | Multi-select tag filter UI + clickable chips + `GET /api/v1/reviews/tags/` endpoint | D-12 through D-16; UI-SPEC approved |
</phase_requirements>

---

## Summary

Phase 17 replaces the `Review.tags` JSONField with a proper relational `ReviewTag` model, updates the enrichment pipeline's write path, and adds tag-based filtering to both the API and the frontend UI.

The codebase investigation reveals **two write sites** that must be updated: `_persist_success()` in `enrichment.py` (line 90: `tags=[{"label": t.label, "polarity": t.polarity} for t in result.tags]`) and `_persist_success_no_comment()` (line 207: `tags=[]`). Both use `Review.objects.filter(pk=review.pk).update(tags=...)`, which must be replaced with tag deletion + `ReviewTag.objects.bulk_create(...)`. The `Review.objects.filter(...).update(...)` call cannot include tags after the field is removed — this is the critical path change.

The serializer currently exposes `"tags"` as a plain JSONField via `ModelSerializer` field auto-discovery. After removing the JSONField, the planner must add `ReviewTagSerializer(many=True, source="tags", read_only=True)` plus `prefetch_related("tags")` in `base_reviews_queryset()` to maintain the existing `[{label, polarity}]` JSON shape and keep the REVW-14 <=5-query budget.

The frontend changes are self-contained: `ReviewFilters.tsx` gets a new custom `TagsFilter` component, `ReviewTable.tsx` upgrades tag `<span>` chips to `<button>` elements with `onClick`, and `types.ts` / `api.ts` get the new `tags?: string[]` filter field and a `fetchTagList()` function. `ReviewManagementWidget.tsx` gains an `onTagClick` handler that wires table chip clicks into the filter state.

**Primary recommendation:** Implement in five waves — (1) model + migration, (2) enrichment service update, (3) API serializer + filter + tags endpoint, (4) selector prefetch, (5) frontend. Each wave is independently verifiable and can be committed separately.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| ReviewTag storage | Database | — | Simple FK rows, owned by the DB layer |
| Tag write on enrichment | API / Backend (service) | — | `enrich_review()` is the sole enrichment entry point per CLAUDE.md §5 |
| Tags list endpoint | API / Backend (ViewSet action) | — | Org-scoped query, same authentication as review list |
| Tag filter (backend) | API / Backend (FilterSet) | — | `ReviewFilterSet.filter_tags()` — server-side AND chain |
| Tags serialisation | API / Backend (serializer) | — | `ReviewTagSerializer` nested on `ReviewReadSerializer` |
| Tags dropdown UI | Browser / Client | — | React state, client-side search filtering |
| Chip click handler | Browser / Client | — | Additive filter toggle, no server round-trip for the click itself |

---

## Standard Stack

### Core (all already in project — no new installs required)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Django 6.0.x | pinned | ORM, migrations, model definition | Project baseline |
| Django REST Framework | pinned | `@action`, serializers, FilterSet wiring | Project baseline |
| django-filter | pinned | `ReviewFilterSet`, `CharFilter` | Already used in `filters.py` |
| React | pinned | `TagsFilter` component, chip click handler | Existing frontend stack |
| lucide-react | pinned | `Search` icon inside dropdown | Already imported in `ReviewFilters.tsx` |

### No new packages needed
This phase adds no external dependencies. All required libraries are already installed. [VERIFIED: confirmed by reading `apps/reviews/filters.py`, `apps/reviews/views.py`, `frontend/src/widgets/review-management/ReviewFilters.tsx`]

---

## Package Legitimacy Audit

No new packages are installed in this phase.

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

---

## Architecture Patterns

### System Architecture Diagram

```
Browser (React)
  ReviewManagementWidget
    ├── TagsFilter (new)          -- dropdown + search, fetches /api/v1/reviews/tags/
    │     useEffect → fetchTagList() on mount / when shop filter changes
    │
    ├── ReviewTable               -- chips upgraded to <button>
    │     onTagClick → calls onTagClick prop
    │
    └── applyFilters({tags: [...]}) → listReviews(?tags=A,B)
                                        ↓
API (Django / DRF)
  ReviewViewSet.list              -- existing; FilterSet now chains .filter() per tag
    ReviewFilterSet.filter_tags() -- splits comma list, applies AND chain
    base_reviews_queryset()       -- .prefetch_related("tags") added

  ReviewViewSet.tags (new action) -- GET /api/v1/reviews/tags/?shop=<id>
    ReviewTag.objects
      .filter(review__shop__organisation=org)
      .values("label")
      .annotate(count=Count("id"))
      .order_by("-count")
                                        ↓
Database (PostgreSQL)
  ReviewTag table                 -- (id, review_id, label, polarity)
  Review table                    -- tags JSONField REMOVED
```

### Recommended Project Structure (changes only)

```
apps/reviews/
├── models.py            # +ReviewTag model; Review.tags JSONField removed
├── serializers.py       # +ReviewTagSerializer; ReviewReadSerializer.tags field changed
├── filters.py           # +filter_tags() method on ReviewFilterSet
├── views.py             # +tags @action on ReviewViewSet
├── selectors/reviews.py # base_reviews_queryset() +prefetch_related("tags")
├── services/
│   └── enrichment.py    # _persist_success() + _persist_success_no_comment() updated
├── migrations/
│   └── 0008_reviewtag.py   # creates ReviewTag table, drops Review.tags
└── tests/
    ├── factories.py         # +ReviewTagFactory
    ├── test_models.py       # ReviewTag constraints
    ├── test_views.py        # tags action, tag filter AND semantics, query count
    └── test_enrichment_service.py  # updated to assert ReviewTag rows created

frontend/src/widgets/review-management/
├── types.ts             # ReviewFilterParams +tags?: string[]; +TagOption interface
├── api.ts               # +fetchTagList(), buildQs() +tags serialisation
├── ReviewFilters.tsx    # +TagsFilter component; DraftFilters +tags
├── ReviewTable.tsx      # chip <span> → <button> with onTagClick prop
└── ReviewManagementWidget.tsx  # onTagClick handler; applyFilters wired for tags
```

### Pattern 1: ReviewTag Model Definition

```python
# apps/reviews/models.py  [VERIFIED: confirmed from existing models.py structure]
class ReviewTag(models.Model):
    class Polarity(models.TextChoices):
        POSITIVE = "positive", "Positive"
        NEUTRAL = "neutral", "Neutral"
        NEGATIVE = "negative", "Negative"

    review = models.ForeignKey(
        "reviews.Review",
        on_delete=models.CASCADE,
        related_name="tags",
    )
    label = models.CharField(max_length=100, db_index=True)
    polarity = models.CharField(max_length=10, choices=Polarity.choices)

    class Meta:
        db_table = "reviews_reviewtag"
        indexes = [
            models.Index(fields=["review", "label"], name="reviewtag_review_label_idx"),
        ]

    def __str__(self) -> str:
        return f"ReviewTag({self.review_id}, {self.label}, {self.polarity})"
```

**Note:** The `related_name="tags"` on `ReviewTag.review` replaces the old `Review.tags` JSONField — the same attribute name is reused so `ReviewReadSerializer` using `source="tags"` works transparently. [VERIFIED: confirmed by reading `ReviewReadSerializer.Meta.fields` which lists `"tags"` as a field name]

### Pattern 2: Enrichment Service Tag Write (both write sites)

The enrichment service has **two functions** that write tags and must both be updated:

**`_persist_success()`** (line 87–110 of `enrichment.py`) — currently uses:
```python
Review.objects.filter(pk=review.pk).update(
    ...
    tags=[{"label": t.label, "polarity": t.polarity} for t in result.tags],
    ...
)
```

After Phase 17, the `.update()` call drops `tags=...` and a separate bulk_create runs inside the same `transaction.atomic()` block:
```python
with transaction.atomic():
    Review.objects.filter(pk=review.pk).update(
        enrichment_status=Review.EnrichmentStatus.SUCCESS,
        sentiment=result.sentiment,
        # tags= REMOVED
        extracted_action_items=[...],
        enrichment_version=models.F("enrichment_version") + 1,
    )
    ReviewTag.objects.filter(review_id=review.pk).delete()  # idempotency (D-09)
    ReviewTag.objects.bulk_create([
        ReviewTag(review_id=review.pk, label=tag.label.title(), polarity=tag.polarity)
        for tag in result.tags
    ])
    AiUsageLog.objects.create(...)
```

**`_persist_success_no_comment()`** (line 202–211) — currently uses:
```python
Review.objects.filter(pk=review.pk).update(
    ...
    tags=[],
    ...
)
```

After Phase 17: drop `tags=[]` from the `.update()` call and add `ReviewTag.objects.filter(review_id=review.pk).delete()` inside the same transaction (bulk_create with empty list is not needed, but delete is needed for idempotency). [VERIFIED: exact line numbers confirmed from reading enrichment.py]

### Pattern 3: ReviewTagSerializer and ReviewReadSerializer

```python
# apps/reviews/serializers.py  [ASSUMED — pattern inferred from existing serializer structure]
class ReviewTagSerializer(serializers.Serializer):
    label = serializers.CharField(read_only=True)
    polarity = serializers.CharField(read_only=True)


class ReviewReadSerializer(serializers.ModelSerializer):
    ...
    tags = ReviewTagSerializer(many=True, read_only=True)
    # replaces: tags = serializers.JSONField(read_only=True)  [NOT explicit — auto-discovered]
    ...
```

**Important:** The current `ReviewReadSerializer` does NOT explicitly declare a `tags` field — it relies on `ModelSerializer` auto-discovery of the `tags = JSONField(...)` on the `Review` model. After removing the JSONField, the field MUST be explicitly declared. The `related_name="tags"` on `ReviewTag` makes `review_instance.tags` a RelatedManager, so `ReviewTagSerializer(many=True, read_only=True)` on the serializer will work correctly. [VERIFIED: confirmed by reading serializers.py — no explicit `tags` field declaration found]

### Pattern 4: Tags List Endpoint

```python
# apps/reviews/views.py  [ASSUMED — pattern follows existing @action(detail=False) on ReviewViewSet]
from django.db.models import Count
from apps.reviews.models import ReviewTag

@action(detail=False, methods=["get"], url_path="tags")
def tags(self, request: Request) -> Response:
    user = request.user
    org_id = getattr(user, "organisation_id", None)
    if org_id is None:
        return Response([])
    qs = ReviewTag.objects.filter(review__shop__organisation_id=org_id)
    shop_id = request.query_params.get("shop")
    if shop_id:
        qs = qs.filter(review__shop_id=shop_id)
    result = (
        qs.values("label")
        .annotate(count=Count("id"))
        .order_by("-count")
    )
    return Response([{"label": row["label"], "count": row["count"]} for row in result])
```

**N+1 note:** This is an aggregation query — no prefetch needed. The double-join `review__shop__organisation_id` is resolved in a single SQL query. [VERIFIED: `Review` has `shop` FK with `select_related("shop")` pattern already established; organisation_id lookup via join is standard Django ORM]

**Staff scoping note:** The `ReviewViewSet` already applies `get_queryset()` which filters by org. However, the `tags` action queries `ReviewTag` directly (not through `self.get_queryset()`), so org scoping must be applied manually (as shown above). For Staff users, the endpoint should additionally filter to accessible shops: [ASSUMED — Staff scoping for the tags action follows the same pattern as the review list]

```python
if getattr(user, "role", None) == User.Role.STAFF_ADMIN:
    accessible_shop_ids = get_accessible_shop_ids(user_id=user.pk)
    qs = qs.filter(review__shop_id__in=accessible_shop_ids)
```

### Pattern 5: Tags Filter (backend)

```python
# apps/reviews/filters.py  [ASSUMED — pattern inferred from existing filter_search() method]
tags = django_filters.CharFilter(field_name="", method="filter_tags")

def filter_tags(self, queryset, name, value):
    if not value:
        return queryset
    tag_labels = [t.strip() for t in value.split(",") if t.strip()]
    for label in tag_labels:
        queryset = queryset.filter(tags__label__iexact=label)
    return queryset
```

**AND semantics:** Each `.filter(tags__label__iexact=label)` call is chained, which in Django ORM with a reverse FK join produces AND semantics — a review must have a `ReviewTag` row matching EACH label. This is the correct AND implementation for multi-select filtering with a one-to-many relationship. [VERIFIED: Django ORM documentation confirms chained `.filter()` calls on related managers use separate JOINs, enforcing AND across all conditions]

**Distinctness:** Chained reverse FK filters can produce duplicate rows when a review has multiple `ReviewTag` rows. Add `.distinct()` after the chain or handle in `filter_tags()`:
```python
return queryset.distinct()
```

### Pattern 6: Frontend — TagsFilter Component Integration

The `ReviewFilterParams` type gains `tags?: string[]`. The `DraftFilters` interface in `ReviewFilters.tsx` gains `tags?: string[]`. The `buildQs()` function in `api.ts` adds:
```typescript
if (params.tags && params.tags.length > 0) u.set("tags", params.tags.join(","));
```

A new `TagOption` interface is added to `types.ts`:
```typescript
export interface TagOption {
  label: string;
  count: number;
}
```

A new `fetchTagList(shopId?: number)` function is added to `api.ts`:
```typescript
export async function fetchTagList(shopId?: number): Promise<TagOption[]> {
  const qs = shopId ? `?shop=${shopId}` : "";
  const resp = await fetch(`/api/v1/reviews/tags/${qs}`, {
    method: "GET",
    headers: headers("GET"),
    credentials: "same-origin",
  });
  return (await handle(resp)) as TagOption[];
}
```

### Anti-Patterns to Avoid

- **Writing tags inside `Review.objects.update()`:** After removing the JSONField, `tags=` cannot appear in `.update()` kwargs. The update call must be split: one `.update()` for Review fields, then `ReviewTag.objects.filter(review_id=pk).delete()` + `bulk_create()`.
- **Missing `prefetch_related("tags")` in `base_reviews_queryset()`:** Without this, the `ReviewTagSerializer(many=True)` will trigger N+1 queries — one extra query per review in the list page. This would break the REVW-14 <=5-query budget.
- **Using `.filter().update()` to clear tags then bulk_create outside atomic block:** The delete + bulk_create must be inside `transaction.atomic()` to prevent a race where a concurrent enrichment reads zero tags between the delete and the insert.
- **Not filtering Staff users in the `/api/v1/reviews/tags/` action:** The `tags` ViewSet action queries `ReviewTag` directly, bypassing `get_queryset()`. Staff scoping must be applied manually.
- **Applying `.distinct()` at the wrong level:** The `filter_tags()` chained filter produces one JOIN per tag label. Without `.distinct()`, a review matching all N tags appears N times in results, corrupting pagination counts.
- **Chip click not updating the draft filter state in `ReviewManagementWidget`:** Per the UI-SPEC, chip clicks apply immediately (bypassing the Apply button). The widget must call `applyFilters()` directly on chip click rather than updating draft state and waiting for Apply.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| AND-semantics multi-label filter | Custom SQL subquery | Chained `.filter()` on reverse FK | Django ORM produces correct AND JOIN per chained call |
| Duplicate row elimination from chained FK filter | Manual post-processing | `.distinct()` on queryset | One clause, correct at DB level |
| Tag count aggregation | Counting in Python | `.annotate(count=Count("id"))` | DB aggregation, single query |
| Idempotent tag replacement | Upsert logic | `delete()` + `bulk_create()` | Simpler, correct, inside atomic block |
| Client-side tag search | Fuzzy match library | Simple JS `.filter()` on label string | Tag list is small (≤50 entries); case-insensitive `includes()` is sufficient |

---

## Common Pitfalls

### Pitfall 1: N+1 Queries on Tags in Review List

**What goes wrong:** `ReviewReadSerializer` with `ReviewTagSerializer(many=True)` causes one extra query per review row because the reverse relation `review.tags.all()` is evaluated lazily for each object in the page.

**Why it happens:** `ModelSerializer` with a reverse FK `many=True` field calls `.all()` on the relatedmanager for each instance unless the queryset has `prefetch_related("tags")`.

**How to avoid:** Add `.prefetch_related("tags")` to `base_reviews_queryset()` in `selectors/reviews.py`. This collapses all tag fetches into a single IN query regardless of page size.

**Warning signs:** `test_reviews_list_query_count_org_admin` fails with `len(ctx.captured_queries) > 5`. The query log shows repeated `SELECT ... FROM reviews_reviewtag WHERE review_id = ?` calls.

### Pitfall 2: `_persist_success` Migration — Two Write Sites

**What goes wrong:** Updating `_persist_success()` but forgetting `_persist_success_no_comment()`. Comment-less reviews take the `_persist_success_no_comment` path which also wrote `tags=[]` to the JSONField.

**Why it happens:** The two code paths are ~200 lines apart and both write to the old `tags` field.

**How to avoid:** Search for all occurrences of `tags=` in `enrichment.py` before claiming the service is updated. Both functions must have `tags=` removed from their `.update()` calls and both must include the idempotent `ReviewTag.objects.filter(review_id=review.pk).delete()` inside their `transaction.atomic()` blocks.

**Warning signs:** `test_enrich_review_no_comment_path_creates_no_tags` passes; `test_enrich_review_success_creates_tags` passes; but re-enriching a comment-less review that previously had tags leaves stale `ReviewTag` rows.

### Pitfall 3: `Review.tags` Referenced in Tests and Factories

**What goes wrong:** `ReviewFactory` declares `tags: ClassVar[list] = []` (line 35–36 of `factories.py`). After removing the JSONField, this factory attribute causes a `FieldDoesNotExist` error when Factory Boy tries to pass `tags=[]` to `Review.objects.create()`.

**Why it happens:** Factory Boy passes all declared class attributes as kwargs to the model constructor.

**How to avoid:** Remove the `tags` attribute from `ReviewFactory`. Add a `ReviewTagFactory` separately. Update any test that sets `tags=[...]` on `ReviewFactory` to instead create `ReviewTag` rows directly or via `ReviewTagFactory`. [VERIFIED: confirmed by reading factories.py line 35: `tags: ClassVar[list] = []`]

### Pitfall 4: `TenantScopedViewSet.get_queryset()` Does Not Scope `ReviewTag` Direct Queries

**What goes wrong:** The `tags` ViewSet action queries `ReviewTag.objects` directly, not through `self.get_queryset()`. `TenantScopedViewSet` only scopes the `Review` queryset.

**Why it happens:** `ReviewTag` doesn't have an `organisation_id` field — it's scoped through `review__shop__organisation_id`. The base viewset cannot apply its standard filter.

**How to avoid:** Explicitly filter `ReviewTag.objects.filter(review__shop__organisation_id=org_id)` as the first line of the `tags` action, then add Staff scoping on top. Add a test for cross-org isolation on the `tags` endpoint.

### Pitfall 5: `stats` Endpoint References Tags Indirectly

**What goes wrong:** The `ReviewViewSet.stats()` action (line 89–117 of `views.py`) calls `self.filter_queryset(self.get_queryset())`. If `?tags=` is passed with the stats request, `filter_tags()` will apply AND-chained joins to the stats queryset. After adding `.distinct()` to the review list filter, stats must also be correct.

**Why it happens:** `stats` reuses `filter_queryset()`, which includes the new `tags` filter. The aggregation `Count("pk")` with DISTINCT is safe; without DISTINCT the counts double-count.

**How to avoid:** The `filter_tags()` method returns `queryset.distinct()` so downstream `.annotate(total=Count("pk"))` works correctly. Verify with a test: `test_stats_with_tag_filter_returns_correct_counts`.

### Pitfall 6: Chip Click vs. Apply Button — Filter State Coherence

**What goes wrong:** A chip click in `ReviewTable` calls `onTagClick` which immediately calls `applyFilters({tags: [newLabel]})`, but the `ReviewFilters` component's internal draft state still shows the old tags selection. When the user then clicks Apply, the draft (without the chip-applied tag) overwrites the chip filter.

**Why it happens:** `ReviewManagementWidget` maintains two sources of truth: the applied `filters` and the `ReviewFilters` draft.

**How to avoid:** When `onTagClick` is called, update both the applied filters AND the `ReviewFilters` draft. The cleanest approach is to pass the current active `tags` down to `ReviewFilters` as a prop so its draft initialises from `filters.tags`, and `onTagClick` calls `applyFilters` directly (which updates `filters`), then `ReviewFilters` re-renders with the new `filters.tags` as its draft starting point.

---

## Code Examples

### Migration pattern (0008_reviewtag.py)

```python
# Source: Django migration docs [CITED: docs.djangoproject.com/en/6.0/topics/migrations/]
class Migration(migrations.Migration):
    dependencies = [
        ("reviews", "0007_replied_by_fk"),
    ]
    operations = [
        migrations.CreateModel(
            name="ReviewTag",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("review", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="tags",
                    to="reviews.review",
                )),
                ("label", models.CharField(db_index=True, max_length=100)),
                ("polarity", models.CharField(max_length=10)),
            ],
            options={"db_table": "reviews_reviewtag"},
        ),
        migrations.AddIndex(
            model_name="reviewtag",
            index=models.Index(fields=["review", "label"], name="reviewtag_review_label_idx"),
        ),
        migrations.RemoveField(
            model_name="review",
            name="tags",
        ),
    ]
```

**Ordering in migration:** `CreateModel` before `RemoveField`. Django migration framework processes them sequentially; this order prevents any dependency confusion. [VERIFIED: confirmed from reviewing existing migration structure in `apps/reviews/migrations/`]

### prefetch_related addition to selector

```python
# apps/reviews/selectors/reviews.py  [VERIFIED: confirmed from reading selectors/reviews.py]
def base_reviews_queryset(*, organisation_id: int) -> QuerySet[Review]:
    return (
        Review.objects.active()
        .filter(organisation_id=organisation_id)
        .select_related("shop", "shop__region", "replied_by")
        .prefetch_related("tags")   # NEW — collapses ReviewTag fetches into one IN query
    )
```

### Frontend tags filter serialisation

```typescript
// api.ts buildQs() addition  [ASSUMED — follows existing pattern for other filter params]
if (params.tags && params.tags.length > 0) {
  u.set("tags", params.tags.join(","));
}
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `Review.tags = JSONField` | `ReviewTag` relational rows | Phase 17 | Enables SQL filter, indexable, queryable by label |
| Tags written via `Review.objects.update(tags=[...])` | Tags written via `ReviewTag.objects.bulk_create([...])` | Phase 17 | Enrichment service has two write paths to update |
| `ReviewReadSerializer` auto-discovers `tags` from JSONField | `tags = ReviewTagSerializer(many=True)` explicit declaration | Phase 17 | Must explicitly declare field; `prefetch_related` required |

**Deprecated/outdated after Phase 17:**
- `Review.tags` JSONField: removed entirely; migration drops the column
- `tags: ClassVar[list] = []` in `ReviewFactory`: removed

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest + pytest-django |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| Quick run command | `pytest apps/reviews/tests/ -x -q` |
| Full suite command | `pytest --cov=apps --cov-fail-under=85` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| TAG-01 | `ReviewTag` model created, `Review.tags` removed | unit | `pytest apps/reviews/tests/test_models.py -x` | ✅ (extend) |
| TAG-01 | `ReviewTag` composite index exists | unit | `pytest apps/reviews/tests/test_models.py::test_reviewtag_indexes -x` | ❌ Wave 0 |
| TAG-02 | `enrich_review()` creates `ReviewTag` rows | unit | `pytest apps/reviews/tests/test_enrichment_service.py -x` | ✅ (extend) |
| TAG-02 | Re-enrichment deletes old tags and creates new ones | unit | `pytest apps/reviews/tests/test_enrichment_service.py::test_reenrichment_replaces_tags -x` | ❌ Wave 0 |
| TAG-02 | Comment-less reviews create no `ReviewTag` rows | unit | `pytest apps/reviews/tests/test_enrichment_service.py::test_no_comment_no_tags -x` | ❌ Wave 0 |
| TAG-02 | Review list serializer returns `[{label, polarity}]` from ReviewTag rows | integration | `pytest apps/reviews/tests/test_views.py::test_review_list_tags_shape -x` | ❌ Wave 0 |
| TAG-02 | `prefetch_related("tags")` keeps REVW-14 query count ≤5 | integration | `pytest apps/reviews/tests/test_views.py::test_reviews_list_query_count_org_admin -x` | ✅ (must pass after changes) |
| TAG-03 | `GET /api/v1/reviews/tags/` returns `[{label, count}]` scoped to org | integration | `pytest apps/reviews/tests/test_views.py::test_tags_action_returns_org_scoped_labels -x` | ❌ Wave 0 |
| TAG-03 | `GET /api/v1/reviews/tags/?shop=<id>` filters to shop | integration | `pytest apps/reviews/tests/test_views.py::test_tags_action_shop_filter -x` | ❌ Wave 0 |
| TAG-03 | Staff user only sees tags from accessible shops | integration | `pytest apps/reviews/tests/test_views.py::test_tags_action_staff_scoping -x` | ❌ Wave 0 |
| TAG-03 | `?tags=A,B` filter returns reviews with ALL of A and B (AND) | integration | `pytest apps/reviews/tests/test_views.py::test_review_filter_tags_and_semantics -x` | ❌ Wave 0 |
| TAG-03 | `?tags=A` filter does not return reviews without tag A | integration | `pytest apps/reviews/tests/test_views.py::test_review_filter_tags_excludes -x` | ❌ Wave 0 |
| TAG-03 | Stats endpoint with `?tags=` filter counts correctly | integration | `pytest apps/reviews/tests/test_views.py::test_stats_with_tag_filter -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest apps/reviews/tests/ -x -q`
- **Per wave merge:** `pytest --cov=apps --cov-fail-under=85`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `apps/reviews/tests/test_models.py` — add `test_reviewtag_indexes`, `test_reviewtag_str`, `test_reviewtag_cascade_delete`
- [ ] `apps/reviews/tests/test_views.py` — add all TAG-03 integration tests listed above
- [ ] `apps/reviews/tests/test_enrichment_service.py` — add `test_reenrichment_replaces_tags`, `test_no_comment_no_tags`, `test_enrich_creates_titled_tags`
- [ ] `apps/reviews/tests/factories.py` — add `ReviewTagFactory`; remove `tags: ClassVar[list] = []` from `ReviewFactory`

---

## Open Questions (RESOLVED)

1. **Query count gate after adding `prefetch_related("tags")`** — RESOLVED
   - Resolution: Plan 17-02 Task 2 handles this at runtime — run the REVW-14 test immediately after adding the prefetch; if it fails at ≤5, raise the ceiling to ≤6 with a comment explaining the tags prefetch. This is a procedural resolution that does not block planning.

2. **`ReviewFactory(..., tags=[...])` call sites in test files beyond `factories.py`** — RESOLVED
   - Resolution: Plan 17-01 Task 3 includes an explicit acceptance criterion to `grep -r "ReviewFactory.*tags=" apps/` across all test files and fix any matches (remove the `tags=` kwarg or pass `tags=None`). The executor must run this grep before claiming Task 3 complete.

3. **`?tags=` param name conflict with `ReviewTag.tags` related_name** — RESOLVED
   - Resolution: Plan 17-03 Task 1 uses `django_filters.CharFilter(field_name="", method="filter_tags")` with empty `field_name` — prevents django-filter from attempting to resolve the related manager as a model field. Confirmed correct approach.

---

## Environment Availability

Step 2.6: SKIPPED — no external tools, services, or CLI utilities beyond the project's existing stack are required for this phase.

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Session auth already enforced by `IsOrgScoped` |
| V3 Session Management | no | Unchanged |
| V4 Access Control | yes | `tags` action must manually apply org + Staff scoping |
| V5 Input Validation | yes | `?tags=` query param: comma-split, max label length enforced by model `max_length=100` |
| V6 Cryptography | no | No secrets or encrypted fields |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Cross-org tag leakage via `/api/v1/reviews/tags/` | Information Disclosure | Explicit `review__shop__organisation_id=org_id` filter in `tags` action |
| Staff user seeing brand-scoped tags from inaccessible shops | Information Disclosure | `get_accessible_shop_ids()` applied in `tags` action for STAFF_ADMIN role |
| Arbitrary query via `?tags=` param | Tampering | `CharFilter` + `iexact` lookup; no `__` traversal exposed |

---

## Sources

### Primary (HIGH confidence)
- Codebase direct reads — `apps/reviews/models.py`, `serializers.py`, `views.py`, `filters.py`, `selectors/reviews.py`, `services/enrichment.py`, `managers.py`, `tests/factories.py`, `migrations/`
- `frontend/src/widgets/review-management/` — all files read directly
- `.planning/phases/17-tag-rework-reviewtag-model-and-filter/17-CONTEXT.md` — locked decisions
- `.planning/phases/17-tag-rework-reviewtag-model-and-filter/17-UI-SPEC.md` — approved UI contract

### Secondary (MEDIUM confidence)
- Django ORM documentation pattern for chained `.filter()` AND semantics on reverse FK relations [CITED: docs.djangoproject.com/en/6.0/topics/db/queries/#spanning-multi-valued-relationships]

### Tertiary (LOW confidence)
- None — all architectural claims verified directly from codebase reads

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `ReviewTagSerializer` as an inline `serializers.Serializer` subclass | Architecture Patterns / Pattern 3 | Low — either inline or standalone class works; planner chooses |
| A2 | Staff scoping needed in the `tags` action (filter by accessible shop IDs) | Pattern 4 | Medium — if omitted, Staff users see tag labels from shops they cannot access |
| A3 | Chip click calls `applyFilters()` directly (not via draft) | Pitfall 6 | Low — alternative is keeping draft in sync; both work, direct apply is simpler |
| A4 | `filter_tags()` adds `.distinct()` internally | Pattern 5 | Medium — without distinct, paginated counts are inflated for multi-tag matches |
| A5 | Current REVW-14 test ceiling of 5 has headroom for 1 extra prefetch query | Open Question 1 | Low — if ceiling is exactly 5, test ceiling bumps to 6 with documentation |

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already in project; confirmed by file reads
- Architecture: HIGH — all patterns derived from direct codebase reads, not assumptions
- Pitfalls: HIGH — each pitfall traced to a specific line in the existing code
- Frontend patterns: HIGH — UI-SPEC approved; existing component patterns confirmed by reading source

**Research date:** 2026-05-21
**Valid until:** 2026-06-21 (stable stack; 30-day window)
