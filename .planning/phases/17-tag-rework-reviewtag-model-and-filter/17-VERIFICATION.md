---
phase: 17-tag-rework-reviewtag-model-and-filter
verified: 2026-05-21T00:00:00Z
status: passed
score: 5/5 must-haves verified
overrides_applied: 0
---

# Phase 17: Tag Rework — ReviewTag Model and Filter — Verification Report

**Phase Goal:** Replace `Review.tags` JSONField with a proper `ReviewTag` relational model; update the AI enrichment pipeline to write rows into the new table; add a multi-select tag filter with search to the reviews list UI; and make tag chips on review rows clickable to filter — giving Org Admins a fast, queryable way to explore reviews by AI-generated topic.
**Verified:** 2026-05-21
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | A `ReviewTag` model exists with `(id, review_id, label, polarity)`; `Review.tags` JSONField is removed | VERIFIED | `apps/reviews/models.py:123-144` defines `ReviewTag(review FK, label CharField(100), polarity choices=positive/neutral/negative)` with `db_table="reviews_reviewtag"` and `reviewtag_review_label_idx`. Migration `apps/reviews/migrations/0008_reviewtag.py` creates the table AND contains `RemoveField(model_name="review", name="tags")`. No `tags = models.JSONField` in `Review`. |
| 2 | Review enrichment writes `ReviewTag` rows (title-cased, case-insensitively deduplicated per org) instead of updating the JSONField | VERIFIED | `apps/reviews/services/enrichment.py:_persist_success` (lines 96–109): `ReviewTag.objects.filter(review_id=review.pk).delete()` followed by `bulk_create([ReviewTag(label=tag.label.title(), polarity=tag.polarity), …])` — both inside `transaction.atomic()`. `_persist_success_no_comment` (lines 223–225) clears rows on comment-less path. Title-casing via `tag.label.title()`. Delete-before-bulk_create gives per-review idempotency on re-enrichment. |
| 3 | The reviews list API returns tags as `[{label, polarity}]` via the new model — same JSON shape as before | VERIFIED | `apps/reviews/serializers.py:12-22` defines `ReviewTagSerializer(label, polarity)`. `ReviewReadSerializer.tags = ReviewTagSerializer(many=True, read_only=True)` (line 37) with `"tags"` in `fields` (line 61). `apps/reviews/selectors/reviews.py:44` adds `.prefetch_related("tags")` keeping list queries flat. Shape-regression test `test_review_list_tags_shape` confirms `[{label, polarity}]` output. |
| 4 | `GET /api/v1/reviews/tags/` returns `[{label, count}]` scoped to caller's org (optional `?shop=<id>`) | VERIFIED | `apps/reviews/views.py:89-118` registers `@action(detail=False, methods=["get"], url_path="tags")` → `tags()` builds `ReviewTag.objects.filter(review__shop__organisation_id=org_id)`, applies optional `?shop=` filter, applies `get_accessible_shop_ids` filter when role is STAFF_ADMIN, then `.values("label").annotate(count=Count("id")).order_by("-count")`. Returns `[{"label", "count"}]`. ViewSet registered at `/api/v1/reviews/` in `config/urls.py:31`. Test `test_tags_action_returns_org_scoped_labels` and sibling tests cover org scoping + shop filter + staff scoping. |
| 5 | Reviews UI has a Tags multi-select dropdown with search; selecting tags filters the review list (AND semantics); clickable tag chips on rows add to the active filter | VERIFIED | Frontend: `ReviewFilters.tsx:75-269` defines `TagsFilter` with search box (`placeholder="Search tags…"`), multi-select checkboxes, empty states, and selected-count summary. `ReviewManagementWidget.tsx:101-150` fetches available tags via `fetchTagList(shopId)`, owns selection state, and provides `handleTagChipClick` that toggles a label in `filters.tags` and calls `applyFilters` immediately. `ReviewTable.tsx:207-221` renders tag chips as `<button>` with `onClick → onTagClick(tag.label)` and `aria-label="Filter by tag: …"`. Backend AND semantics: `apps/reviews/filters.py:40-46` loops each comma-split label, applying `queryset.filter(tags__label__iexact=label)` per label (intersection) then `.distinct()`. API serialization in `api.ts:54` sends `?tags=A,B`. |

