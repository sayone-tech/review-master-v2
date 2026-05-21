# Phase 17: Tag Rework — ReviewTag Model and Filter — Pattern Map

**Mapped:** 2026-05-21
**Files analyzed:** 12 new/modified files
**Analogs found:** 12 / 12

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `apps/reviews/models.py` | model | CRUD | `apps/reviews/models.py` (Review) + `apps/shops/models.py` (TextChoices) | exact — same file, add sibling model |
| `apps/reviews/migrations/0008_reviewtag.py` | migration | — | `apps/reviews/migrations/0007_replied_by_fk.py` | exact — most recent migration |
| `apps/reviews/services/enrichment.py` | service | CRUD | self — `_persist_success()` at line 86, `_persist_success_no_comment()` at line 203 | exact — modify two sites in the same file |
| `apps/reviews/serializers.py` | serializer | request-response | `apps/reviews/serializers.py` (ReviewReadSerializer) | exact — same file, add sibling serializer + swap field |
| `apps/reviews/selectors/reviews.py` | selector | CRUD | `apps/reviews/selectors/reviews.py` `base_reviews_queryset()` | exact — same file, one-line change |
| `apps/reviews/filters.py` | filter | request-response | `apps/reviews/filters.py` `filter_search()` / `filter_has_comment()` | exact — same file, add new method |
| `apps/reviews/views.py` | view / viewset | request-response | `apps/reviews/views.py` `stats` @action + `apps/shops/views.py` org-scoped direct query | exact role-match |
| `apps/reviews/tests/factories.py` | test factory | — | `apps/reviews/tests/factories.py` ReviewFactory | exact — same file, remove field + add sibling factory |
| `frontend/src/widgets/review-management/types.ts` | type definition | — | `frontend/src/widgets/review-management/types.ts` | exact — same file, extend interfaces |
| `frontend/src/widgets/review-management/api.ts` | API client | request-response | `frontend/src/widgets/review-management/api.ts` `fetchReviewStats()` / `buildQs()` | exact — same file, add function + extend buildQs |
| `frontend/src/widgets/review-management/ReviewFilters.tsx` | component | event-driven | `frontend/src/widgets/review-management/ReviewFilters.tsx` — Sentiment select block | exact — same file, add Tags row following Sentiment pattern |
| `frontend/src/widgets/review-management/ReviewTable.tsx` | component | event-driven | `frontend/src/widgets/review-management/ReviewTable.tsx` — tags column chip `<span>` blocks | exact — same file, `<span>` → `<button>` with `onClick` |
| `frontend/src/widgets/review-management/ReviewManagementWidget.tsx` | component (orchestrator) | event-driven | self — `applyFilters` wiring at line 146 | exact — same file, add `onTagClick` handler |

---

## Pattern Assignments

### `apps/reviews/models.py` — Add `ReviewTag` model

**Analog:** `apps/reviews/models.py` lines 20–121 (Review class) + `apps/shops/models.py` lines 13–27 (TextChoices inner class pattern)

**TextChoices inner class pattern** (`apps/shops/models.py` lines 17–22):
```python
class ConnectionStatus(models.TextChoices):
    CONNECTED = "CONNECTED", "Connected"
    EXPIRED = "EXPIRED", "Connection Expired"
    ERROR = "ERROR", "Connection Error"
    QUOTA_EXCEEDED = "QUOTA_EXCEEDED", "Quota Exceeded"
    NOT_CONNECTED = "NOT_CONNECTED", "Not Connected"
```

**FK with related_name pattern** (`apps/reviews/models.py` lines 34–44):
```python
organisation = models.ForeignKey(
    "organisations.Organisation",
    on_delete=models.CASCADE,
    related_name="reviews",
    db_index=True,
)
shop = models.ForeignKey(
    "shops.Shop",
    on_delete=models.CASCADE,
    related_name="reviews",
)
```

