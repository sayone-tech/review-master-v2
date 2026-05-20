# Phase 17: Tag Rework — ReviewTag Model and Filter - Context

**Gathered:** 2026-05-18
**Status:** Ready for planning

<domain>
## Phase Boundary

Replace the current `Review.tags` JSONField (a blob of `{label, polarity}` dicts) with a proper `ReviewTag` relational model. Update the AI enrichment pipeline to write rows into the new table. Add a multi-select tag filter (with search) to the reviews UI, and make tag chips on review rows clickable to filter. Remove the JSONField from `Review` once the new model is in place.

**Out of scope:** Tag management UI (rename/merge/delete), predefined taxonomy, per-brand tag analytics, tag versioning.

</domain>

<decisions>
## Implementation Decisions

### Tag storage model
- **D-01:** New model `ReviewTag(id, review_id, label, polarity)` — simple per-review rows, one row per tag per review. No org-level catalog. The filter dropdown derives distinct labels via `SELECT DISTINCT lower(label) WHERE review__shop__organisation = org`.
- **D-02:** `ReviewTag` lives in the `reviews` app (`apps/reviews/models.py`). FK to `Review` with `on_delete=CASCADE`.
- **D-03:** `label` is stored title-cased on insert (e.g. `"cleanliness"` → `"Cleanliness"`). Deduplication is case-insensitive per org — the dropdown normalises to lower-case for grouping.
- **D-04:** `polarity` is `CharField` with choices matching the existing `Literal["positive", "negative", "neutral"]` enum. The polarity stays on the per-review tag row (not on a shared catalog entry), because the same topic (e.g. "Cleanliness") can be positive in one review and negative in another.
- **D-05:** Add `db_index=True` on `ReviewTag.label` and a composite index on `(review_id, label)` to support the dropdown query efficiently.

### JSONField removal
- **D-06:** `Review.tags` JSONField is **removed** from the model in this phase. A migration drops the column. No backfill — production data will be cleared before deployment. The serializer (`ShopReadSerializer` / `ReviewReadSerializer`) switches from `tags` JSONField to the `ReviewTag` reverse relation.
- **D-07:** The OpenAI parser (`EnrichmentResult.tags`) keeps its Pydantic `Tag` model shape for now — the enrichment service writes each tag as a `ReviewTag` row instead of appending to the JSONField.

### Enrichment service changes
- **D-08:** `enrich_review()` in `apps/reviews/services/enrichment.py`: after GPT response is parsed, replace `review.tags = [...]` + `review.save()` with `ReviewTag.objects.bulk_create([ReviewTag(review=review, label=tag.label.title(), polarity=tag.polarity) for tag in result.tags])`. First delete existing tags for the review before bulk_create (idempotent re-enrichment).
- **D-09:** Idempotency: `ReviewTag.objects.filter(review=review).delete()` before bulk_create so re-enrichment is safe.

### API / serializer
- **D-10:** `ReviewReadSerializer` exposes tags as a nested list: `tags: [{label, polarity}]` — same JSON shape as before for frontend compatibility. Use `ReviewTagSerializer` as a nested read serializer on a `tags` field with `many=True`.
- **D-11:** The frontend `ReviewTag` TypeScript type remains `{label: string, polarity: TagPolarity}` — no frontend type changes needed beyond wiring the filter.

### Tag filter — UI
- **D-12:** Add a **Tags multi-select dropdown with search** to `ReviewFilters.tsx`, alongside the existing Sentiment and Star filters. The dropdown lists all distinct tags for the current org (or shop if a shop filter is active). Source: a new API endpoint `GET /api/v1/reviews/tags/?shop={id}` that returns `[{label, count}]`.
- **D-13:** **Clickable tag chips** on review rows — clicking a chip in the ReviewTable adds that label to the active tag filter. This is additive (multi-select, not replace).
- **D-14:** The tag filter is passed to the reviews list endpoint as `?tags=Cleanliness,Wait+Time` (comma-separated). The backend filters with `ReviewTag.objects.filter(label__iexact=tag)` per tag, using AND semantics (a review must have ALL selected tags).