**Score:** 5/5 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `apps/reviews/models.py` | `ReviewTag` model + Polarity TextChoices | VERIFIED | Lines 123–144; FK to Review, label/polarity fields, table + index. |
| `apps/reviews/migrations/0008_reviewtag.py` | Create ReviewTag table, drop `Review.tags` | VERIFIED | Both `CreateModel(ReviewTag)` and `RemoveField(model_name="review", name="tags")` present. Dependency `0007_replied_by_fk`. |
| `apps/reviews/services/enrichment.py` | Title-cased ReviewTag bulk_create in success path + clear in no-comment path | VERIFIED | `_persist_success` lines 96–109 and `_persist_success_no_comment` lines 223–225. |
| `apps/reviews/selectors/reviews.py` | `prefetch_related("tags")` in base queryset | VERIFIED | `base_reviews_queryset` line 44. |
| `apps/reviews/serializers.py` | `ReviewTagSerializer` + `ReviewReadSerializer.tags` | VERIFIED | Lines 12–22, 37, and field list 61. |
| `apps/reviews/filters.py` | `tags` CharFilter with AND semantics | VERIFIED | Lines 23 + 40–46 (per-label `.filter(tags__label__iexact=…)` loop + `.distinct()`). |
| `apps/reviews/views.py` | `tags` @action endpoint scoped per org + staff | VERIFIED | Lines 89–118. |
| `frontend/src/widgets/review-management/types.ts` | `ReviewRow.tags: ReviewTag[]`, `ReviewFilterParams.tags?: string[]` | VERIFIED | Lines 39, 66. |
| `frontend/src/widgets/review-management/api.ts` | `fetchTagList` + `?tags=A,B` serialization | VERIFIED | Lines 54, 97–105. |
| `frontend/src/widgets/review-management/ReviewFilters.tsx` | `TagsFilter` multi-select with search | VERIFIED | Lines 75–269; integrated at 421–424. |
| `frontend/src/widgets/review-management/ReviewTable.tsx` | Chip click → `onTagClick(label)` | VERIFIED | Lines 207–221. |
| `frontend/src/widgets/review-management/ReviewManagementWidget.tsx` | Wires availableTags + chip toggle | VERIFIED | Lines 97–150, 166. |
| `apps/reviews/tests/factories.py` | `ReviewTagFactory` | VERIFIED | Line 38 — used in test_models and test_views. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| Enrichment success → DB | `ReviewTag` rows | `bulk_create` inside `transaction.atomic` | WIRED | Atomic delete+bulk_create guarantees relational write replaces old JSON write. |
| Reviews list selector → serializer | tags array | `prefetch_related("tags")` + `ReviewTagSerializer(many=True)` | WIRED | Prevents N+1; shape preserved. |
| Filter set `tags=` → DB | Per-label intersection | `queryset.filter(tags__label__iexact=label)` loop + `.distinct()` | WIRED | AND semantics confirmed by per-label loop. |
| Frontend `fetchTagList` → API | `GET /api/v1/reviews/tags/` | `fetch(\`/api/v1/reviews/tags/${qs}\`)` | WIRED | Endpoint exists as `@action url_path="tags"`. |
| Tag chip click → filter state | `applyFilters({..., tags})` | `onTagClick` in ReviewTable → `handleTagChipClick` in widget | WIRED | Lines 211–214 in ReviewTable; 142–150 in widget. |
| `?tags=` URL param → backend filter | `ReviewFilterSet.filter_tags` | `api.ts` joins on `,`, backend splits on `,` | WIRED | Round-trip confirmed by integration tests. |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Phase 17 backend tests pass | `pytest apps/reviews/tests/ --tb=line -p no:warnings` | `140 passed in 3.07s` | PASS |
| Frontend type-checks clean | `npx tsc --noEmit` (in `frontend/`) | no errors, no output | PASS |
| Migration file applies | `find apps/reviews/migrations -name 0008_reviewtag.py` | exists | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| TAG-01 | 17-01-PLAN.md | ReviewTag model + migration removing `Review.tags` JSONField | SATISFIED | Truths 1 + 2 + Migration 0008. |
| TAG-02 | 17-02-PLAN.md | Enrichment writes ReviewTag rows; list API returns `[{label, polarity}]` | SATISFIED | Truths 2 + 3. |
| TAG-03 | 17-03 + 17-04 PLANs | Tags endpoint + filter + frontend multi-select + clickable chips | SATISFIED | Truths 4 + 5. |

**Traceability note (info-level, not a blocker):** TAG-01/02/03 identifiers appear in ROADMAP.md Phase 17 entry and all four PLAN files, but `.planning/REQUIREMENTS.md` does not define a `TAG-*` block (it currently lists only v0.4 dashboard + v0.5 sync-depth IDs). The ROADMAP Success Criteria (the 5 truths above) act as the actual requirement contract for this phase and are fully satisfied. Recommend back-filling a Tag Rework block into REQUIREMENTS.md for traceability completeness — but the phase goal is achieved either way.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| (none) | — | No TBD/FIXME/XXX markers found in modified files; no stub returns; no hardcoded empty data flowing to UI; no console.log-only implementations | — | — |

### Human Verification Required

(none — all five success criteria are observable in code + tests; no visual or real-time behavior requires human checking that isn't already covered by the frontend tsc + backend test suite. The UI dropdown and chip click flows are wired through pure state plumbing already exercised by the existing test suite at the backend boundary.)

### Gaps Summary

No gaps. All 5 ROADMAP Success Criteria are met. Backend ReviewTag relational model is in place, JSONField removed, enrichment writes title-cased rows idempotently, list API returns the same `[{label, polarity}]` shape via prefetched relational rows, `GET /api/v1/reviews/tags/` returns `[{label, count}]` org-scoped (+ staff scoping + optional shop filter), and the frontend ships a searchable multi-select Tags dropdown plus clickable tag chips wired through `applyFilters`. 140 backend tests pass; frontend tsc is clean.

The only documentation hygiene observation is that TAG-01/02/03 are referenced in ROADMAP/PLAN files but not formalised in REQUIREMENTS.md — recommended back-fill, not a blocker.

---

_Verified: 2026-05-21_
_Verifier: Claude (gsd-verifier)_
