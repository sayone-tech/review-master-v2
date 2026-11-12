# Phase 29 — External API Coverage

No external API integration: Phase 29 is DB models, selectors, and CI only.

The plans reference `openai.AiUsageLog` solely as the target of a nullable `SET_NULL` foreign key on
`CreditTransaction` (D-01). No OpenAI, Google, LangSmith, or SES call is added, mocked, or wrapped in
this phase. The metered OpenAI reply path is Phase 30.
