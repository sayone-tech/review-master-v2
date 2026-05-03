# GSD Debug Knowledge Base

Resolved debug sessions. Used by `gsd-debugger` to surface known-pattern hypotheses at the start of new investigations.

---

## langsmith-cost-not-shown — LangSmith Cost column blank/$0.00 despite traces shipping
- **Date:** 2026-05-03
- **Error patterns:** langsmith, cost, $0.00, blank, total_tokens, usage_metadata, traceable, responses.parse, ls_model_name, gpt-4o-mini, enrichment, OpenAI Responses API
- **Root cause:** The `@traceable`-decorated function did not attach `usage_metadata` to the LangSmith run. LangSmith's `_extract_usage` (run_helpers.py) reads `usage_metadata` from `run_tree.metadata` or outputs; neither was set. Function returned a tuple `(response, trace_id)`, so LangSmith's auto-extraction couldn't parse it. Without usage tokens on the run, LangSmith's pricing engine had nothing to multiply, so Cost rendered as $0.00. Compounding factor: `ls_model_name` (the metadata key LangSmith uses for the pricing-table lookup) was also missing.
- **Fix:** In `_call_openai_with_tracing`, after the OpenAI Responses API call returns, extract `response.usage.input_tokens/output_tokens/total_tokens` (which match LangSmith's UsageMetadata schema 1:1) and set `run_tree.metadata['usage_metadata']` plus `run_tree.metadata['ls_model_name'] = model`. Cached tokens go to `input_token_details.cache_read`. All inside the existing best-effort try/except so metadata failures cannot block the OpenAI call.
- **Files changed:** apps/integrations/openai/client.py
---