**Meta with indexes pattern** (`apps/reviews/models.py` lines 87–118):
```python
class Meta:
    db_table = "reviews_review"
    ordering: ClassVar[list[str]] = ["-review_create_time"]
    indexes: ClassVar[list[models.Index]] = [
        models.Index(
            fields=["organisation", "shop", "is_replied", "star_rating"],
            name="review_org_shop_filter_idx",
        ),
        ...
    ]
```

**ReviewTag to write** (verbatim from RESEARCH.md Pattern 1 — verified against codebase):
```python
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
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=["review", "label"], name="reviewtag_review_label_idx"),
        ]

    def __str__(self) -> str:
        return f"ReviewTag({self.review_id}, {self.label}, {self.polarity})"
```

**Remove from Review model** (line 78):
```python
# REMOVE this line:
tags = models.JSONField(default=list, blank=True)
```

---

### `apps/reviews/migrations/0008_reviewtag.py` — New migration

**Analog:** `apps/reviews/migrations/0007_replied_by_fk.py` (lines 1–21) — exact migration header/dependency pattern

**Migration header pattern** (`0007_replied_by_fk.py` lines 1–8):
```python
# Generated by Django 6.0.2 on 2026-05-07 15:07

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('reviews', '0007_replied_by_fk'),
        ...
    ]
```

**Migration to write** — dependency chain: `("reviews", "0007_replied_by_fk")`. Operations in order: `CreateModel`, `AddIndex`, `RemoveField`. Order matters — `CreateModel` before `RemoveField` so the column can be dropped cleanly after the new table exists:
```python
# Generated by Django 6.0.2

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("reviews", "0007_replied_by_fk"),
    ]

    operations = [
        migrations.CreateModel(
            name="ReviewTag",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                (
                    "review",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="tags",
                        to="reviews.review",
                    ),
                ),
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

---

### `apps/reviews/services/enrichment.py` — Modify two write sites

**Analog:** `apps/reviews/services/enrichment.py` — the existing `_persist_success()` and `_persist_success_no_comment()` functions are the analogs. The surrounding `transaction.atomic()` block and `AiUsageLog.objects.create()` call remain intact.

**Site 1: `_persist_success()` — lines 86–110**

Current code to REPLACE (lines 87–96):
```python
with transaction.atomic():
    Review.objects.filter(pk=review.pk).update(
        enrichment_status=Review.EnrichmentStatus.SUCCESS,
        sentiment=result.sentiment,
        tags=[{"label": t.label, "polarity": t.polarity} for t in result.tags],  # REMOVE
        extracted_action_items=[
            {"title": a.title, "scope": a.scope, "priority": a.priority}
            for a in result.action_items
        ],
        enrichment_version=models.F("enrichment_version") + 1,
    )
    AiUsageLog.objects.create(...)
```

New code (add `ReviewTag` import at top of file alongside existing `Review` import, then inside the `transaction.atomic()` block after the `.update()` call, before `AiUsageLog.objects.create()`):
```python
# At file top — add to existing import:
from apps.reviews.models import Review, ReviewTag

# Inside the transaction.atomic() block of _persist_success():
with transaction.atomic():
    Review.objects.filter(pk=review.pk).update(
        enrichment_status=Review.EnrichmentStatus.SUCCESS,
        sentiment=result.sentiment,
        # tags= REMOVED — now written as ReviewTag rows below
        extracted_action_items=[
            {"title": a.title, "scope": a.scope, "priority": a.priority}
            for a in result.action_items
        ],
        enrichment_version=models.F("enrichment_version") + 1,
    )
    ReviewTag.objects.filter(review_id=review.pk).delete()      # idempotency (D-09)
    ReviewTag.objects.bulk_create([
        ReviewTag(review_id=review.pk, label=tag.label.title(), polarity=tag.polarity)
        for tag in result.tags
    ])
    AiUsageLog.objects.create(...)  # unchanged
```

**Site 2: `_persist_success_no_comment()` — lines 203–210**

Current code to REPLACE (lines 204–210):
```python
with transaction.atomic():
    Review.objects.filter(pk=review.pk).update(
        enrichment_status=Review.EnrichmentStatus.SUCCESS,
        sentiment=sentiment_value,
        tags=[],                          # REMOVE — was always empty list
        extracted_action_items=[],
        enrichment_version=models.F("enrichment_version") + 1,
    )
