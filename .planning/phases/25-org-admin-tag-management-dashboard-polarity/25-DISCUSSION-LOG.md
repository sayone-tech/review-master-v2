# Phase 25: Org Admin Tag Management & Dashboard Polarity - Discussion Log

> **Audit trail only.** Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-16
**Phase:** 25-org-admin-tag-management-dashboard-polarity
**Areas discussed:** Rename collision handling, Merge winner & review_count, Merge progress storage, Dashboard mixed-tag rendering

---

## Rename collision handling

| Option | Description | Selected |
|--------|-------------|----------|
| Reject case-insensitive dups; 1–100 chars; Title-Case but relax ≤3-word | reject dup, normalize case, no word cap for admins | ✓ (Claude) |
| Reject dups; enforce full D-05 (Title-Case ≤3 words) | also cap at 3 words | |
| Rename-to-existing AUTO-MERGES | rename becomes a merge shortcut | |

**User's choice:** "you decide the best approach" → reject case-insensitive dups, no silent merge, relax word cap. Rename is O(1) per D-04. → CONTEXT D-03/D-04.

---

## Merge winner & review_count

| Option | Description | Selected |
|--------|-------------|----------|
| Target wins; review_count refreshed via aggregate; keep target polarity_type | admin intent governs; D-03 refresh | ✓ (Claude) |
| Target wins; review_count = naive sum | simpler, drifts from D-03 | |
| Higher-review_count wins (Phase 23 rule) | reuse auto-merge rule | |

**User's choice:** "you decide the best approach" → target wins, aggregate refresh (reuse Phase 23 _refresh_review_counts). → CONTEXT D-06/D-07.

---

## Merge progress storage

| Option | Description | Selected |
|--------|-------------|----------|
| New DB MergeJob model | durable, survives reload+flush, rollback record | ✓ (Claude) |
| Redis job-state key | matches sync-progress, ephemeral | |
| No dedicated store — reuse notifications | simplest, no live bar | |

**User's choice:** "you decide the best approach" → durable `TagMergeJob` DB model, ~2s HTTP poll, no WebSocket. → CONTEXT D-08.

---

## Dashboard mixed-tag rendering

| Option | Description | Selected |
|--------|-------------|----------|
| Extend existing chart: one bar/tag, mixed = stacked pos/neg split | cohesive single chart | ✓ (Claude) |
| Add a separate polarity chart | two tag charts | |
| Mixed as two rows | split into two entries | |

**User's choice:** "you decide the best approach" → extend existing chart, mixed = stacked split; exclude null canonical_tag (TDASH-02). → CONTEXT D-09/D-10.

---

## Claude's Discretion

React widget composition, poll interval, progress granularity, sidebar icon, DRF actions-vs-endpoints, review_count source, chart-lib details. All noted in CONTEXT.md "Claude's Discretion".

## Deferred Ideas

- Merge undo/history beyond TagMergeJob — irreversible by D-05.
- Bulk multi-tag merge/split — single source→target only.
- Superadmin data reset — Phase 26.
- Auto re-promotion of mixed tags — deferred from Phase 24.

## Pre-resolved (carried forward, not asked)

- "Manager" = ORG_ADMIN display label; Staff cannot reach the Tags page.
- Rename is O(1) on OrgCanonicalTag.label (Phase 22 D-04); TMGT-03 "update all ReviewTag rows" superseded.
- Reuse Phase 23 tag-merge queue + per-org lock + _merge_group/_refresh_review_counts.
- HTTP polling (no new WebSocket consumer) per CLAUDE.md §13.2.
