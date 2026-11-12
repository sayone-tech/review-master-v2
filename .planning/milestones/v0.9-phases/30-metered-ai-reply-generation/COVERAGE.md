# Phase 30 — External API Coverage

Phase 30 changes **how** the existing OpenAI integration is called on the AI-reply path. It adds no new
OpenAI API surface, no new external service, and no new dependency.

| OpenAI capability | Disposition | Where | Notes |
|---|---|---|---|
| `chat.completions` (reply drafting) | INTEGRATE (existing) | `apps/integrations/openai/client.py::_do_chat_completions_create` | Reply path only: a `with_options(timeout, max_retries)` copy of the shared client (D-05); `APIConnectionError`/`APITimeoutError` mapped to `OpenAITransientError` (D-15). The enrichment path's shared client is untouched. |
| `moderations` (input + output screening) | INTEGRATE (existing) | `apps/integrations/openai/guardrails.py::_call_moderation_api` | Optional `timeout` / `max_retries` options applied only when the reply path passes them (D-15). Enrichment calls are unchanged. |
| `responses.parse` (review enrichment) | INTEGRATE (existing, unchanged) | `apps/integrations/openai/client.py::_do_responses_parse` | Not modified in this phase. |
| All other OpenAI capabilities (embeddings, images, audio, files, batch, assistants, realtime, fine-tuning, vector stores) | OPT-OUT | — | Not needed: this phase only meters reply drafting. |

LangSmith tracing stays the existing `@traceable` decorator on the reply call; no `wrap_openai` client
wrapper exists in the repo, so the `with_options` copy is traced identically (30-RESEARCH Pattern 5).

Tests never call real OpenAI: they patch `_get_reply_client`, `_call_moderation_api`,
`call_openai_reply_generation`, or `_generate_reply_draft_with_log` (CLAUDE.md §14.10, §16).