```

New code:
```python
with transaction.atomic():
    Review.objects.filter(pk=review.pk).update(
        enrichment_status=Review.EnrichmentStatus.SUCCESS,
        sentiment=sentiment_value,
        # tags= REMOVED
        extracted_action_items=[],
        enrichment_version=models.F("enrichment_version") + 1,
    )
    ReviewTag.objects.filter(review_id=review.pk).delete()      # idempotency for re-enrichment
    # bulk_create with empty list is not needed — no-op for comment-less reviews
```

**Key constraint:** Both delete + bulk_create calls must be INSIDE the `transaction.atomic()` block. The `_emit_enrichment_progress()` call remains OUTSIDE the transaction block (existing pattern, line 113).

---

### `apps/reviews/serializers.py` — Add `ReviewTagSerializer` + swap `tags` field

**Analog:** `apps/reviews/serializers.py` lines 67–70 — `ReviewReplySerializer` as a plain `serializers.Serializer` subclass (not ModelSerializer). Same pattern for `ReviewTagSerializer`.

**Plain Serializer pattern** (`serializers.py` lines 67–70):
```python
class ReviewReplySerializer(serializers.Serializer):  # type: ignore[type-arg]
    """Input serializer for POST /reviews/{id}/reply/ (Plan 07)."""

    comment = serializers.CharField(min_length=1, max_length=4000, trim_whitespace=False)
```

**Add before `ReviewReadSerializer`:**
```python
class ReviewTagSerializer(serializers.Serializer):  # type: ignore[type-arg]
    label = serializers.CharField(read_only=True)
    polarity = serializers.CharField(read_only=True)
```

**Swap in `ReviewReadSerializer`:** `"tags"` is currently auto-discovered from the `JSONField` on `Review` — after field removal it must be explicitly declared. Add as explicit field on `ReviewReadSerializer`:
```python
class ReviewReadSerializer(serializers.ModelSerializer):  # type: ignore[type-arg]
    shop_name = serializers.CharField(source="shop.name", read_only=True)
    shop_region_name = serializers.SerializerMethodField()
    region_id = serializers.IntegerField(source="shop.region_id", read_only=True)
    replied_by_name = serializers.SerializerMethodField()
    has_action_items = serializers.BooleanField(read_only=True)
    tags = ReviewTagSerializer(many=True, read_only=True)  # NEW — replaces JSONField auto-discovery
```

`"tags"` stays in `Meta.fields` at line 44 — no change needed there. The `read_only_fields = fields` assignment covers it.

---

### `apps/reviews/selectors/reviews.py` — Add `prefetch_related("tags")`

**Analog:** `apps/reviews/selectors/reviews.py` lines 36–42 — `base_reviews_queryset()` (the exact function to modify)

**Current** (`selectors/reviews.py` lines 38–42):
```python
return (
    Review.objects.active()
    .filter(organisation_id=organisation_id)
    .select_related("shop", "shop__region", "replied_by")
)
```

**After change** — add `.prefetch_related("tags")` as the last chain call:
```python
return (
    Review.objects.active()
    .filter(organisation_id=organisation_id)
    .select_related("shop", "shop__region", "replied_by")
    .prefetch_related("tags")   # prevents N+1 in ReviewTagSerializer(many=True)
)
```

No other selector changes needed. `list_reviews()` calls `base_reviews_queryset()` so it inherits the prefetch automatically.

---

### `apps/reviews/filters.py` — Add `tags` CharFilter

**Analog:** `apps/reviews/filters.py` lines 28–37 — `filter_has_comment()` and `filter_search()` — both are `method=` filters that take `(self, queryset, name, value)`.

**`filter_has_comment()` pattern** (lines 28–31):
```python
def filter_has_comment(self, queryset, name, value):  # type: ignore[no-untyped-def]
    if value:
        return queryset.exclude(comment="")
    return queryset.filter(comment="")
