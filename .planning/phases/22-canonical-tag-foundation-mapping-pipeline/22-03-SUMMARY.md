---
phase: 22-canonical-tag-foundation-mapping-pipeline
plan: "03"
subsystem: integrations/openai
tags: [pydantic, structured-outputs, parser, canonical-tags, phase-22]
dependency_graph:
  requires: ["22-01"]
  provides: ["extended Tag schema with canonical + polarity_type"]
  affects: ["22-04", "22-05"]
tech_stack:
  added: []
  patterns:
    - "Pydantic nullable union with NO default for Structured Outputs strict mode"
    - "Mutating field_validator for server-side label normalization (D-05)"
key_files:
  created: []
  modified:
    - apps/integrations/openai/parser.py
    - apps/integrations/openai/tests/fixtures/enrichment_success.json
    - apps/integrations/openai/tests/test_parser.py
decisions:
  - "polarity_type declared as Literal[...] | None with NO default — Structured Outputs strict mode requires every field present, optional fields must be nullable unions (Pitfall 1)"
  - "normalize_canonical uses mutating field_validator (not pattern/constr) — SDK strips schema-level constraints in strict mode (Pitfall 7)"
  - "Existing tests (test_truncates_tags_over_five, etc.) updated to use _make_tag() helper that supplies canonical + polarity_type — fixes breakage caused by adding required canonical field"
metrics:
  duration: ~15m
  completed: "2026-06-10"
  tasks_completed: 2
  files_modified: 3
---

# Phase 22 Plan 03: Tag Schema Extension (canonical + polarity_type) Summary

Extended the structured-output `Tag` Pydantic schema with a required `canonical: str` field (server-side normalized to Title Case ≤3 words via a mutating `field_validator`) and a nullable `polarity_type: Literal["always_positive", "always_negative", "mixed"] | None` with no default, matching the `OrgCanonicalTag.PolarityType` literals from 22-01.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Extend Tag with canonical + polarity_type + normalize_canonical validator | (see commit) | apps/integrations/openai/parser.py, apps/integrations/openai/tests/test_parser.py |
| 2 | Update enrichment_success fixture and extend parser tests | (see commit) | apps/integrations/openai/tests/fixtures/enrichment_success.json, apps/integrations/openai/tests/test_parser.py |

## What Was Built

**`apps/integrations/openai/parser.py`** — `Tag` now carries:
- `canonical: str` — required field, normalized by `normalize_canonical` validator: strips input, keeps first 3 words, Title-Cases each word. No `pattern`/`constr` (SDK strips schema-level constraints in Structured Outputs strict mode).
- `polarity_type: Literal["always_positive", "always_negative", "mixed"] | None` — nullable union with **no default**, matching `OrgCanonicalTag.PolarityType` exactly. Required field presence + nullable union is the Structured Outputs strict-mode contract for optional data.

**`apps/integrations/openai/tests/fixtures/enrichment_success.json`** — Updated so every tag carries `canonical` (string) and `polarity_type` (one concrete literal and one `null`). This single fixture is consumed by both `test_parser.py` and `test_client.py` (via `_load_fixture()` → `EnrichmentResult.model_validate`), keeping both test files green.

**`apps/integrations/openai/tests/test_parser.py`** — Added 9 new Phase 22 test cases covering:
- `test_canonical_normalized_to_title_case` — lowercase input → Title Case
- `test_canonical_truncated_to_three_words` — >3 word input → first 3 words Title-Cased
- `test_canonical_single_word_normalized` — single-word normalization
- `test_polarity_type_none_parses_successfully` — null polarity_type valid (existing-tag mapping)
- `test_polarity_type_always_positive_parses` — literal accepted
- `test_polarity_type_always_negative_parses` — literal accepted
- `test_polarity_type_mixed_parses` — literal accepted
- `test_polarity_type_invalid_value_rejected` — non-allowed value raises ValidationError
- `test_enrichment_result_with_mixed_polarity_types` — full EnrichmentResult with one set/one null

Existing tests updated to use `_make_tag()` helper that supplies `canonical` + `polarity_type`, keeping the full test suite green.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated existing tests that would break with required `canonical` field**
- **Found during:** Task 1 (GREEN phase) — adding `canonical: str` as a required field breaks any test that creates Tag objects without it
- **Issue:** `test_truncates_tags_over_five` was building Tag dicts without `canonical`; this would fail ValidationError on the new required field
- **Fix:** Added `_make_tag()` helper function and updated existing tests to use it; `test_parses_known_good_fixture` stays intact (fixture updated in Task 2)
- **Files modified:** `apps/integrations/openai/tests/test_parser.py`

None beyond the above auto-fix.

## Known Stubs

None — all fields are fully implemented and validated.

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes at trust boundaries.

The threat mitigations from the plan's `<threat_model>` are implemented:
- **T-22-05 (Tampering - canonical label):** `normalize_canonical` field_validator enforces Title Case ≤3 words server-side — never trust-prompt-alone.
- **T-22-06 (Input Validation - polarity_type):** `Literal["always_positive", "always_negative", "mixed"] | None` rejects any value outside the allowed set at parse time.

## Self-Check

### Files Created/Modified

- [x] `apps/integrations/openai/parser.py` — FOUND (Tag.canonical + Tag.polarity_type + normalize_canonical validator)
- [x] `apps/integrations/openai/tests/fixtures/enrichment_success.json` — FOUND (tags carry canonical + polarity_type)
- [x] `apps/integrations/openai/tests/test_parser.py` — FOUND (Phase 22 test cases added)

### Acceptance Criteria Verified

**Task 1:**
- [x] `Tag` has `canonical: str` field
- [x] `Tag` has `polarity_type: Literal["always_positive", "always_negative", "mixed"] | None`
- [x] No `= None` default on `polarity_type`
- [x] `def normalize_canonical` decorated with `@field_validator("canonical")`
- [x] No `pattern=` or `constr` on the canonical field

**Task 2:**
- [x] Fixture tags each contain `canonical` and `polarity_type` keys
- [x] At least one concrete literal polarity_type (`"always_positive"`, `"mixed"`)
- [x] At least one `polarity_type: null`
- [x] `-k canonical` selects at least one passing test

## Self-Check: PASSED
