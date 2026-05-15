# Action Item Categories Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `category` field to `ActionItem` (Quality / Service / Experience / Operations / Other), have OpenAI classify it in the existing enrichment prompt, and surface it as a badge + filter in the React UI.

**Architecture:** Extend the existing single-prompt enrichment flow — one new Literal field in the Pydantic schema, ~40 words added to the system prompt, and a `_CATEGORY_MAP` in `promote_action_items_from_review`. The category is stored on the model and exposed via serializer + django-filter on the backend; the React layer adds a TypeScript type, a `CategoryBadge` component, a new table column, and a filter select.

**Tech Stack:** Django 6 / DRF, Pydantic v2, django-filter, React 18, TypeScript, Tailwind CSS.

---

## File Map

| File | Change |
|---|---|
| `apps/action_items/models.py` | Add `Category` TextChoices + `category` field + index |
| `apps/action_items/migrations/0002_actionitem_category.py` | New migration (auto-generated) |
| `apps/integrations/openai/parser.py` | Add `category` Literal to `ActionItem` Pydantic schema |
| `apps/integrations/openai/prompts.py` | Bump `ENRICHMENT_PROMPT_VERSION` to 2, add category instruction |
| `apps/action_items/services/lifecycle.py` | Add `_CATEGORY_MAP`, pass `category` in `promote_action_items_from_review` |
| `apps/action_items/serializers.py` | Add `category` + `category_display` read fields to `_ActionItemBaseRead` |
| `apps/action_items/filters.py` | Add `MultipleChoiceFilter` for `category` |
| `apps/action_items/tests/test_models.py` | Test `category` defaults to `OTHER` |
| `apps/action_items/tests/test_services.py` | Test category mapping and fallback in `promote_action_items_from_review` |
| `apps/action_items/tests/factories.py` | Add `category` field to `ActionItemFactory` |
| `frontend/src/widgets/action-items/types.ts` | Add `ActionItemCategory` type + `category` fields |
| `frontend/src/widgets/action-items/CategoryBadge.tsx` | New component — category pill badge |
| `frontend/src/widgets/action-items/ActionItemTable.tsx` | Add CATEGORY column using `CategoryBadge` |
| `frontend/src/widgets/action-items/ActionItemFilters.tsx` | Add Category filter select |

---

## Task 1: Model — add Category field

**Files:**
- Modify: `apps/action_items/models.py`
- Test: `apps/action_items/tests/test_models.py`

- [ ] **Step 1: Write the failing test**

Add to `apps/action_items/tests/test_models.py`:

```python
@pytest.mark.django_db
def test_action_item_category_defaults_to_other() -> None:
    item = ActionItemFactory()
    assert item.category == ActionItem.Category.OTHER
```

- [ ] **Step 2: Run it and confirm it fails**

```bash
python -m pytest apps/action_items/tests/test_models.py::test_action_item_category_defaults_to_other -v
```

Expected: `AttributeError: type object 'ActionItem' has no attribute 'Category'`

- [ ] **Step 3: Add `Category` choices and field to the model**

In `apps/action_items/models.py`, add after the `Source` class:

```python
class Category(models.TextChoices):
    QUALITY = "QUALITY", "Quality"
    SERVICE = "SERVICE", "Service"
    EXPERIENCE = "EXPERIENCE", "Experience"
    OPERATIONS = "OPERATIONS", "Operations"
    OTHER = "OTHER", "Other"
```

Add the field after the `source` field (line ~58):

```python
category = models.CharField(
    max_length=15,
    choices=Category.choices,
    default=Category.OTHER,
    db_index=True,
)
```

Add a new index inside `Meta.indexes`:

```python
models.Index(fields=["organisation", "category"], name="ai_org_category_idx"),
```

- [ ] **Step 4: Generate and apply the migration**

```bash
python manage.py makemigrations action_items --name actionitem_category
python manage.py migrate
```

Expected: migration `0002_actionitem_actionitem_category.py` (or similar) created and applied cleanly.

- [ ] **Step 5: Run the test and confirm it passes**

```bash
python -m pytest apps/action_items/tests/test_models.py::test_action_item_category_defaults_to_other -v
```

Expected: PASS

- [ ] **Step 6: Update factory**

In `apps/action_items/tests/factories.py`, add `category` to `ActionItemFactory`:

```python
category = ActionItem.Category.OTHER
```

- [ ] **Step 7: Run full model test suite to confirm no regressions**

```bash
python -m pytest apps/action_items/tests/test_models.py -v
```

Expected: all tests pass.

- [ ] **Step 8: Commit**

```bash
git add apps/action_items/models.py \
        apps/action_items/migrations/ \
        apps/action_items/tests/factories.py \
        apps/action_items/tests/test_models.py
git commit -m "feat(action-items): add Category field with db_index and migration"
```

---

## Task 2: AI Layer — Pydantic schema + prompt + lifecycle mapping

**Files:**
- Modify: `apps/integrations/openai/parser.py`
- Modify: `apps/integrations/openai/prompts.py`
- Modify: `apps/action_items/services/lifecycle.py`
- Test: `apps/action_items/tests/test_services.py`

- [ ] **Step 1: Write failing tests for category mapping**

Add to `apps/action_items/tests/test_services.py`:

```python
@pytest.mark.django_db
def test_promote_maps_category_correctly():
    org = OrganisationFactory()
    shop = ShopFactory(organisation=org)
    review = ReviewFactory(
        organisation=org,
        shop=shop,
        extracted_action_items=[
            {"title": "Fix cold food", "scope": "shop", "priority": "high", "category": "quality"},
            {"title": "Train staff", "scope": "brand", "priority": "medium", "category": "service"},
        ],
    )
    promote_action_items_from_review(review=review)
    items = {i.title: i for i in ActionItem.objects.filter(source_review=review)}
    assert items["Fix cold food"].category == ActionItem.Category.QUALITY
    assert items["Train staff"].category == ActionItem.Category.SERVICE


@pytest.mark.django_db
def test_promote_category_falls_back_to_other_when_missing():
    org = OrganisationFactory()
    shop = ShopFactory(organisation=org)
    review = ReviewFactory(
        organisation=org,
        shop=shop,
        extracted_action_items=[
            # No category key — old enrichment format
            {"title": "Fix entrance sign", "scope": "shop", "priority": "low"},
        ],
    )
    promote_action_items_from_review(review=review)
    item = ActionItem.objects.get(source_review=review)
    assert item.category == ActionItem.Category.OTHER


@pytest.mark.django_db
def test_promote_category_falls_back_to_other_on_unknown_value():
    org = OrganisationFactory()
    shop = ShopFactory(organisation=org)
    review = ReviewFactory(
        organisation=org,
        shop=shop,
        extracted_action_items=[
            {"title": "Do something", "scope": "shop", "priority": "low", "category": "invented"},
        ],
    )
    promote_action_items_from_review(review=review)
    item = ActionItem.objects.get(source_review=review)
    assert item.category == ActionItem.Category.OTHER
```

- [ ] **Step 2: Run tests and confirm they fail**

```bash
python -m pytest apps/action_items/tests/test_services.py::test_promote_maps_category_correctly \
                 apps/action_items/tests/test_services.py::test_promote_category_falls_back_to_other_when_missing \
                 apps/action_items/tests/test_services.py::test_promote_category_falls_back_to_other_on_unknown_value -v
```

Expected: FAIL — `TypeError` or `unexpected keyword argument 'category'`

- [ ] **Step 3: Update the Pydantic schema**

In `apps/integrations/openai/parser.py`, replace the `ActionItem` class:

```python
class ActionItem(BaseModel):
    title: str
    scope: Literal["shop", "brand"]
    priority: Literal["high", "medium", "low"]
    category: Literal["quality", "service", "experience", "operations", "other"]
```

- [ ] **Step 4: Update the system prompt**

In `apps/integrations/openai/prompts.py`:

1. Bump the version constant:
```python
ENRICHMENT_PROMPT_VERSION = 2
```

2. In `SYSTEM_PROMPT`, replace the `action_items` line ending with `"and a 'priority' ('high'|'medium'|'low').\n"` so it becomes:

```python
"  - action_items: list of 0 to 5 actionable next steps. Each item has a "
"'title' (under 200 chars, English imperative phrase), a 'scope' "
"(use 'shop' for issues specific to the location like 'Fix broken AC'; "
"use 'brand' for systemic patterns like 'Improve staff training across "
"all shops'), a 'priority' ('high'|'medium'|'low'), and a 'category': "
"classify as 'quality' (product/food standard), 'service' (staff behaviour, "
"responsiveness), 'experience' (ambience, atmosphere, overall feel), "
"'operations' (wait time, delivery, logistics, processes), or 'other' when "
"none fit.\n"
```