```

**`filter_search()` pattern** (lines 33–37):
```python
def filter_search(self, queryset, name, value):  # type: ignore[no-untyped-def]
    if not value:
        return queryset
    q = SearchQuery(value, config="english")
    return queryset.filter(Q(search_vector=q) | Q(reviewer_display_name__icontains=value))
```

**Add to `ReviewFilterSet`** — declare field in class body alongside existing filters, then add method:
```python
# In class body (after existing filter declarations at lines 14–22):
tags = django_filters.CharFilter(field_name="", method="filter_tags")
# field_name="" prevents django-filter from resolving "tags" as a model field
# (it is now a RelatedManager, not a DB column — auto-resolution would fail)

# Method on ReviewFilterSet:
def filter_tags(self, queryset, name, value):  # type: ignore[no-untyped-def]
    if not value:
        return queryset
    tag_labels = [t.strip() for t in value.split(",") if t.strip()]
    for label in tag_labels:
        queryset = queryset.filter(tags__label__iexact=label)
    return queryset.distinct()
    # .distinct() is required: chained reverse-FK joins produce duplicate rows
    # when a review has multiple ReviewTag rows. Without it pagination counts
    # are inflated (Pitfall 5 in RESEARCH.md).
```

---

### `apps/reviews/views.py` — Add `tags` @action

**Analog:** `apps/reviews/views.py` lines 89–117 — `stats` @action (`detail=False`, `methods=["get"]`, uses `self.filter_queryset(self.get_queryset())` internally). The new `tags` action is also `detail=False` but queries `ReviewTag` directly (not through `get_queryset()`), so org scoping must be explicit.

**`stats` @action pattern** (lines 89–117):
```python
@action(detail=False, methods=["get"], url_path="stats")
def stats(self, request: Request) -> Response:
    """Aggregate stats for the reviews list header cards."""
    qs = self.filter_queryset(self.get_queryset())
    agg = qs.aggregate(
        total=Count("pk"),
        ...
    )
    return Response({...})
```

**`tags` action to add** — mirrors the `stats` action structure but queries `ReviewTag` directly:
```python
@action(detail=False, methods=["get"], url_path="tags")
def tags(self, request: Request) -> Response:
    """Return distinct tag labels + counts scoped to the caller's org.

    ?shop=<id>  — optional, narrows to a single shop.
    Staff users see only tags from their accessible shops.
    """
    user = request.user
    org_id = getattr(user, "organisation_id", None)
    if org_id is None:
        return Response([])

    from apps.reviews.models import ReviewTag  # local import — avoids circular at module load

    qs = ReviewTag.objects.filter(review__shop__organisation_id=org_id)

    shop_id = request.query_params.get("shop")
    if shop_id:
        qs = qs.filter(review__shop_id=shop_id)

    if getattr(user, "role", None) == User.Role.STAFF_ADMIN:
        raw_pk = user.pk
        if raw_pk is None:
            return Response([])
        user_id: int = raw_pk
        qs = qs.filter(review__shop_id__in=get_accessible_shop_ids(user_id=user_id))

    result = (
        qs.values("label")
        .annotate(count=Count("id"))
        .order_by("-count")
    )
    return Response([{"label": row["label"], "count": row["count"]} for row in result])
```

**Import additions needed at top of `views.py`** (line 8 area, existing `Count` already imported):
```python
# Count is already imported at line 8. No new imports needed beyond ReviewTag
# which is brought in via local import inside the action to avoid circular deps.
```

---

### `apps/reviews/tests/factories.py` — Remove `tags` field; add `ReviewTagFactory`

**Analog:** `apps/reviews/tests/factories.py` lines 15–36 — `ReviewFactory` (existing class to modify)

**Remove from `ReviewFactory`** (line 35):
```python
# REMOVE this line from ReviewFactory:
tags: ClassVar[list] = []
```

**Add `ReviewTagFactory` after `ReviewFactory`** — following the same `DjangoModelFactory` pattern:
```python
class ReviewTagFactory(DjangoModelFactory):
    class Meta:
        model = "reviews.ReviewTag"   # string label avoids import-time circular dep

    review = factory.SubFactory(ReviewFactory)
    label = factory.Faker("word")
    polarity = "positive"
