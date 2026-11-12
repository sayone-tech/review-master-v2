---
status: testing
phase: 32-superadmin-credit-controls
source: [32-VERIFICATION.md]
started: 2026-11-11T16:11:43Z
updated: 2026-11-11T16:11:43Z
audit_acknowledged:
  milestone: v0.9
  at: 2026-11-12
  gap_snapshot: "testing::scenarios=4"
---

## Current Test

number: 1
name: backend-pg CI job passes all pg_concurrency tests on PostgreSQL 16
expected: |
  After pushing feat/v0.9-ai-reply-credits, the GitHub Actions backend-pg job (postgres:16-alpine) shows the pg_concurrency tests (Phases 29–32) passed with 0 skipped; backend-test (SQLite) green.
awaiting: user response

## Tests

### 1. backend-pg CI job passes all pg_concurrency tests on PostgreSQL 16
expected: backend-pg on postgres:16-alpine — pg_concurrency all passed, 0 skipped (`gh run view`).
result: [pending]

### 2. Manage Credits walk-through as Superadmin
expected: Org row → Manage Credits shows active shops (search, paging), Add bonus → live preview → Allocate shows toast and returns to the refreshed list; Edit Organisation hint shows "immediate" for 0→N and the next-month copy otherwise; a forced month rollover returns the amber 409 banner with typed values kept; Org Admin/Staff never see the action.
result: [pending]

### 3. 360px: bonus balance block collapses to two columns without overflow
expected: At 360px width the 4-column balance block in the bonus form becomes 2 columns with no horizontal overflow.
result: [pending]

### 4. 360px: long org/shop names wrap in the modal subtitle
expected: Long names wrap and never overlap the close button at 360px.
result: [pending]

## Summary

total: 4
passed: 0
issues: 0
pending: 4
skipped: 0
blocked: 0

## Gaps
