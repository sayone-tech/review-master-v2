---
status: testing
phase: 31-monthly-renewal-reservation-reaper
source: [31-VERIFICATION.md]
started: 2026-11-11T14:46:19Z
updated: 2026-11-11T14:46:19Z
audit_acknowledged:
  milestone: v0.9
  at: 2026-11-12
  gap_snapshot: "testing::scenarios=3"
---

## Current Test

number: 1
name: backend-pg CI job passes all pg_concurrency tests on PostgreSQL 16
expected: |
  After pushing feat/v0.9-ai-reply-credits, the GitHub Actions backend-pg job (postgres:16-alpine) shows the pg_concurrency tests (Phases 29–31) passed with 0 skipped; backend-test (SQLite) green.
awaiting: user response

## Tests

### 1. backend-pg CI job passes all pg_concurrency tests on PostgreSQL 16
expected: backend-pg on postgres:16-alpine — pg_concurrency all passed, 0 skipped (`gh run view`).
result: [pending]

### 2. Beat picks up both seeded schedules after deploy
expected: After migrate + Beat restart, django-celery-beat shows credits_lapse_expired_balances (daily 00:05 UTC) and credits_reap_stale_reservations (every 10 min) enabled, and a reaper run appears in worker logs within 10 minutes.
result: [pending]

### 3. 00:30 UTC lapse alert configured by the deployment owner
expected: An alert fires if the lapse sweep has not completed by 00:30 UTC on the 1st (handoff in docs/sre/v0.9-credits-rollout.md).
result: [pending]

## Summary

total: 3
passed: 0
issues: 0
pending: 3
skipped: 0
blocked: 0

## Gaps