```

**Import addition** — add `ReviewTag` to the model import at line 12 once the model exists:
```python
from apps.reviews.models import Review, ReviewTag
```

---

### `frontend/src/widgets/review-management/types.ts` — Extend interfaces

**Analog:** `frontend/src/widgets/review-management/types.ts` lines 54–66 — `ReviewFilterParams` interface (the interface to extend)

**`ReviewFilterParams` extension** (add after `page?: number` at line 65):
```typescript
tags?: string[];   // comma-joined for ?tags=A,B; array here for multi-select UI
```

**New `TagOption` interface** — add after `ShopOption` at line 93:
```typescript
export interface TagOption {
  label: string;
  count: number;
}
```

`ReviewTag` type at lines 5–8 is unchanged — confirmed by D-11.

---

### `frontend/src/widgets/review-management/api.ts` — Add `fetchTagList()` + extend `buildQs()`

**Analog:** `frontend/src/widgets/review-management/api.ts`

**`fetchReviewStats()` pattern** (lines 85–93) — exact pattern for `fetchTagList()`:
```typescript
export async function fetchReviewStats(params?: ReviewFilterParams): Promise<ReviewStats> {
  const qs = params ? buildQs(params) : "";
  const resp = await fetch(`/api/v1/reviews/stats/${qs}`, {
    method: "GET",
    headers: headers("GET"),
    credentials: "same-origin",
  });
  return (await handle(resp)) as ReviewStats;
}
```

**`fetchTagList()` to add** (same pattern, different endpoint):
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

**Add `TagOption` to imports at line 1:**
```typescript
import type {
  ReviewFilterParams,
  ReviewListResponse,
  ReviewRow,
  ReviewStats,
  SyncingResponse,
  TagOption,             // NEW
} from "./types";
```

**`buildQs()` extension** — add after `params.page` check at line 52:
```typescript
if (params.tags && params.tags.length > 0) {
  u.set("tags", params.tags.join(","));
}
```

---

### `frontend/src/widgets/review-management/ReviewFilters.tsx` — Add `TagsFilter`

**Analog:** `frontend/src/widgets/review-management/ReviewFilters.tsx`

**`DraftFilters` interface extension** (lines 5–14) — add `tags` field:
```typescript
interface DraftFilters {
  search: string;
  shop?: number;
  rating?: 1 | 2 | 3 | 4 | 5;
  sentiment?: "positive" | "neutral" | "negative";
  is_replied?: boolean;
  has_comment?: boolean;
  from_date?: string;
  to_date?: string;
  tags?: string[];   // NEW
}
```

**`Props` interface extension** (lines 16–21) — add `onTagClick` prop for chip-initiated filters:
```typescript
interface Props {
  shops: ShopOption[];
  filters: ReviewFilterParams;
  onApply: (draft: DraftFilters) => void;
  onReset: () => void;
  availableTags?: TagOption[];   // fetched by parent; passed in for dropdown list
}
```

**Sentiment select pattern to copy** (lines 191–215) — `TagsFilter` is a multi-select dropdown following the same `<label>/<FilterLabel>/<select>` structure. However, tags need multi-select with search, so replace the `<select>` with a custom dropdown:

The existing Sentiment block (lines 191–215) is the closest structural analog for the label + container wrapper. The multi-select implementation differs — use a `<div>` with a search `<input>` and checkboxes inside (client-side filter on `availableTags`), not a native `<select multiple>`. Pattern for the outer wrapper:
```tsx
{/* Tags multi-select — Row 2 addition or new Row 3 */}
<label className="flex flex-col gap-1.5 min-w-0">
  <FilterLabel icon={<Tag size={15} />} label="Tags" />
  {/* custom dropdown body — search input + checkbox list */}
