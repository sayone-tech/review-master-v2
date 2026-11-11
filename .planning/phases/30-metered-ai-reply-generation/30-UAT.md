---
status: testing
phase: 30-metered-ai-reply-generation
source: [30-VERIFICATION.md]
started: 2026-11-11T13:50:36Z
updated: 2026-11-11T13:50:36Z
---

## Current Test

number: 1
name: backend-pg CI job passes the 12 Phase 29/30 pg_concurrency tests on PostgreSQL 16
expected: |
  After pushing feat/v0.9-ai-reply-credits, the GitHub Actions backend-pg job (postgres:16-alpine) shows the pg_concurrency tests passed with 0 skipped; backend-test (SQLite) green.
awaiting: user response

## Tests

### 1. backend-pg CI job passes the 12 Phase 29/30 pg_concurrency tests on PostgreSQL 16
expected: backend-pg on postgres:16-alpine — pg_concurrency all passed, 0 skipped (check with `gh run view`).
result: [pending]

### 2. Live generate against an enabled org (CCON-01)
expected: With an org allocation set per docs/sre/v0.9-credits-rollout.md, generating a reply returns a draft with credits_charged / credits_remaining; the shop balance drops by the review's cost; an insufficient-credit shop gets 402 before any OpenAI call.
result: [pending]

### 3. Proxy timeout covers the documented worst case (go-live checklist)
expected: The production reverse-proxy / app timeout exceeds the reply path's worst-case budget (~190 s, see runbook) so a slow generate isn't cut off mid-settlement.
result: [pending]

## Summary

total: 3
passed: 0
issues: 0
pending: 3
skipped: 0
blocked: 0

## Gaps