- [ ] **Step 5: Add `_CATEGORY_MAP` and wire it in `promote_action_items_from_review`**

In `apps/action_items/services/lifecycle.py`, add after `_SCOPE_MAP`:

```python
_CATEGORY_MAP = {
    "quality": ActionItem.Category.QUALITY,
    "service": ActionItem.Category.SERVICE,
    "experience": ActionItem.Category.EXPERIENCE,
    "operations": ActionItem.Category.OPERATIONS,
    "other": ActionItem.Category.OTHER,
}
```

In `promote_action_items_from_review`, inside the `for entry in items:` loop, add after `priority_val`:

```python
category_val = _CATEGORY_MAP.get(
    (entry.get("category") or "").lower(), ActionItem.Category.OTHER
)
```

And pass it when constructing `ActionItem`:

```python
to_create.append(
    ActionItem(
        organisation_id=review.organisation_id,
        title=title[:200],
        scope=scope_val,
        priority=priority_val,
        category=category_val,
        source=ActionItem.Source.AI,
        shop_id=review.shop_id if scope_val == ActionItem.Scope.SHOP else None,
        source_review=review,
    )
)
```

- [ ] **Step 6: Run the new tests and confirm they pass**

```bash
python -m pytest apps/action_items/tests/test_services.py::test_promote_maps_category_correctly \
                 apps/action_items/tests/test_services.py::test_promote_category_falls_back_to_other_when_missing \
                 apps/action_items/tests/test_services.py::test_promote_category_falls_back_to_other_on_unknown_value -v
```

Expected: all 3 PASS

- [ ] **Step 7: Run the full services test suite to confirm no regressions**

```bash
python -m pytest apps/action_items/tests/test_services.py -v
```

Expected: all tests pass.

- [ ] **Step 8: Commit**

```bash
git add apps/integrations/openai/parser.py \
        apps/integrations/openai/prompts.py \
        apps/action_items/services/lifecycle.py \
        apps/action_items/tests/test_services.py
git commit -m "feat(enrichment): add category to Pydantic schema, prompt, and lifecycle mapping"
```

---

## Task 3: API Layer — serializer + filter

**Files:**
- Modify: `apps/action_items/serializers.py`
- Modify: `apps/action_items/filters.py`
- Test: `apps/action_items/tests/test_views.py`

- [ ] **Step 1: Write failing tests**

Add to `apps/action_items/tests/test_views.py` (find the existing list endpoint test class and add alongside):

```python
@pytest.mark.django_db
def test_list_response_includes_category_fields(org_admin_client, org):
    ActionItemFactory(organisation=org, category=ActionItem.Category.QUALITY)
    response = org_admin_client.get("/api/v1/action-items/")
    assert response.status_code == 200
    result = response.json()["results"][0]
    assert result["category_value"] == "QUALITY"
    assert result["category"] == "Quality"


@pytest.mark.django_db
def test_filter_by_category_returns_matching_items(org_admin_client, org):
    ActionItemFactory(organisation=org, category=ActionItem.Category.QUALITY)
    ActionItemFactory(organisation=org, category=ActionItem.Category.SERVICE)
    response = org_admin_client.get("/api/v1/action-items/?category=QUALITY")
    assert response.status_code == 200
    results = response.json()["results"]
    assert len(results) == 1
    assert results[0]["category_value"] == "QUALITY"
```

> **Note:** Check the existing test file for how `org_admin_client` and `org` fixtures are defined — use the same fixture names and import patterns already established in that file.

- [ ] **Step 2: Run the tests and confirm they fail**

```bash
python -m pytest apps/action_items/tests/test_views.py::test_list_response_includes_category_fields \
                 apps/action_items/tests/test_views.py::test_filter_by_category_returns_matching_items -v
```

Expected: FAIL — `KeyError: 'category_value'` and similar.

- [ ] **Step 3: Add category fields to `_ActionItemBaseRead`**

In `apps/action_items/serializers.py`, add two fields to `_ActionItemBaseRead`:

