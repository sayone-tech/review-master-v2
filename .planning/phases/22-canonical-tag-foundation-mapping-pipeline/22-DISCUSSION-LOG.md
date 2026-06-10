# Phase 22: Canonical Tag Foundation & Mapping Pipeline - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-10
**Phase:** 22-canonical-tag-foundation-mapping-pipeline
**Areas discussed:** Polarity at creation, Vocabulary injection cap, review_count on re-enrichment, Canonical label storage & format

---

## Polarity at creation (Phase 22 ↔ 24 boundary)

| Option | Description | Selected |
|--------|-------------|----------|
| Capture in Phase 22 | GPT returns polarity_type for new canonical tags now; store on OrgCanonicalTag. P24 adds only reclassification + visibility. | ✓ |
| Default now, GPT-assign in 24 | Store placeholder polarity_type in P22; add GPT assignment to prompt in P24 (touches prompt/parser twice). | |

**User's choice:** Capture in Phase 22 (recommended)
**Notes:** Field already exists in P22 success criteria and CTAG-04 requires it; keeps the prompt/parser change in one place.

---

## Vocabulary injection cap

| Option | Description | Selected |
|--------|-------------|----------|
| Cap to top-N by usage | Inject N most-used canonical tags (configurable, ~200 default); safety valve against unbounded prompt growth. | ✓ |
| Inject all canonical tags | Full list every time; simplest, matches spec literally. | |

**User's choice:** Cap to top-N by usage (recommended)
**Notes:** N is a configurable setting; rarely-used tags still match via the new-proposal path.

---

## review_count on re-enrichment

| Option | Description | Selected |
|--------|-------------|----------|
| Derive on read | Aggregate over ReviewTag→canonical_tag on the bounded/cached tag-list query; no counter drift. | ✓ |
| Stored counter, adjusted on re-enrich | Exact stored counter; re-enrichment decrements old + increments new. | |
| Stored counter, increment-only | Simplest; tolerate minor drift on rare re-enrichment. | |

**User's choice:** Derive on read (recommended)
**Notes:** Sidesteps double-counting from the delete-then-bulk_create re-enrichment path. Optional denormalized cache refreshed by weekly job/merge, never inline.

---

## Canonical label storage & format

| Option | Description | Selected |
|--------|-------------|----------|
| FK only + server-enforced format | canonical_tag FK on ReviewTag; label only on OrgCanonicalTag (rename O(1)); Title Case/≤3 words via validator. | ✓ |
| Denormalize label onto ReviewTag | Store label string on each ReviewTag (matches spec literal text); rename updates all rows; risks drift. | |

**User's choice:** FK only + server-enforced format (recommended)
**Notes:** Spec's "update all ReviewTag rows on rename" was an artifact of the old JSONB model. FK-only makes Phase 25 rename O(1). Title Case/≤3 words enforced via a validator mirroring max_five_tags.

---

## Claude's Discretion

- New-canonical creation race → `get_or_create` + `IntegrityError` catch on the `(organisation, label)` unique constraint; no new Redis lock.
- Rate limit (QUEUE-02) → global Celery `rate_limit`, env-configurable, default ~500/min.
- Bump `ENRICHMENT_PROMPT_VERSION`; no bulk re-enrichment.
- Migration adds model + nullable FK, no backfill.
- Canonical mapping runs inside the existing `_persist_success` `transaction.atomic()`.
- Exact module placement of `OrgCanonicalTag` (keep direct `organisation` FK regardless).

## Deferred Ideas

- Weekly polarity auto-reclassification + visibility → Phase 24.
- Four-step sync, seed/bulk, queue split → Phase 23.
- Tags page / rename / merge / dashboard polarity → Phase 25.
- Superadmin data reset → Phase 26.
- Bulk re-enrichment on prompt-version bump → out of scope (milestone-wide).
