---
status: resolved
trigger: "OpenAI traces appear in LangSmith but Cost column is blank/$0.00"
created: 2026-05-03T00:00:00Z
updated: 2026-05-03T00:00:00Z
---

## Current Focus

hypothesis: The @traceable wrapper traces our `_call_openai_with_tracing` function as run_type="llm", but LangSmith does not auto-extract token usage from the OpenAI Responses API response (`client.responses.parse`). LangSmith's auto-extraction is built around the Chat Completions API shape (response.usage with prompt_tokens/completion_tokens). For Responses API or custom returns, you must explicitly attach usage_metadata to the run tree. Since we already use `get_current_run_tree()` in this function, the fix is to also call `run_tree.add_outputs(...)` or set `run_tree.outputs` with a usage_metadata dict so LangSmith's pricing engine can compute Cost.
test: Read the code, confirm the flow, then add usage_metadata attachment.
expecting: After attaching usage_metadata={"input_tokens": ..., "output_tokens": ..., "total_tokens": ...} on the run tree, LangSmith will populate Total Tokens AND Cost (via its built-in gpt-4o-mini pricing).
next_action: Modify _call_openai_with_tracing to attach usage_metadata after extracting it from response.usage.

## Symptoms

expected: Each enrichment run in LangSmith shows non-zero Total Tokens and Cost computed from gpt-4o-mini pricing.
actual: Runs appear with input/output, but Cost column is blank/$0.00.
errors: None — server-side AiUsageLog is correct, traces ship to LangSmith successfully.
reproduction: Run `enrich_review(review_id=<id>)` on a comment-bearing review, then check the run in LangSmith UI.
started: Phase 12 launch — Cost has never rendered.

## Eliminated

(none yet)

## Evidence

- timestamp: 2026-05-03T00:00:00Z
  checked: apps/integrations/openai/client.py
  found: The OpenAI client uses `client.responses.parse(...)` (Responses API), NOT chat.completions.create. The function is decorated with `@traceable(run_type="llm", name="enrich_review")` but returns a tuple `(response, trace_id)` — NOT the raw OpenAI response. LangSmith's auto-extraction would key off the return value's shape; a tuple means LangSmith cannot find a `.usage` attribute on the run output. The function gets `run_tree = get_current_run_tree()` and updates `run_tree.metadata` with entity IDs, but NEVER sets usage_metadata on the run.
  implication: This is the smoking gun. LangSmith's cost computation requires usage_metadata on the run; the run output is a tuple of (response, trace_id) so auto-extraction fails. We must explicitly attach usage_metadata.

- timestamp: 2026-05-03T00:00:00Z
  checked: apps/integrations/openai/tracing.py
  found: Just sets env vars (LANGSMITH_TRACING, LANGSMITH_API_KEY, LANGSMITH_PROJECT, LANGSMITH_ENDPOINT). No wrap_openai. LangSmith init looks correct.
  implication: Tracing is enabled but no SDK-level wrapping is in play. We rely entirely on @traceable.

- timestamp: 2026-05-03T00:00:00Z
  checked: apps/integrations/openai/parser.py
  found: Pure Pydantic schemas. Doesn't touch the OpenAI response object. Not part of the LangSmith path.
  implication: Eliminated as a culprit. The response.usage field is intact when we extract from it.

- timestamp: 2026-05-03T00:00:00Z
  checked: pyproject.toml
  found: langsmith==0.8.0, openai==2.33.0. Modern langsmith supports `run_tree.add_outputs()` and metadata "usage_metadata" key for cost computation. Modern openai SDK Responses API has `response.usage.input_tokens / output_tokens / total_tokens` (NOT prompt_tokens/completion_tokens — that's Chat Completions).
  implication: Need to map Responses API field names to LangSmith's expected `usage_metadata` keys: `{"input_tokens": ..., "output_tokens": ..., "total_tokens": ...}`. LangSmith 0.8.0 accepts these directly.

## Resolution

root_cause: The `@traceable`-decorated function `_call_openai_with_tracing` does not attach usage_metadata to the LangSmith run. LangSmith's `_extract_usage` (langsmith/run_helpers.py:319) reads `usage_metadata` from either run_tree.metadata or outputs; neither is set. The function returns `(response, trace_id)` — a tuple — so even if LangSmith tried to auto-extract from outputs, it would fail because the tuple isn't a recognised LLM response shape. Without usage_metadata, LangSmith's Cost engine has zero tokens to multiply against gpt-4o-mini pricing, hence $0.00. Compounding factor: we also never set `ls_model_name`, the metadata key LangSmith uses for the pricing-table lookup (see langsmith.wrappers._openai:135).
fix: In _call_openai_with_tracing, after the OpenAI call returns, extract response.usage (Responses API: input_tokens/output_tokens/total_tokens — matches LangSmith UsageMetadata schema 1:1) and attach to run_tree.metadata as `usage_metadata`. Also set `ls_model_name = model` so LangSmith's pricing lookup resolves the snapshot ID. Cached tokens (from input_tokens_details) are mapped to `input_token_details.cache_read` per LangSmith schema. Best-effort try/except preserved — metadata failure cannot block the OpenAI call.
verification: Reset Review id=109 to PENDING, ran enrich_review(review_id=109). Run trace_id=019ded00-bf56-7cf3-8c3d-b84f7f9ca714. LangSmith API GET /api/v1/runs/019ded00-bf56-7cf3-8c3d-b84f7f9ca714 returned: total_tokens=515, prompt_tokens=450, completion_tokens=65, total_cost=$0.0001065, prompt_cost=$0.0000675, completion_cost=$0.000039, metadata.usage_metadata={'input_tokens':450,'output_tokens':65,'total_tokens':515}, metadata.ls_model_name=gpt-4o-mini-2024-07-18. LangSmith's computed total_cost ($0.0001065) matches AiUsageLog.estimated_cost_usd ($0.00010600) to the sub-cent — pricing alignment confirmed. Existing pytest suite (test_client.py + test_tracing.py = 11 tests) all pass.
files_changed: ["apps/integrations/openai/client.py"]