</label>
```

**`hasActiveFilters` extension** (lines 85–94) — add `tags` check:
```typescript
const hasActiveFilters = Boolean(
  filters.search ||
    filters.shop !== undefined ||
    filters.rating !== undefined ||
    filters.sentiment ||
    filters.is_replied !== undefined ||
    filters.has_comment !== undefined ||
    filters.from_date ||
    filters.to_date ||
    (filters.tags && filters.tags.length > 0),   // NEW
);
```

**`handleReset` extension** (lines 96–108) — add tags reset:
```typescript
const handleReset = () => {
  setDraft({
    search: "",
    shop: undefined,
    rating: undefined,
    sentiment: undefined,
    is_replied: undefined,
    has_comment: undefined,
    from_date: undefined,
    to_date: undefined,
    tags: [],   // NEW
  });
  onReset();
};
```

**Import addition** — `TagOption` is needed in the component:
```typescript
import type { ReviewFilterParams, ShopOption, TagOption } from "./types";
```

---

### `frontend/src/widgets/review-management/ReviewTable.tsx` — Chip `<span>` → `<button>`

**Analog:** `frontend/src/widgets/review-management/ReviewTable.tsx` lines 204–214 — the tags column chip rendering block

**`Props` interface extension** (lines 66–76) — add `onTagClick` prop:
```typescript
interface Props {
  rows: ReviewRow[];
  loading: boolean;
  emptyState: ReactNode;
  onReply: (row: ReviewRow) => void;
  expandedRowId: number | null;
  onComposerSuccess: (row: ReviewRow) => void;
  onComposerClose: () => void;
  showFullComment: Map<number, boolean>;
  onToggleShowFullComment: (reviewId: number) => void;
  onTagClick?: (label: string) => void;   // NEW — undefined = chips are not clickable
}
```

**Current chip rendering** (lines 205–213):
```tsx
{r.tags.slice(0, 4).map((tag) => (
  <span
    key={`${tag.label}-${tag.polarity}`}
    className="inline-flex items-center px-1.5 py-0.5 text-[11px] font-medium rounded"
    style={TAG_STYLES[tag.polarity]}
  >
    {tag.label}
  </span>
))}
```

**After change — `<span>` → `<button>`** (same Tailwind classes; add `onClick` and cursor):
```tsx
{r.tags.slice(0, 4).map((tag) => (
  <button
    key={`${tag.label}-${tag.polarity}`}
    type="button"
    onClick={(e) => {
      e.stopPropagation();
      onTagClick?.(tag.label);
    }}
    className="inline-flex items-center px-1.5 py-0.5 text-[11px] font-medium rounded cursor-pointer hover:opacity-80 transition-opacity"
    style={TAG_STYLES[tag.polarity]}
    aria-label={`Filter by tag: ${tag.label}`}
  >
    {tag.label}
  </button>
))}
```

**Click-expand pattern analog** (lines 165–172) — `e.stopPropagation()` is already used on the "Read more" button and is the established pattern for nested click handlers inside a table row:
```tsx
onClick={(e) => {
  e.stopPropagation();
  onToggleShowFullComment(r.id);
}}
```

---

### `frontend/src/widgets/review-management/ReviewManagementWidget.tsx` — Wire `onTagClick`

**Analog:** `frontend/src/widgets/review-management/ReviewManagementWidget.tsx` lines 146–158 — `onApply` handler passed to `ReviewFilters`

**`onTagClick` handler to add** (add near `handleReplyCtaClick` at line 126):
```typescript
const handleTagClick = (label: string) => {
  // Chip click applies immediately — bypasses Apply button (Pitfall 6 in RESEARCH.md).
  // applyFilters merges the new tags array into the active filter state.
  const currentTags = filters.tags ?? [];
  const alreadyActive = currentTags.includes(label);
  const newTags = alreadyActive
    ? currentTags.filter((t) => t !== label)   // toggle off
    : [...currentTags, label];                  // toggle on (additive)
  applyFilters({ tags: newTags.length > 0 ? newTags : undefined });
};
```

**Pass `onTagClick` to `ReviewTable`** (lines 165–175):
```tsx
<ReviewTable
  rows={rows}
  loading={loading}
  emptyState={emptyState}
  onReply={handleReplyCtaClick}
  expandedRowId={openComposerId}
  showFullComment={showFullComment}
  onToggleShowFullComment={toggleShowFullComment}
  onTagClick={handleTagClick}    // NEW
  onComposerSuccess={(updated) => { replaceRow(updated); }}
  onComposerClose={() => setOpenComposerId(null)}