```python
category_value = serializers.CharField(source="category", read_only=True)
category = serializers.CharField(source="get_category_display", read_only=True)
```

Add both to `Meta.fields` list after `"source"`:

```python
"category_value",
"category",
```

And to `read_only_fields` (since the list equals `fields`).

- [ ] **Step 4: Add `MultipleChoiceFilter` for category**

In `apps/action_items/filters.py`, add after the `scope` filter:

```python
category = django_filters.MultipleChoiceFilter(choices=ActionItem.Category.choices)
```

- [ ] **Step 5: Run the new tests and confirm they pass**

```bash
python -m pytest apps/action_items/tests/test_views.py::test_list_response_includes_category_fields \
                 apps/action_items/tests/test_views.py::test_filter_by_category_returns_matching_items -v
```

Expected: both PASS

- [ ] **Step 6: Run full views test suite**

```bash
python -m pytest apps/action_items/tests/test_views.py -v
```

Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add apps/action_items/serializers.py \
        apps/action_items/filters.py \
        apps/action_items/tests/test_views.py
git commit -m "feat(action-items): expose category in serializer and add category filter"
```

---

## Task 4: Frontend — TypeScript types + CategoryBadge component

**Files:**
- Modify: `frontend/src/widgets/action-items/types.ts`
- Create: `frontend/src/widgets/action-items/CategoryBadge.tsx`

- [ ] **Step 1: Add `ActionItemCategory` type and update interfaces**

In `frontend/src/widgets/action-items/types.ts`:

Add after `ActionItemSource`:

```typescript
export type ActionItemCategory =
  | "QUALITY"
  | "SERVICE"
  | "EXPERIENCE"
  | "OPERATIONS"
  | "OTHER";
```

Add to `ActionItemListRow` interface (after `source`):

```typescript
category_value: ActionItemCategory;
category: string;
```

Add to `ListParams` interface (after `scope`):

```typescript
category?: ActionItemCategory;
```

- [ ] **Step 2: Create `CategoryBadge` component**

Create `frontend/src/widgets/action-items/CategoryBadge.tsx`:

```tsx
import type { ActionItemCategory } from "./types";

const CATEGORY_STYLES: Record<ActionItemCategory, { bg: string; text: string; dot: string }> = {
  QUALITY: {
    bg: "bg-blue-50",
    text: "text-blue-700",
    dot: "bg-blue-400",
  },
  SERVICE: {
    bg: "bg-purple-50",
    text: "text-purple-700",
    dot: "bg-purple-400",
  },
  EXPERIENCE: {
    bg: "bg-teal-50",
    text: "text-teal-700",
    dot: "bg-teal-400",
  },
  OPERATIONS: {
    bg: "bg-orange-50",
    text: "text-orange-700",
    dot: "bg-orange-400",
  },
  OTHER: {
    bg: "bg-zinc-100",
    text: "text-zinc-500",
    dot: "bg-zinc-400",
  },
};

interface Props {
  category: ActionItemCategory;
  label: string;
}

export function CategoryBadge({ category, label }: Props) {
  const { bg, text, dot } = CATEGORY_STYLES[category] ?? CATEGORY_STYLES.OTHER;
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[12px] font-medium ${bg} ${text}`}
    >
      <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${dot}`} aria-hidden="true" />
      {label}
    </span>
  );
}
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/widgets/action-items/types.ts \
        frontend/src/widgets/action-items/CategoryBadge.tsx
