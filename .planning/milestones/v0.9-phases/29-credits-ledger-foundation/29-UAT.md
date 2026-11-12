---
status: testing
phase: 29-credits-ledger-foundation
source: [29-VERIFICATION.md]
started: 2026-11-11T13:14:07Z
updated: 2026-11-11T13:14:07Z
audit_acknowledged:
  milestone: v0.9
  at: 2026-11-12
  gap_snapshot: "testing::scenarios=1"
---

## Current Test

number: 1
name: backend-pg CI job runs the pg_concurrency tests on PostgreSQL 16 (CQA-01)
expected: |
  Push branch feat/v0.9-ai-reply-credits. In GitHub Actions, the backend-pg job (postgres:16-alpine) reports 3 pg_concurrency tests passed, 0 skipped; the SQLite backend-test job stays green.
awaiting: user response

## Tests

### 1. backend-pg CI job runs the pg_concurrency tests on PostgreSQL 16 (CQA-01)
expected: backend-pg on postgres:16-alpine shows 3 passed / 0 skipped for pg_concurrency; backend-test (SQLite) green. Check with `gh run view` after pushing.
result: [pending]

## Summary

total: 1
passed: 0
issues: 0
pending: 1
skipped: 0
blocked: 0

## Gaps
