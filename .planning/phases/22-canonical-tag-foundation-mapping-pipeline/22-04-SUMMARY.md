---
phase: 22-canonical-tag-foundation-mapping-pipeline
plan: 04
status: complete
requirements: [CTAG-03, CTAG-05]
key-files:
  created:
    - apps/reviews/selectors/canonical_tags.py
  modified:
    - apps/integrations/openai/prompts.py
    - apps/integrations/openai/client.py
    - apps/reviews/services/enrichment.py
    - apps/integrations/openai/tests/test_prompts.py
    - apps/reviews/tests/test_enrichment_service.py
---

# 22-04 — Prompt Vocabulary Injection (SUMMARY)

## What was built

Injected the org's capped canonical vocabulary into the single enrichment
prompt and threaded it through all three call signatures (CTAG-03), with an
explicit English-canonical instruction (CTAG-05).

### Task 1 — `get_org_vocabulary` selector
`apps/reviews/selectors/canonical_tags.py` (new). Returns the org's top-N
canonical labels ordered by `-review_count`, sliced to `limit`. Single bounded
query that exploits the `orgcanon_org_count_idx` index from 22-01. Pure
read-only helper — does **not** read settings internally (CLAUDE.md §5); the
caller passes `limit=settings.CANONICAL_VOCAB_INJECT_LIMIT` (D-02).

### Task 2 — prompt injection + version bump
`apps/integrations/openai/prompts.py`:
- `ENRICHMENT_PROMPT_VERSION` 3 → **4**; `REPLY_GENERATION_PROMPT_VERSION`
  untouched (still 1). No bulk re-enrichment triggered (deferred).
- `SYSTEM_PROMPT` extended: each tag now carries a `canonical` label
  (Title Case, ≤3 words, **English**) and a `polarity_type`
  (`always_positive|always_negative|mixed`), set only when proposing a NEW
  canonical label.
- `build_enrichment_messages` gained `canonical_vocab: list[str] | None = None`.
  A new `_build_canonical_vocab_block` helper appends a **map-or-propose**
  instruction: when vocab is present GPT maps to an existing label or proposes
  a new one; when empty, GPT proposes a canonical label for every tag. Prompt
  context stays brand + shop + rating + text only (Phase 12 lock — no address,
  no reviewer name).

### Task 3 — threading
- `apps/integrations/openai/client.py`: `call_openai_enrichment` gained
  `canonical_vocab` and passes it straight to `build_enrichment_messages`
  (the seam at the old line 200).
- `apps/reviews/services/enrichment.py`: `enrich_review` fetches the vocab via
  `get_org_vocabulary(organisation_id=review.organisation_id,
  limit=settings.CANONICAL_VOCAB_INJECT_LIMIT)` — org id is already loaded by
  `select_related("shop__organisation")`, so no extra org query — and passes it
  to `call_openai_enrichment`. The no-comment skip path is untouched, and
  `_persist_success` is left for 22-05.

## Tests
- `test_prompts.py`: added Phase 22 cases — version==4, English canonical +
  `polarity_type` wording, non-empty vocab injected with MAP instruction,
  empty/None vocab → PROPOSE instruction, address-exclusion guard.
- `test_enrichment_service.py`: updated tag fixtures to satisfy the new required
  `canonical`/`polarity_type` fields (cross-plan fix for the 22-03 schema), and
  widened the moderation-test OpenAI mock to accept `canonical_vocab`.

## Verification
- `pytest apps/integrations/openai/tests/test_prompts.py` — green
- `pytest apps/reviews/tests/test_enrichment_service.py apps/integrations/openai` — green (102 tests)
- `mypy` on prompts.py / client.py / canonical_tags.py — clean
- `REPLY_GENERATION_PROMPT_VERSION` still `= 1`

## Notes / deviations
- This was re-implemented inline by the orchestrator after the original
  background worktree executor was denied Bash permission (its edits were lost).
  No scope change from the plan.

## Self-Check: PASSED
