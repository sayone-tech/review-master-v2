---
status: diagnosed
trigger: "All action item categories are showing as 'other' regardless of review content. Code bug or data/runtime issue?"
created: 2026-05-24T00:00:00Z
updated: 2026-05-24T00:00:00Z
---

## Current Focus

hypothesis: _persist_success in enrichment.py serialises extracted_action_items JSON without the category field, so promote_action_items_from_review always falls back to OTHER
test: confirmed by direct code reading — the list comprehension at line 95-98 of enrichment.py omits "category" from the dict
expecting: root cause confirmed
next_action: DONE — return diagnosis

## Symptoms

expected: Action items should have categories like QUALITY, SERVICE, EXPERIENCE, OPERATIONS derived from GPT output
actual: All action items show category = OTHER regardless of review content
errors: (none — silent data bug)
reproduction: Any AI-enriched action item
started: Always, since category field was introduced on this branch

## Eliminated

(none — root cause found immediately)

## Evidence

- timestamp: 2026-05-24
  checked: apps/integrations/openai/parser.py — ActionItem Pydantic model
  found: Has `category: Literal["quality", "service", "experience", "operations", "other"]`
  implication: GPT correctly returns category. Parser correctly parses it.

- timestamp: 2026-05-24
  checked: apps/integrations/openai/prompts.py — SYSTEM_PROMPT
  found: Prompt explicitly defines all 5 categories and instructs GPT to pick the closest match; "other" is explicitly a last-resort
  implication: GPT is being told to return category. Prompt is correct.

- timestamp: 2026-05-24
  checked: apps/reviews/services/enrichment.py _persist_success lines 95-98
  found: extracted_action_items JSON is serialised as {"title": a.title, "scope": a.scope, "priority": a.priority} — "category" field is MISSING
  implication: Category is available on the Pydantic ActionItem object (a.category) but is never written into the JSON stored in Review.extracted_action_items

- timestamp: 2026-05-24
  checked: apps/action_items/services/lifecycle.py promote_action_items_from_review lines 293-294
  found: category_val = _CATEGORY_MAP.get((entry.get("category") or "").lower(), ActionItem.Category.OTHER)
  implication: Promotion correctly reads "category" from the JSON entry — but entry.get("category") always returns None because the key was never written in _persist_success. The .get() default fires every time → always OTHER.

- timestamp: 2026-05-24
  checked: apps/action_items/services/lifecycle.py _CATEGORY_MAP
  found: Full mapping exists — quality/service/experience/operations/other all mapped correctly
  implication: Promotion logic is correct; the bug is 100% in the serialisation step upstream.

- timestamp: 2026-05-24
  checked: git log — commit 012a60a "fix(enrichment): broaden category glosses + push back on 'other' default"
  found: This commit updated the SYSTEM_PROMPT to push back on 'other'. It did NOT update the _persist_success serialisation.
  implication: The prompt was improved but the serialisation bug was not fixed in the same commit. The prompt improvement has no effect while category is dropped from extracted_action_items.

## Resolution

root_cause: |
  In apps/reviews/services/enrichment.py, _persist_success() serialises the Pydantic ActionItem
  objects into extracted_action_items JSON with a list comprehension that omits the "category" field:

      extracted_action_items=[
          {"title": a.title, "scope": a.scope, "priority": a.priority}
          for a in result.action_items
      ],

  The "category" key is never written. When promote_action_items_from_review() later reads
  entry.get("category"), it always gets None, and the _CATEGORY_MAP.get(..., OTHER) default
  fires every time — producing OTHER for every AI-extracted action item regardless of what
  GPT actually returned.

fix: |
  Add "category": a.category to the dict in _persist_success():

      extracted_action_items=[
          {"title": a.title, "scope": a.scope, "priority": a.priority, "category": a.category}
          for a in result.action_items
      ],

  This is a one-line change. After deploying:
  - New enrichments will store and promote categories correctly.
  - Existing rows will remain OTHER until re-enriched (enrichment_status reset to PENDING
    and Celery worker re-processes them), or manually corrected via the category edit UI
    already shipped in this branch.

verification: N/A — diagnose-only mode
files_changed: [apps/reviews/services/enrichment.py]
