# Action Item Categories — Design Spec

**Date:** 2026-05-15
**Status:** Approved

---

## Problem

Action items extracted from reviews have no category. Org admins and staff cannot quickly see what area an item relates to (food quality? staff behaviour? wait time?) and cannot filter by area. A customer operating a restaurant chain requested categorisation.

---

## Decisions

- **5 fixed categories:** Quality, Service, Experience, Operations, Other
- **Sector-agnostic:** "Operations" chosen over "Delivery" so the categories apply equally to restaurants, retail, hotels, gyms, clinics, and other sectors.
- **AI-assigned only:** All action items are AI-extracted; there is no manual creation UI. Category is always set by OpenAI — no user input required.
- **"Other" as catch-all:** Items that don't fit the four primary categories (e.g. "Update Google Business profile photos") land in Other rather than being force-fit.
- **Single prompt, zero extra calls:** Category classification is added to the existing enrichment prompt (~40 extra tokens on the system prompt, cached after first call). This follows the "one call per review" rule (CLAUDE.md §14.2).

---

## Category Definitions

| Value | Label | Covers |
|---|---|---|
| `QUALITY` | Quality | Product, food, ingredient, or service quality standards |
| `SERVICE` | Service | Staff behaviour, responsiveness, attitude, communication |
| `EXPERIENCE` | Experience | Ambience, atmosphere, overall feel of the visit |
| `OPERATIONS` | Operations | Wait times, delivery, logistics, processes, efficiency |
| `OTHER` | Other | Anything that doesn't fit the four above |

---

## Section 1 — Data Layer

**File:** `apps/action_items/models.py`

Add a `Category` inner class to `ActionItem`:

```python
class Category(models.TextChoices):
    QUALITY     = "QUALITY",     "Quality"
    SERVICE     = "SERVICE",     "Service"
    EXPERIENCE  = "EXPERIENCE",  "Experience"
    OPERATIONS  = "OPERATIONS",  "Operations"
    OTHER       = "OTHER",       "Other"
```

Add the field:

```python
category = models.CharField(
    max_length=15,
    choices=Category.choices,
    default=Category.OTHER,
    db_index=True,
)
```

Add a composite index:

```python
models.Index(fields=["organisation", "category"], name="ai_org_category_idx"),
```

**Migration:** One migration. Reversible. Existing rows default to `OTHER`.

**Existing data:** All pre-existing action items get `OTHER`. They will be properly categorised only if re-enrichment is triggered in a future phase.

---

## Section 2 — AI Layer

### `apps/integrations/openai/parser.py`

Add `category` to the `ActionItem` Pydantic schema:

```python
class ActionItem(BaseModel):
    title: str
    scope: Literal["shop", "brand"]
    priority: Literal["high", "medium", "low"]
    category: Literal["quality", "service", "experience", "operations", "other"]
```

If GPT returns an unrecognised value, Pydantic validation fails and the existing retry-once logic handles it (ENRCH-04). No new error handling needed.

### `apps/integrations/openai/prompts.py`

Bump `ENRICHMENT_PROMPT_VERSION` from `1` to `2`.

Add one sentence to `SYSTEM_PROMPT` inside the `action_items` instruction:

```
Each item also has a 'category': classify as 'quality' (product/food standard),
'service' (staff behaviour, responsiveness), 'experience' (ambience, atmosphere,
overall feel), 'operations' (wait time, delivery, logistics, processes), or
'other' when none fit.
```

Token overhead: ~40 tokens added to system prompt. System prompt is cached after the first call so marginal cost per review is near zero.

### `apps/action_items/lifecycle.py`

Add a `_CATEGORY_MAP` dict (same pattern as existing `_PRIORITY_MAP` and `_SCOPE_MAP`):

```python
_CATEGORY_MAP = {
    "quality":     ActionItem.Category.QUALITY,
    "service":     ActionItem.Category.SERVICE,
    "experience":  ActionItem.Category.EXPERIENCE,
    "operations":  ActionItem.Category.OPERATIONS,
    "other":       ActionItem.Category.OTHER,
}
```

In `promote_action_items_from_review`, resolve category with fallback to `OTHER`:

```python
category_val = _CATEGORY_MAP.get(
    (entry.get("category") or "").lower(), ActionItem.Category.OTHER
)
```

Pass `category=category_val` when constructing each `ActionItem`.

---

## Section 3 — API Layer

### `apps/action_items/serializers.py`

Add two read fields to `ActionItemSerializer`:

```python
category = serializers.CharField(source="get_category_display", read_only=True)
category_value = serializers.CharField(source="category", read_only=True)
```

`category` returns the human label (`"Quality"`); `category_value` returns the stored value (`"QUALITY"`) for filter state.

### `apps/action_items/filters.py`

Add a `MultipleChoiceFilter` to `ActionItemFilter`:

```python
category = django_filters.MultipleChoiceFilter(choices=ActionItem.Category.choices)
```

Supports `?category=QUALITY&category=SERVICE` for multi-select. Consistent with existing `status`, `scope`, and `priority` filters. No new URL or viewset changes needed.

---

## Section 4 — UI Layer

### Badge on each item

Each action item card/row gets a pill badge showing the category label, sitting alongside the existing Priority and Scope badges.

| Category | Badge colour |
|---|---|
| Quality | Blue |
| Service | Purple |
| Experience | Teal |
| Operations | Orange |
| Other | Grey |

### Filter in the list header

A "Category" dropdown/multi-select is added to the filter bar in `action_item_list.html`, consistent with the existing Status, Priority, and Scope filters. Selecting a value appends `?category=VALUE` to the API request — no new JS logic, same pattern as existing filters.

---

## Files Touched

| File | Change |
|---|---|
| `apps/action_items/models.py` | Add `Category` choices + field + index |
| `apps/action_items/migrations/000X_...py` | New migration |
| `apps/integrations/openai/parser.py` | Add `category` to `ActionItem` Pydantic schema |
| `apps/integrations/openai/prompts.py` | Bump prompt version, add category instruction |
| `apps/action_items/services/lifecycle.py` | Add `_CATEGORY_MAP`, pass category in `promote_action_items_from_review` |
| `apps/action_items/serializers.py` | Add `category` + `category_value` read fields |
| `apps/action_items/filters.py` | Add `MultipleChoiceFilter` for category |
| `apps/action_items/templates/action_items/action_item_list.html` | Add category badge + filter control |

---

## Out of Scope

- Re-enriching existing action items to assign correct categories (deferred to a future phase).
- Admin UI for editing category on an existing item (all items are AI-sourced; category follows enrichment).
- Adding category to the Reports page aggregate table (separate feature request).