### Tag filter — backend
- **D-15:** New endpoint `GET /api/v1/reviews/tags/` on `ReviewViewSet` (`@action(detail=False, methods=["get"])`). Returns `[{label, count}]` for the caller's org, optionally scoped by `?shop=<id>`. Query: `ReviewTag.objects.filter(review__shop__organisation=org).values("label").annotate(count=Count("id")).order_by("-count")`.
- **D-16:** The existing `ReviewViewSet.list` accepts `?tags=` query param. Add a `tags` field to the existing `ReviewFilterSet` using a `CharFilter` that splits on comma and applies `reviewtag__label__iexact` with AND chaining via `.filter()` calls.

### Claude's Discretion
- Exact migration number (follows latest migration in `apps/reviews/migrations/`)
- Whether to add `GinIndex` on `label` or stick with standard `db_index=True` (prefer standard unless query count tests show it's needed)
- Whether `ReviewTagSerializer` is a standalone class or inline `serializers.Serializer`

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Existing code to extend
- `apps/reviews/models.py` — `Review` model with current `tags = JSONField` (to be removed)
- `apps/reviews/serializers.py` — `ReviewReadSerializer` (replace JSONField `tags` with nested ReviewTag)
- `apps/reviews/services/enrichment.py` — `enrich_review()` (switch from JSONField write to ReviewTag bulk_create)
- `apps/integrations/openai/parser.py` — `Tag` Pydantic model + `EnrichmentResult.tags` (no change needed)
- `apps/reviews/views.py` — `ReviewViewSet` (add `tags` action + extend FilterSet)
- `frontend/src/widgets/review-management/ReviewFilters.tsx` — add tag multi-select
- `frontend/src/widgets/review-management/ReviewTable.tsx` — make chips clickable
- `frontend/src/widgets/review-management/types.ts` — `ReviewTag` type (no change)

### Architecture constraints
- `CLAUDE.md` §5 — Services/selectors pattern; `enrich_review()` is the sole entry point
- `CLAUDE.md` §6 — No-N+1; tag rows must be prefetched (`prefetch_related("tags")`) on the reviews queryset
- `CLAUDE.md` §24 — Order: models → migration → serializer → service → tests → views → frontend

</canonical_refs>

<code_context>
## Existing Code Insights

### Current tag write path (to be replaced)
- `apps/reviews/services/enrichment.py`: `review.tags = [{"label": t.label, "polarity": t.polarity} for t in result.tags]` + `review.save(update_fields=["tags", ...])`
- After Phase 17: delete existing ReviewTag rows → bulk_create new rows

### Current tag read path (to be adapted)
- `apps/reviews/serializers.py`: `tags = serializers.JSONField(read_only=True)` — replace with `tags = ReviewTagSerializer(many=True, read_only=True)` + `prefetch_related("tags")` on the queryset in the selector

### Existing filter pattern
- `apps/reviews/views.py` uses `django-filter` with `ReviewFilterSet` — extend this with a `tags` `CharFilter`
- `frontend/src/widgets/review-management/ReviewFilters.tsx` has existing multi-select pattern for Sentiment — reuse for Tags

### Reusable frontend assets
- `ReviewFilters.tsx` — existing filter pill/dropdown components for Sentiment; Tags filter follows same pattern
- `TAG_STYLES` in `ReviewTable.tsx` — polarity-to-style map already exists; chip click handler is new

</code_context>

<deferred>
## Deferred Ideas

- **Tag management UI** (rename, merge, delete tags) — own phase, needs org-level catalog first
- **Predefined tag taxonomy** — GPT maps to fixed categories — valuable for consistency but requires prompt engineering work; separate phase
- **Tag analytics** — "most common tags this week" on dashboard — separate dashboard phase
- **Brand-scoped tag filtering** — filtering by tags across all shops in an org — separate phase

</deferred>

---

*Phase: 17-tag-rework-reviewtag-model-and-filter*
*Context gathered: 2026-05-18*