/>
```

**`applyFilters` call extension** (lines 146–158) — extend the Draft→Params mapping to pass `tags`:
```typescript
onApply={(draft) =>
  applyFilters({
    search: draft.search || undefined,
    shop: draft.shop,
    rating: draft.rating,
    sentiment: draft.sentiment,
    is_replied: draft.is_replied,
    has_comment: draft.has_comment,
    from_date: draft.from_date,
    to_date: draft.to_date,
    tags: draft.tags && draft.tags.length > 0 ? draft.tags : undefined,   // NEW
  })
}
```

**Stats `useEffect` dependency array** (lines 87–97) — add `filters.tags` to the dep array so stats refresh when tags filter changes:
```typescript
useEffect(() => {
  ...
}, [
  filters.shop,
  filters.sentiment,
  filters.rating,
  filters.is_replied,
  filters.has_comment,
  filters.from_date,
  filters.to_date,
  filters.search,
  filters.tags,   // NEW
]);
```

---

## Shared Patterns

### `transaction.atomic()` block structure
**Source:** `apps/reviews/services/enrichment.py` lines 86–110
**Apply to:** Both `_persist_success()` and `_persist_success_no_comment()` modifications
```python
with transaction.atomic():
    Review.objects.filter(pk=review.pk).update(...)     # update Review fields
    ReviewTag.objects.filter(review_id=review.pk).delete()   # idempotent clear
    ReviewTag.objects.bulk_create([...])                 # write new tag rows
    # Optional: AiUsageLog.objects.create(...)
# AFTER commit — emit progress / other side effects
```

### Org-scoping for direct model queries (bypassing `get_queryset()`)
**Source:** `apps/reviews/views.py` lines 57–66 — `ReviewViewSet.get_queryset()` org + staff scoping
**Apply to:** `tags` @action in `ReviewViewSet`
```python
org_id = getattr(user, "organisation_id", None)
if org_id is None:
    return Response([])
qs = SomeModel.objects.filter(review__shop__organisation_id=org_id)
if getattr(user, "role", None) == User.Role.STAFF_ADMIN:
    user_id: int = user.pk
    qs = qs.filter(review__shop_id__in=get_accessible_shop_ids(user_id=user_id))
```

### `e.stopPropagation()` on nested row click handlers
**Source:** `frontend/src/widgets/review-management/ReviewTable.tsx` lines 166–170
**Apply to:** Tag chip `onClick` in the tags column accessor
```tsx
onClick={(e) => {
  e.stopPropagation();
  onTagClick?.(tag.label);
}}
```

### API fetch function shape
**Source:** `frontend/src/widgets/review-management/api.ts` lines 85–93 (`fetchReviewStats`)
**Apply to:** `fetchTagList()` in `api.ts`
```typescript
export async function fetchSomething(param?: Type): Promise<ReturnType> {
  const qs = param ? `?param=${param}` : "";
  const resp = await fetch(`/api/v1/reviews/endpoint/${qs}`, {
    method: "GET",
    headers: headers("GET"),
    credentials: "same-origin",
  });
  return (await handle(resp)) as ReturnType;
}
```

---

## No Analog Found

None — all files have direct analogs in the codebase. Pattern confidence is HIGH for all 12 files.

---

## Metadata

**Analog search scope:** `apps/reviews/`, `apps/shops/`, `apps/common/`, `frontend/src/widgets/review-management/`
**Files read directly:** 14 source files
**Pattern extraction date:** 2026-05-21