git commit -m "feat(ui): add ActionItemCategory type and CategoryBadge component"
```

---

## Task 5: Frontend — table column + filter select

**Files:**
- Modify: `frontend/src/widgets/action-items/ActionItemTable.tsx`
- Modify: `frontend/src/widgets/action-items/ActionItemFilters.tsx`

- [ ] **Step 1: Add CATEGORY column to `ActionItemTable`**

In `frontend/src/widgets/action-items/ActionItemTable.tsx`:

Add the import at the top:

```tsx
import { CategoryBadge } from "./CategoryBadge";
```

Add a new column to the `columns` array, after the `scope` column:

```tsx
{
  key: "category",
  label: "CATEGORY",
  skeletonWidth: "100px",
  accessor: (r) => (
    <CategoryBadge category={r.category_value} label={r.category} />
  ),
},
```

- [ ] **Step 2: Add Category filter to `ActionItemFilters`**

In `frontend/src/widgets/action-items/ActionItemFilters.tsx`:

Add the type import at the top:

```tsx
import type { ActionItemCategory, ActionItemScope, ActionItemStatus, ... } from "./types";
```

Add the options constant after `SCOPE_OPTIONS`:

```tsx
const CATEGORY_OPTIONS: { value: ActionItemCategory; label: string }[] = [
  { value: "QUALITY", label: "Quality" },
  { value: "SERVICE", label: "Service" },
  { value: "EXPERIENCE", label: "Experience" },
  { value: "OPERATIONS", label: "Operations" },
  { value: "OTHER", label: "Other" },
];
```

Add `category` to the `DraftFilters` interface:

```tsx
category?: ActionItemCategory;
```

Update the `useState` initializer to include:

```tsx
category: filters.category as ActionItemCategory | undefined,
```

Update `hasActiveFilters` to include `|| filters.category`.

Update `handleReset` to include `category: undefined`.

Add the Category select in Row 1 (after the Scope select, visible to all roles — unlike Scope which is org-admin only):

```tsx
{/* Category */}
<label className="flex flex-col gap-1.5 min-w-0">
  <FilterLabel icon={<Tag size={15} />} label="Category" />
  <div className="relative">
    <select
      aria-label="Filter by category"
      className={selectCls}
      value={draft.category ?? ""}
      onChange={(e) =>
        setDraft((d) => ({
          ...d,
          category: (e.target.value || undefined) as ActionItemCategory | undefined,
        }))
      }
    >
      <option value="">Any category</option>
      {CATEGORY_OPTIONS.map((o) => (
        <option key={o.value} value={o.value}>
          {o.label}
        </option>
      ))}
    </select>
    <ChevronIcon />
  </div>
</label>
```

Update the `row1Cols` grid template to add one more column for Category. The current logic is:

```tsx
const row1Cols = isOrgAdmin
  ? "minmax(0,1.6fr) minmax(0,1fr) minmax(0,1fr) minmax(0,1fr)"
  : "minmax(0,1.6fr) minmax(0,1fr) minmax(0,1fr)";
```

Update to:

```tsx
const row1Cols = isOrgAdmin
  ? "minmax(0,1.6fr) minmax(0,1fr) minmax(0,1fr) minmax(0,1fr) minmax(0,1fr)"
  : "minmax(0,1.6fr) minmax(0,1fr) minmax(0,1fr) minmax(0,1fr)";
```

Pass `category` from `DraftFilters` to `onApply` — it's already part of the `draft` object, so `onApply(draft)` passes it automatically. Verify that the parent widget (`ActionItemManagementWidget.tsx`) forwards `category` in `ListParams` to the API call — check `useActionItems.ts` and add `category` to the params object if missing.

- [ ] **Step 3: Check `useActionItems.ts` wires `category` to the API**

Open `frontend/src/widgets/action-items/useActionItems.ts` and confirm the API call forwards all `ListParams` fields. If `category` is built from `ListParams` via a spread or explicit params object, add it:

```typescript
...(params.category ? { category: params.category } : {}),
```

- [ ] **Step 4: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 5: Build frontend bundle**

```bash
cd frontend && npm run build
```

Expected: build succeeds with no errors.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/widgets/action-items/ActionItemTable.tsx \
        frontend/src/widgets/action-items/ActionItemFilters.tsx \
        frontend/src/widgets/action-items/useActionItems.ts
git commit -m "feat(ui): add category column to action items table and category filter"
```

---

## Task 6: Final verification

- [ ] **Step 1: Run full backend test suite**

```bash
python -m pytest apps/action_items/ apps/integrations/openai/ -v
```

Expected: all tests pass.

- [ ] **Step 2: Run pre-commit checks**

```bash
pre-commit run --all-files
```

Expected: all hooks pass.

- [ ] **Step 3: Smoke-test the migration is reversible**

```bash
python manage.py migrate action_items 0001
python manage.py migrate action_items
```

Expected: both commands succeed cleanly.

- [ ] **Step 4: Final commit if any hook auto-fixes were made**

```bash
git add -p
git commit -m "chore: pre-commit auto-fixes for action item categories"
```

Only if files were modified by hooks. Skip otherwise.
