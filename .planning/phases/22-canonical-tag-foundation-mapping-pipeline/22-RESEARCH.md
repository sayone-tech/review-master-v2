# Phase 22: Canonical Tag Foundation & Mapping Pipeline - Research

**Researched:** 2026-06-10
**Domain:** Django 6 + DRF + Celery + OpenAI Structured Outputs (Responses API) — extending an existing single-call enrichment pipeline with a per-org self-organising canonical tag vocabulary
**Confidence:** HIGH (codebase verified by direct file reads; external claims verified against official OpenAI + Celery docs)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Phase 22 **captures and stores GPT's `polarity_type`** for each newly proposed canonical tag. Prompt + Pydantic parser change to return `polarity_type` (`always_positive` / `always_negative` / `mixed`) lands here; `OrgCanonicalTag.polarity_type` is populated at creation. Phase 24 adds ONLY the weekly DB-only reclassification job + visibility — it does NOT touch prompt/parser again.
- **D-02:** Inject the org's canonical vocabulary into the prompt **capped to the top-N by `review_count`**, N a configurable Django setting, generous default (~200). Tags outside the cap can still be re-proposed/matched via the new-canonical path.
- **D-03:** `review_count` is **derived on read** — aggregate over `ReviewTag → canonical_tag` on the (bounded, cached) tag-list query — NOT a hot counter. A denormalized `review_count` column MAY exist as a cache, refreshed by the weekly job / merge task only, never incremented inline. **No re-enrichment bookkeeping in the enrichment hot path.**
- **D-04:** Store the **FK only** — `ReviewTag.canonical_tag` → `OrgCanonicalTag`. The canonical label lives ONLY on `OrgCanonicalTag`, never denormalized onto `ReviewTag`. Makes Phase 25 rename O(1).
- **D-05:** Enforce canonical label format — **Title Case, ≤3 words** — **server-side** via a normalizer/validator (mirroring `EnrichmentResult.max_five_tags`), not by trusting the prompt alone. Raw `ReviewTag.label` stays as-is (`.title()`-cased per Phase 17); canonical label is a separate normalized value.

### Claude's Discretion
- **New-canonical creation race:** use `get_or_create` (or equivalent) with an `IntegrityError` catch against the `(organisation, label)` unique constraint. No new Redis lock beyond the existing per-review enrichment lock.
- **Rate limit (QUEUE-02):** global Celery `rate_limit` on the enrichment task, value from an env-configurable setting, default ~500/min; applies per task-type across all workers. **(See Common Pitfall 6 — this assumption is technically WRONG; `rate_limit` is per-worker. The planner must reconcile.)**
- **Prompt version:** bump `ENRICHMENT_PROMPT_VERSION` (currently 3) when canonical instructions are added; do NOT trigger bulk re-enrichment.
- **Migration:** add `OrgCanonicalTag` + nullable `canonical_tag` FK in one migration; **no backfill** (criterion 5).
- **Where the mapping runs:** inside the existing `_persist_success` `transaction.atomic()` in `apps/reviews/services/enrichment.py`, alongside the `ReviewTag` delete-then-`bulk_create`, resolving org via `review.organisation_id`.
- Exact placement of the canonical model (`apps/reviews` vs adjacent) — direct `organisation` FK regardless.

### Deferred Ideas (OUT OF SCOPE)
- Weekly polarity auto-reclassification + visibility — Phase 24 (POL-01..03). P22 only captures the initial `polarity_type`.
- Four-step initial sync, seed/bulk phases, queue split (`ai-enrichment-high`/`-low`, `tag-merge`) — Phase 23 (SEED, DSYNC, QUEUE-01).
- Org Admin Tags page, inline rename, merge, dashboard polarity split — Phase 25 (TMGT, TDASH). D-04 makes rename there O(1).
- Superadmin data reset + re-sync — Phase 26 (RESET).
- Bulk re-enrichment to a new prompt version — out of scope across the milestone.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CTAG-01 | Per-org `OrgCanonicalTag` vocabulary (label Title Case ≤3 words, `polarity_type`, `review_count`, timestamps; unique `(organisation, label)`) | OrgCanonicalTag model shape (§Architecture Pattern 1); `review_count` is derived-on-read per D-03 — see Pitfall 5 reconciliation |
| CTAG-02 | Each `ReviewTag` carries a nullable `canonical_tag` FK populated once mapped | Nullable FK migration with no backfill (§Architecture Pattern 2, §Runtime State Inventory) |
| CTAG-03 | Single enrichment GPT call has the org's existing canonical vocabulary injected into its prompt | Vocabulary injection into `build_enrichment_messages` (§Architecture Pattern 4); top-N cap per D-02 |
| CTAG-04 | GPT maps each tag to an existing canonical label OR proposes a new one with `polarity_type`, in one call | Pydantic `Tag` schema extension (§Architecture Pattern 3); Structured Outputs nullable-field rules (§Common Pitfall 1) |
| CTAG-05 | All tags (raw + canonical) + action items emitted in English | English-only rule already in `SYSTEM_PROMPT`; extend to canonical labels (§Architecture Pattern 4) |
| CTAG-06 | Post-enrichment lookup/insert inside the existing enrichment `transaction.atomic()`; matched→FK, new→insert row | Fold into `_persist_success` (§Architecture Pattern 5); get_or_create + IntegrityError (§Common Pitfall 4) |
| CTAG-07 | Exactly one `AiUsageLog` row per call (canonicalisation adds no separate call) | Mapping happens in-call + post-enrichment DB only; ZERO extra OpenAI calls (§Don't Hand-Roll, §Common Pitfall 2) |
| CTAG-08 | Pre-canonicalisation reviews remain valid with null canonical mapping | Nullable FK + no backfill; existing queries unaffected (§Common Pitfall 8) |
| QUEUE-02 | Enrichment task enforces a global, configurable Celery rate limit (~500/min) across all workers | **`rate_limit` is PER-WORKER, not global** (§Common Pitfall 6) — planner must reconcile the success criterion with reality |
</phase_requirements>

## Summary

This phase extends an already-working, well-factored enrichment pipeline. There is **no greenfield domain research** to do — the architecture is fixed by CONTEXT.md and the codebase. The work is precise surgical extension at five existing seams:

1. **`parser.py`** — add `canonical: str` and `polarity_type` to the `Tag` Pydantic model, add a Title-Case/≤3-word normalizer mirroring `max_five_tags`.
2. **`prompts.py`** — inject the org's top-N canonical vocabulary into `build_enrichment_messages`, add the map-or-propose + polarity-on-new instruction, bump `ENRICHMENT_PROMPT_VERSION`.
3. **`apps/reviews/models.py`** — new `OrgCanonicalTag` model (direct `organisation` FK, unique `(organisation, label)`) + nullable `canonical_tag` FK on `ReviewTag`; one migration, no backfill.
4. **`enrichment.py` `_persist_success`** — fold canonical lookup/insert + FK population into the existing `transaction.atomic()` delete-then-`bulk_create` block.
5. **`tasks.py` / `settings/base.py`** — add an env-configurable `rate_limit` to `enrich_review_task` (QUEUE-02).

**The two highest-risk landmines, both VERIFIED externally:**
- **OpenAI Structured Outputs requires every field to be `required`.** Optional fields must be modeled as a nullable union (`X | None`), and the SDK strips Python defaults / extra JSON-schema constraints. Adding `polarity_type` naively (with a default, or as a constrained type) will silently break `responses.parse` strict-mode schema generation. [CITED: developers.openai.com/api/docs/guides/structured-outputs]
- **Celery `rate_limit` is per-worker-instance, NOT global.** The OpenAI docs and Celery docs are explicit. QUEUE-02's "global ~500/min across all workers" cannot be achieved by the task `rate_limit` option alone. [CITED: docs.celeryq.dev/en/stable/userguide/tasks.html]

**Primary recommendation:** Implement the parser/prompt/model/service changes as direct extensions of the existing patterns (the codebase already shows the exact idioms to mirror). For QUEUE-02, set the env-configurable `rate_limit` but **document explicitly that it is per-worker** and compute the per-worker value as `total_target / worker_count` — OR defer true-global rate limiting to the Phase 23 queue split. Flag this to the user as an ASSUMED-correction needing confirmation.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Map raw tag → canonical label | API / Backend (GPT call, in-call) | — | Happens inside the single existing OpenAI call; no extra tier |
| Persist `OrgCanonicalTag` + `ReviewTag.canonical_tag` FK | Database / Backend service | — | `_persist_success` transaction; pure DB write, org-scoped |
| Inject org vocabulary into prompt | API / Backend (selector → prompt builder) | Database (indexed SELECT) | Read top-N canonical tags per org before the call |
| `review_count` (derive-on-read) | Database (aggregate query) | — | Computed on the future tag-list query (Phase 25), not stored hot |
| Global enrichment throttle (QUEUE-02) | Celery worker config / Infra | — | Rate limit is a worker concern; per-worker only (see Pitfall 6) |
| Label format enforcement (Title Case ≤3 words) | API / Backend (Pydantic validator) | — | Server-side, never prompt-only (D-05) |

## Standard Stack

No new third-party packages are required. Phase 22 uses libraries already pinned and in use.

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `openai` | 2.33.0 | `client.responses.parse(text_format=EnrichmentResult)` structured outputs | Already the enrichment client (`client.py`); pinned in `pyproject.toml` [VERIFIED: pyproject.toml] |
| `pydantic` | 2.13.3 | `EnrichmentResult` / `Tag` schema + `field_validator` | Already the structured-output contract (`parser.py`) [VERIFIED: pyproject.toml] |
| `celery` | 5.x | `enrich_review_task` + `rate_limit` | Already the task runner [VERIFIED: pyproject.toml has celery] |
| `Django` | 6.0.x | `OrgCanonicalTag` model, migration, FK | Project ORM [CITED: CLAUDE.md §2] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `factory-boy` | — | `OrgCanonicalTagFactory` for tests | Add one factory per new model (CLAUDE.md §16) |
| `pytest-django` | — | Test runner | Existing; `CELERY_TASK_ALWAYS_EAGER=True` already set in test settings |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| FK-only on `ReviewTag` (D-04) | Denormalized `canonical_label` on `ReviewTag` | Rejected by D-04 — fans rename across all rows; FK join keeps rename O(1) |
| `get_or_create` + IntegrityError | Redis lock per `(org,label)` | Discretion item — no new lock; the DB unique constraint + IntegrityError catch is the standard Django race-safe idiom |
| Per-worker `rate_limit` | Distributed token bucket in Redis (existing `rate:openai:org:*` pattern, CLAUDE.md §7.7) | True-global throttle; more work — likely Phase 23. See Pitfall 6 |

**Installation:** None. (No new packages.)

## Package Legitimacy Audit

> Not applicable — Phase 22 installs **no new external packages**. All libraries (`openai`, `pydantic`, `celery`, `Django`, `factory-boy`) are already pinned in `pyproject.toml` and in active use. slopcheck gate skipped (no install step).

## Architecture Patterns

### System Architecture Diagram

```
enrich_review_task (Celery, ai-enrichment queue, NEW rate_limit)
        │
        ▼
enrich_review(review_id)  ── Redis lock lock:enrich:review:{id}  (Layer 1)
        │
        ├─ select_for_update Review (Layer 2/3: PENDING→IN_PROGRESS)
        │     review.select_related("shop__organisation")  ← org id already loaded
        │
        ├─ moderate_input (unchanged)
        │
        ├─ [NEW] load org canonical vocab (top-N by review_count, capped)  ──► SELECT OrgCanonicalTag
        │                                                                        WHERE org=? ORDER BY review_count DESC LIMIT N
        │
        ├─ build_enrichment_messages(review, vocab)  [NEW: inject vocab + map-or-propose instruction]
        │
        ├─ call_openai_enrichment ──► OpenAI responses.parse(text_format=EnrichmentResult)
        │        returns Tag{label, polarity, canonical, polarity_type|null}   ← ONE call, no extra
        │
        ▼
_persist_success  ── transaction.atomic()  (CTAG-06: all-or-nothing)
        ├─ Review.update(status=SUCCESS, sentiment, ...)
        ├─ ReviewTag.filter(review).delete()
        ├─ [NEW] for each tag: normalize canonical label (D-05 validator)
        │         get_or_create OrgCanonicalTag(org, label) → catch IntegrityError  (CTAG-01)
        ├─ ReviewTag.bulk_create([... canonical_tag=fk ...])   (CTAG-02)   ← FK populated here
        └─ AiUsageLog.create(...)  ← EXACTLY ONE row  (CTAG-07)
        │
        ▼ (after commit)
   _emit_enrichment_progress + action item promotion (unchanged)
```

### Recommended Project Structure
No new files strictly required; all changes land in existing modules. Optionally a selector for vocab fetch:
```
apps/reviews/
├── models.py            # + OrgCanonicalTag, + ReviewTag.canonical_tag FK
├── selectors/
│   └── canonical_tags.py   # NEW (optional): get_org_vocabulary(org_id, limit) + derive-on-read review_count aggregate
├── services/
│   └── enrichment.py    # _persist_success: fold canonical lookup/insert
└── tests/
    ├── factories.py     # + OrgCanonicalTagFactory
    └── test_enrichment_service.py  # + canonical mapping tests
apps/integrations/openai/
├── parser.py            # Tag gains canonical + polarity_type; canonical-label normalizer
├── prompts.py           # build_enrichment_messages injects vocab; ENRICHMENT_PROMPT_VERSION → 4
config/settings/base.py  # + ENRICHMENT_RATE_LIMIT, + VOCAB cap setting
```

### Pattern 1: `OrgCanonicalTag` model (CTAG-01, D-04)
**What:** Per-org canonical vocabulary table; direct `organisation` FK for tenant scoping (CLAUDE.md §9).
**When to use:** New model in `apps/reviews/models.py`.
```python
# Source: mirrors ReviewTag (apps/reviews/models.py:128) + CLAUDE.md §9 tenant-scoping rule
class OrgCanonicalTag(TimeStampedModel):   # TimeStampedModel gives created_at/updated_at (CTAG-01 timestamps)
    class PolarityType(models.TextChoices):
        ALWAYS_POSITIVE = "always_positive", "Always Positive"
        ALWAYS_NEGATIVE = "always_negative", "Always Negative"
        MIXED = "mixed", "Mixed"

    organisation = models.ForeignKey(
        "organisations.Organisation", on_delete=models.CASCADE,
        related_name="canonical_tags", db_index=True,
    )
    label = models.CharField(max_length=100)            # Title Case, <=3 words (D-05 validator on write)
    polarity_type = models.CharField(max_length=20, choices=PolarityType.choices)
    # D-03: review_count is a DENORMALIZED CACHE only, refreshed by Phase 24 weekly job / Phase 25 merge.
    # NEVER incremented in the enrichment hot path. Default 0; authoritative value is derived-on-read.
    review_count = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "reviews_orgcanonicaltag"
        constraints = [
            models.UniqueConstraint(fields=["organisation", "label"],
                                    name="uniq_orgcanonicaltag_org_label"),
        ]
        indexes = [
            # Supports the top-N-by-review_count vocab fetch (D-02) and org-scoped reads.
            models.Index(fields=["organisation", "-review_count"],
                         name="orgcanon_org_count_idx"),
        ]
```
**Note:** decide `label` case-sensitivity of the unique constraint. Title-Case normalization (D-05) makes `(org, "Food Quality")` deterministic, so a plain unique constraint suffices — but document that "food quality" and "Food Quality" must normalize to the same value *before* the constraint check.

### Pattern 2: Nullable `canonical_tag` FK on `ReviewTag` (CTAG-02, CTAG-08)
```python
# Add to ReviewTag (apps/reviews/models.py)
canonical_tag = models.ForeignKey(
    "reviews.OrgCanonicalTag", null=True, blank=True,
    on_delete=models.SET_NULL,      # deleting a canonical tag must not delete review tags (Phase 25 merge re-points)
    related_name="review_tags", db_index=True,
)
```
**Migration:** single migration adds `OrgCanonicalTag` + the nullable FK. **No backfill** (criterion 5 / CTAG-08). Existing `ReviewTag` rows keep `canonical_tag = NULL` and stay valid. The existing `uniq_reviewtag_review_label_polarity` constraint is untouched — `canonical_tag` is NOT part of it, so adding the FK cannot break the delete-then-`bulk_create` race guard.

### Pattern 3: Pydantic `Tag` schema extension (CTAG-04, D-01, D-05)
**What:** add `canonical` (always present) + `polarity_type` (only meaningful for new tags) to `Tag`.
**Critical:** OpenAI Structured Outputs requires every field be `required`; "optional" must be a nullable union, NOT a Python default (see Pitfall 1).
```python
# Source: apps/integrations/openai/parser.py + OpenAI structured-outputs nullable rule
class Tag(BaseModel):
    label: str                                  # raw tag, lowercase 2-4 words (unchanged)
    polarity: Literal["positive", "negative", "neutral"]
    canonical: str                              # GPT's canonical mapping (existing-or-proposed)
    polarity_type: Literal["always_positive", "always_negative", "mixed"] | None  # nullable union, NOT Optional-with-default

    @field_validator("canonical")
    @classmethod
    def normalize_canonical(cls, v: str) -> str:
        # D-05: enforce Title Case + <=3 words SERVER-SIDE, mirroring max_five_tags.
        words = v.strip().split()[:3]           # truncate to <=3 words
        return " ".join(w.capitalize() for w in words) or v.strip().title()
```
- The `max_five_tags` validator at `EnrichmentResult` level already truncates to 5 tags; the canonical normalizer is a **field-level** validator on `Tag.canonical` and runs before the `EnrichmentResult` model is returned by `responses.parse`. VERIFY in a unit test that a validator that *mutates* a field does not cause `responses.parse` to reject the parsed object (it should not — validation runs on the SDK's `output_parsed`).
- The `polarity_type` union with `| None` is the SDK-safe way to express "may be absent for an existing-tag mapping". Do NOT write `polarity_type: ... = None` (a Python default) — that is what breaks strict schema generation (Pitfall 1).

### Pattern 4: Vocabulary injection into the prompt (CTAG-03, CTAG-04, CTAG-05)
**What:** extend `build_enrichment_messages` to receive the org's capped top-N canonical vocabulary and add the map-or-propose instruction.
```python
# Source: extends apps/integrations/openai/prompts.py build_enrichment_messages
def build_enrichment_messages(*, review: Any, canonical_vocab: list[str] | None = None) -> list[dict[str, str]]:
    ...
    vocab = canonical_vocab or []
    vocab_block = (
        "\nExisting canonical tags for this organisation (map each tag to ONE of these "
        "when it fits; otherwise propose a NEW canonical label in Title Case, <=3 words, "
        "English):\n" + ", ".join(vocab)
        if vocab else
        "\nThis organisation has no canonical tags yet — propose canonical labels "
        "(Title Case, <=3 words, English) for every tag.\n"
    )
    # system prompt gains: each tag must include 'canonical' (the mapped/proposed label) and,
    # WHEN proposing a NEW canonical label, a 'polarity_type' of always_positive|always_negative|mixed.
    ...
```
- The vocabulary list is fetched **before** the OpenAI call, inside `enrich_review`, using `review.organisation_id` (already `select_related`). Use a dedicated selector (`get_org_vocabulary(org_id, limit=settings.CANONICAL_VOCAB_INJECT_LIMIT)`).
- English-only is already enforced in `SYSTEM_PROMPT`; extend the wording to cover canonical labels explicitly (CTAG-05).
- **Bump `ENRICHMENT_PROMPT_VERSION` 3 → 4.** Do NOT trigger bulk re-enrichment (deferred).
- Token framing: ~150–300 extra input tokens/review (300 tags ≈ 1,800 tokens, far under 128k). [CITED: spec §6.4]. The top-N cap (D-02) bounds this. Tracked via `AiUsageLog.prompt_tokens` already.

### Pattern 5: Fold canonical mapping into `_persist_success` (CTAG-06, CTAG-07)
**What:** inside the existing `transaction.atomic()` in `_persist_success`, after delete and before/within `bulk_create`, resolve each tag's canonical FK.
```python
# Source: extends apps/reviews/services/enrichment.py _persist_success (lines ~91-128)
with transaction.atomic():
    Review.objects.filter(pk=review.pk).update(...)        # unchanged
    ReviewTag.objects.filter(review_id=review.pk).delete()  # unchanged

    org_id = review.organisation_id                         # already loaded (select_related)
    new_rows = []
    for tag in result.tags:
        canonical_tag = _get_or_create_canonical(           # get_or_create + IntegrityError catch
            organisation_id=org_id,
            label=tag.canonical,                            # already normalized by Pydantic validator
            polarity_type=tag.polarity_type,                # used ONLY on create; ignored on match
        )
        new_rows.append(ReviewTag(
            review_id=review.pk, label=tag.label.title(),
            polarity=tag.polarity, canonical_tag=canonical_tag,   # FK populated (CTAG-02)
        ))
    ReviewTag.objects.bulk_create(new_rows)
    AiUsageLog.objects.create(...)                          # STILL exactly one row (CTAG-07)
```
- `_get_or_create_canonical` uses `OrgCanonicalTag.objects.get_or_create(organisation_id=..., label=..., defaults={"polarity_type": ...})` wrapped to catch `IntegrityError` and re-`get` on the race (Pitfall 4).
- **`review_count` is NOT touched here** (D-03 — derive-on-read). This is the single most important divergence from spec §4/success-criterion-1 wording (see Pitfall 5).
- **Query-count impact:** the canonical lookups add up to N queries (one `get_or_create` per tag, ≤5 tags). This is inside the hot path. Mitigation: bulk-resolve existing canonical tags in one query (`OrgCanonicalTag.objects.filter(organisation_id=org_id, label__in=labels)`), then `bulk_create` only the missing ones, then map FKs — keeps it to ~2-3 queries regardless of tag count. A `CaptureQueriesContext` test must assert a fixed ceiling (CLAUDE.md §6.9).

### Anti-Patterns to Avoid
- **Incrementing a `review_count` counter inline in `_persist_success`** — violates D-03; re-enrichment (delete-then-bulk_create) would double-count. Derive on read.
- **Adding a second OpenAI call to map/classify tags** — violates CTAG-04/CTAG-07. Mapping is in the single call; persistence is pure DB.
- **`polarity_type: ... = None` with a default** — breaks Structured Outputs strict schema (Pitfall 1). Use `| None` union, no default.
- **Emitting WebSocket/progress events inside the transaction** — existing code already defers these to `transaction.on_commit` / post-commit; keep canonical work strictly DB-write inside the atomic block.
- **A per-`(org,label)` Redis lock** — unnecessary; the DB unique constraint + IntegrityError catch is the race guard (discretion item).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Race-safe insert of `(org,label)` | Custom Redis lock + check-then-insert | `get_or_create` + `IntegrityError` catch against the unique constraint | Standard Django idiom; DB constraint is authoritative; concurrent workers converge |
| Mapping raw→canonical tag | A second GPT classification call, or fuzzy string matching, or embeddings/pgvector | The single existing GPT call returns `canonical` | CTAG-04/07 — no extra cost, no vector DB (explicitly out of scope) |
| Structured-output parsing of new fields | Hand-parsing JSON | `responses.parse(text_format=EnrichmentResult)` + Pydantic | Already the contract; SDK + Pydantic handle schema + validation |
| `review_count` accuracy | A hot counter with inline increment/decrement | Derive-on-read aggregate over `ReviewTag.canonical_tag` | D-03 — avoids drift from re-enrichment delete-then-recreate |
| Label normalization | Prompt-only "please use Title Case" | Server-side Pydantic `field_validator` | D-05 — never trust the model for an invariant |

**Key insight:** The entire phase is "extend, don't invent." Every problem already has a chosen idiom in the codebase (`max_five_tags` validator, `get_or_create`-style races, the single-call structured-output contract, the `transaction.atomic()` write block). The risk is *deviating* from these, not lacking them.

## Runtime State Inventory

> This is a migration/schema-extension phase touching a live enrichment pipeline. Inventory below.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | Existing `ReviewTag` rows (all orgs) — will gain a `canonical_tag` column defaulting NULL. Existing enriched `Review` rows at `enrichment_version` reflecting prompt v3. | **No backfill** (CTAG-08 / criterion 5). New column is nullable; old rows stay valid. Bumping `ENRICHMENT_PROMPT_VERSION` to 4 does NOT re-enrich existing rows (deferred). |
| Live service config | Celery `enrich_review_task` routed to `ai-enrichment` queue (`CELERY_TASK_ROUTES`). No existing `rate_limit` anywhere (verified — grep found none). | Add `rate_limit` to the task decorator, value from new env setting. NO existing rate limit to migrate. |
| OS-registered state | None — no Task Scheduler / cron / systemd units reference tags. Celery Beat schedules (`enqueue_incremental_syncs_task`, `retry_failed_enrichments_task`) unaffected. | None — verified by reading `tasks.py`; no Beat schedule changes in P22. |
| Secrets/env vars | `OPENAI_*`, `LANGSMITH_*` unchanged. **New** env vars: vocab-inject cap (default ~200) and enrichment rate limit (default ~500/min). | Add to `.env.example` and `config/settings/base.py`. No secret rotation. |
| Build artifacts | None — no compiled artifacts; pure Python + a Django migration. | New migration file under `apps/reviews/migrations/`. Run `makemigrations --check` (CI gate, CLAUDE.md §19). |

**Migration safety note:** Adding a nullable FK column to a large `ReviewTag` table on Postgres is a metadata-only operation in PG 11+ (no table rewrite) — adding a nullable column without a volatile default is fast. The new index on `canonical_tag` will build; for a large table consider `CONCURRENTLY` (but Django migrations don't do this by default — likely fine at current 56-store scale; flag for the planner if table is large).

## Common Pitfalls

### Pitfall 1: Structured Outputs rejects optional fields with defaults
**What goes wrong:** Adding `polarity_type: Literal[...] | None = None` (with a Python default) or a constrained type causes `responses.parse` to generate a schema OpenAI rejects, or silently makes the field "not required," producing parse failures / `output_parsed=None` → `EnrichmentParseError`.
**Why it happens:** OpenAI Structured Outputs supports only a subset of JSON Schema. **Every property must be in `required`.** "Optional" is expressed as a nullable union (`{"type": ["string","null"]}`), i.e. `X | None` in Pydantic — NOT via a default value, and NOT via Pydantic constraints (min/max etc., which the SDK strips/rejects). [CITED: developers.openai.com/api/docs/guides/structured-outputs; community.openai.com optional-values thread]
**How to avoid:** Model `polarity_type` as `Literal[...] | None` with **no default**. Keep `canonical: str` as a plain required string. Add a unit test that introspects the generated schema (or, simpler, an integration test with a mocked response that omits `polarity_type` for an existing-tag mapping and asserts it parses).
**Warning signs:** `output_parsed=None`, `EnrichmentParseError` raised, or the model "refusing." The existing `test_output_parsed_none_raises_parse_error` test covers the symptom; add positive coverage for the new fields.

### Pitfall 2: Accidentally introducing a second OpenAI call
**What goes wrong:** A reviewer "factors out" canonical classification into its own GPT call, producing 2 `AiUsageLog` rows and a cost-per-review regression — violating CTAG-04 and CTAG-07.
**How to avoid:** All canonical signal (`canonical`, `polarity_type`) comes from the ONE existing `call_openai_enrichment`. Persistence is pure DB inside `_persist_success`. Add/keep a test asserting exactly one `AiUsageLog` row per `enrich_review` (existing `test_usage_log_written_on_success` pattern).
**Warning signs:** >1 `AiUsageLog` row per review; a new function calling `client.responses` / `chat.completions`.

### Pitfall 3: Query-count regression in the hot path
**What goes wrong:** A naive per-tag `get_or_create` adds N queries per enrichment; under load this multiplies across thousands of reviews. Violates CLAUDE.md §6 no-N+1.
**How to avoid:** Batch-resolve: one `filter(label__in=labels)` SELECT + one `bulk_create` for the missing ones; map FKs in Python. Plus one SELECT to fetch the inject vocabulary. Assert a fixed ceiling with `CaptureQueriesContext` (CLAUDE.md §6.9). Note the vocab SELECT is per-review; the existing `select_related("shop__organisation")` already loaded the org.
**Warning signs:** Query count scaling with tag count in a `CaptureQueriesContext` test.

### Pitfall 4: The `(organisation, label)` insert race
**What goes wrong:** Two workers enriching different reviews for the same org concurrently both propose the same new canonical label → one hits `IntegrityError` on the unique constraint and the whole enrichment transaction rolls back.
**How to avoid:** `get_or_create` then catch `IntegrityError` and re-`get` (the standard Django pattern). Because `_persist_success` is inside `transaction.atomic()`, an unhandled `IntegrityError` poisons the transaction — so the catch must either (a) be structured so the failed INSERT is in a nested `transaction.atomic()` savepoint, or (b) pre-resolve labels with a single SELECT + `bulk_create(..., ignore_conflicts=True)` then re-SELECT to get FKs. **(b) is cleaner inside an outer atomic block** — `ignore_conflicts=True` avoids poisoning the transaction entirely. Recommend (b) to the planner.
**Warning signs:** `TransactionManagementError` ("current transaction is aborted") in logs; intermittent enrichment failures under concurrent load.

### Pitfall 5: `review_count` "incremented" wording vs derive-on-read decision
**What goes wrong:** Success-criterion 1 and spec §4 say "reused + counted on match" / "review_count++". Taken literally this means a hot counter — which D-03 explicitly rejects (re-enrichment double-counts).
**How to avoid (the reconciliation):** Treat `review_count` as a **denormalized cache column that defaults to 0 and is NOT written in the enrichment path**. The authoritative count is **derived on read** via an aggregate the future Phase 25 tag-list page runs:
```python
# Derive-on-read shape (Phase 25 consumes this; P22 just needs the FK + model to support it)
OrgCanonicalTag.objects.filter(organisation_id=org_id).annotate(
    derived_count=Count("review_tags", distinct=True)   # via the canonical_tag related_name
)
```
The cache column (if kept) is refreshed only by the Phase 24 weekly job / Phase 25 merge. **The planner must phrase the CTAG-01 task as "model has a `review_count` cache column, populated 0, not incremented inline" and add a derive-on-read selector** — and explicitly note the success-criterion-1 wording is satisfied by derive-on-read, not by a hot counter. This is the one place the spec/criteria and the locked decision diverge; D-03 wins.
**Warning signs:** A planned task that says "increment review_count in _persist_success."

### Pitfall 6: QUEUE-02 — Celery `rate_limit` is NOT global
**What goes wrong:** CONTEXT.md's discretion note and the spec both say a "global rate limit across all workers (~500/min)." But `rate_limit` on a `@shared_task` is enforced **per worker instance**, not globally. With 4 workers and `rate_limit="500/m"`, the platform does up to **2000/min**, not 500. [CITED: docs.celeryq.dev/en/stable/userguide/tasks.html — "Note that this is a per worker instance rate limit, and not a global rate limit"; OpenAI/Celery community confirms]
**How to avoid — two viable options for the planner (this needs a decision):**
1. **Per-worker division (simplest, ships in P22):** set `rate_limit` to `TARGET / worker_count`. Make `worker_count` and target env-configurable; document the caveat loudly. Acceptable as an interim TPM safety-net. Set value via `ENRICHMENT_RATE_LIMIT` env (e.g. `"125/m"` for 500 target ÷ 4 workers). Format strings: `"<n>/s"`, `"<n>/m"`, `"<n>/h"`.
2. **True-global token bucket in Redis (matches CLAUDE.md §7.7 `rate:openai:project`):** a distributed counter checked before the OpenAI call; exceed → re-queue with countdown. More work; this is the architecturally-correct global throttle and likely belongs with the Phase 23 queue split (QUEUE-01).
**Recommendation:** Ship option 1 in P22 (it satisfies "configurable rate limit" literally and is a real safety net), and **flag to the user** that "global across all workers" is not achievable with the task `rate_limit` option alone — defer true-global to Phase 23 or implement the Redis token bucket. Mark this an ASSUMED-correction (see Assumptions Log A1).
**Mechanism:** add `rate_limit=settings.ENRICHMENT_RATE_LIMIT` to the `enrich_review_task` decorator. Runtime override is also possible via `app.control.rate_limit("apps.reviews.tasks.enrich_review_task", "X/m")` but env-on-decorator is the right default.
**Warning signs:** A task or test asserting "global 500/min" with a single `rate_limit` decorator and >1 worker.

### Pitfall 7: Validator mutation vs Structured Outputs
**What goes wrong:** A `field_validator` that *rewrites* `canonical` (Title Case) runs during Pydantic validation of `output_parsed`. This is safe — but if a contributor instead adds a `pattern`/`constr` constraint to enforce the format at the schema level, the SDK strips/rejects it (same family as Pitfall 1).
**How to avoid:** Enforce format with a **post-parse `field_validator` (mutating)**, never with a JSON-schema constraint. Mirror `max_five_tags` exactly.

### Pitfall 8: Backward-compat for existing queries
**What goes wrong:** Existing selectors/serializers that read `ReviewTag` might assume `canonical_tag` is always set once the column exists.
**How to avoid:** The column is nullable; all pre-phase rows are NULL (CTAG-08). Any new aggregation that joins on `canonical_tag` must filter `canonical_tag__isnull=False` (this is exactly TDASH-02, deferred to Phase 25). P22 adds no read path that assumes non-null. Confirm no existing serializer eagerly requires it.

## Code Examples

### Mocking the extended structured response in tests
```python
# Source: existing pattern in apps/integrations/openai/tests/test_client.py + test_enrichment_service.py
from apps.integrations.openai.parser import EnrichmentResult

def _build_result_with_canonical():
    return EnrichmentResult.model_validate({
        "sentiment": "positive",
        "tags": [
            # existing-tag mapping: polarity_type null
            {"label": "fast service", "polarity": "positive",
             "canonical": "Staff & Service", "polarity_type": None},
            # new-tag proposal: polarity_type present
            {"label": "great coffee", "polarity": "positive",
             "canonical": "Food Quality", "polarity_type": "always_positive"},
        ],
        "action_items": [],
    })

# Patch the service-level seam (call_openai_enrichment), not the SDK, for service tests:
with patch("apps.reviews.services.enrichment.call_openai_enrichment",
           return_value=(_build_result_with_canonical(), _usage())):
    enrich_review(review_id=review.pk)
```

### Idempotency / re-enrichment test (no duplicate canonical rows, no miscount)
```python
# Run enrich_review twice; assert:
#   - OrgCanonicalTag count for the org is stable (get_or_create dedupes)
#   - ReviewTag rows re-created with FK set (delete-then-bulk_create)
#   - derive-on-read count is correct (1, not 2) because review_count is NOT a hot counter
```

### Query-count ceiling test (CLAUDE.md §6.9)
```python
from django.test.utils import CaptureQueriesContext
from django.db import connection

def test_enrich_review_query_count_bounded():
    review = ReviewFactory(comment="great fast service")
    with patch("apps.reviews.services.enrichment.call_openai_enrichment",
               return_value=(_build_result_with_canonical(), _usage())), \
         patch("apps.reviews.services.enrichment._emit_enrichment_progress", return_value=None):
        with CaptureQueriesContext(connection) as ctx:
            enrich_review(review_id=review.pk)
    assert len(ctx.captured_queries) <= 12   # fixed ceiling, NOT proportional to tag count
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| JSONB `tags` column + `canonical_tag_id` on `Review` (spec §4) | Relational `ReviewTag` model; canonical via FK on `ReviewTag` + new `OrgCanonicalTag` | v0.6 Phase 17 (migration 0008 dropped JSONField) | Spec §4 is SUPERSEDED — do not implement its JSONB design [VERIFIED: SUMMARY.md + models.py:128] |
| `Optional[X]` / defaulted fields for OpenAI optional outputs | Nullable union `X \| None`, all fields required | OpenAI Structured Outputs (strict mode) | Defaulted optionals break strict schema [CITED: developers.openai.com] |

**Deprecated/outdated:**
- Spec §4 JSONB / `canonical_tag_id` data model — superseded by the relational reconciliation. Use `OrgCanonicalTag` + FK.
- The success-criterion-1 phrase "review_count incremented" — superseded by D-03 derive-on-read.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Celery task `rate_limit` cannot satisfy QUEUE-02's "global across all workers" — interim is per-worker division; true-global needs a Redis token bucket (likely Phase 23). | Pitfall 6, Summary | If the user truly needs a hard global TPM cap in P22, option 1 (per-worker division) under-throttles when workers scale up — could exceed OpenAI TPM. Needs user/architect decision. **VERIFIED that rate_limit is per-worker; ASSUMED that deferring true-global is acceptable.** |
| A2 | Adding a nullable FK + index to `ReviewTag` is fast (metadata-only) at current scale; no `CONCURRENTLY` needed. | Runtime State Inventory | If `ReviewTag` is very large, the index build could lock writes briefly. Low risk at 56-store scale. |
| A3 | A mutating `field_validator` on `canonical` does not break `responses.parse` (validation runs on the SDK's parsed object). | Pattern 3, Pitfall 7 | If wrong, normalization must move to `_persist_success` post-parse. Low risk; mirrors `max_five_tags`. Verify with one test. |
| A4 | `recommend ignore_conflicts=True bulk_create` for canonical inserts inside the outer atomic block avoids transaction poisoning. | Pitfall 4 | If `get_or_create` is used instead without a savepoint, an IntegrityError aborts the whole enrichment transaction. Architect should pick the savepoint or ignore_conflicts approach. |

**These four items need confirmation before becoming locked plan decisions** — especially A1 (QUEUE-02 semantics), which contradicts the literal CONTEXT.md discretion wording.

## Open Questions (RESOLVED)

1. **QUEUE-02 acceptance bar**
   - What we know: `rate_limit` is per-worker; spec/CONTEXT want global ~500/min.
   - **RESOLVED (→ D-06):** Ship per-worker `rate_limit` env setting in P22 + document the per-worker caveat; defer true-global Redis token bucket to Phase 23 (QUEUE-01) where queues split anyway. Confirmed with the user; implemented in 22-06.

2. **Canonical-label unique-constraint case handling**
   - What we know: D-05 normalizes to Title Case before insert, so `(org, "Food Quality")` is deterministic.
   - **RESOLVED (→ D-05 / discretion):** plain unique `(organisation, label)` is sufficient because normalization is server-side and deterministic; document the "normalize before lookup" invariant. No functional `Lower` index. Implemented in 22-01.

3. **Vocab-inject cap default**
   - What we know: D-02 says configurable, default ~200; spec §6.4 cites 300 tags ≈ 1,800 tokens as still cheap.
   - **RESOLVED (→ D-02):** default the setting to 200, named `CANONICAL_VOCAB_INJECT_LIMIT`, env-overridable. Implemented in 22-02.

## Environment Availability

> External dependencies are unchanged from the existing enrichment pipeline (OpenAI, Redis, Postgres, Celery). No new tools introduced. Phase is code + one migration + config.

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| OpenAI Responses API | enrichment call | ✓ (already in use) | openai 2.33.0 | — |
| PostgreSQL | new model + FK migration | ✓ | 16 (docker-compose) | — |
| Redis | existing enrichment lock | ✓ | 7 | — |
| Celery | enrich_review_task | ✓ | 5.x | — |

**Missing dependencies with no fallback:** None.
**Missing dependencies with fallback:** None.

## Validation Architecture

> nyquist_validation not found in config as `false` → treated as enabled.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + pytest-django (CLAUDE.md §16) |
| Config file | `pyproject.toml` (ruff/mypy/pytest config) |
| Quick run command | `pytest apps/reviews/tests/test_enrichment_service.py apps/integrations/openai/tests/test_parser.py -x` |
| Full suite command | `pytest --cov=apps --cov-fail-under=85` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CTAG-01 | OrgCanonicalTag created with org FK + polarity_type, unique (org,label) | unit | `pytest apps/reviews/tests/test_models.py -k canonical` | ❌ Wave 0 |
| CTAG-02 | ReviewTag.canonical_tag FK populated post-enrichment | integration | `pytest apps/reviews/tests/test_enrichment_service.py -k canonical_fk` | ❌ Wave 0 |
| CTAG-03/05 | Prompt injects vocab; canonical English-only instruction present | unit | `pytest apps/integrations/openai/tests/test_prompts.py -k vocab` | ❌ Wave 0 (file exists, add cases) |
| CTAG-04 | Tag schema parses canonical + nullable polarity_type | unit | `pytest apps/integrations/openai/tests/test_parser.py -k canonical` | ❌ Wave 0 (file exists, add cases) |
| CTAG-06 | Mapping inside atomic block; rollback on failure | integration | `pytest apps/reviews/tests/test_enrichment_service.py -k atomic` | ❌ Wave 0 |
| CTAG-07 | Exactly one AiUsageLog row per enrich | integration | `pytest apps/reviews/tests/test_enrichment_service.py -k usage_log` | ✅ (extend existing) |
| CTAG-08 | Pre-phase null canonical_tag rows stay valid | unit/migration | `pytest apps/reviews/tests/test_models.py -k null_canonical` | ❌ Wave 0 |
| QUEUE-02 | enrich_review_task has rate_limit from setting | unit | `pytest apps/reviews/tests/test_tasks.py -k rate_limit` | ❌ Wave 0 (file exists) |
| — | Query-count ceiling for enrich hot path | perf | `pytest apps/reviews/tests/test_enrichment_service.py -k query_count` | ❌ Wave 0 |
| — | Idempotency: re-enrich → no dup canonical, no miscount | integration | `pytest apps/reviews/tests/test_enrichment_service.py -k idempot` | ✅ (extend existing) |

### Sampling Rate
- **Per task commit:** quick run (parser + enrichment service tests)
- **Per wave merge:** `pytest apps/reviews apps/integrations/openai`
- **Phase gate:** full suite green (`pytest --cov=apps --cov-fail-under=85`) before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `apps/reviews/tests/factories.py` — add `OrgCanonicalTagFactory`
- [ ] `apps/integrations/openai/tests/fixtures/enrichment_success.json` — add `canonical` + `polarity_type` to tags (or a new fixture) so existing parser tests reflect the new schema
- [ ] Extend `test_parser.py` — canonical normalization + nullable polarity_type parse cases
- [ ] Extend `test_prompts.py` — vocab injection + prompt-version bump assertion
- [ ] New canonical-mapping cases in `test_enrichment_service.py` (FK populate, atomic rollback, query-count, idempotency)
- [ ] `test_tasks.py` — assert `enrich_review_task` carries `rate_limit`

## Security Domain

> security_enforcement not disabled in config → included.

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | No new auth surface in P22 (pipeline-internal) |
| V3 Session Management | no | — |
| V4 Access Control | yes | **Tenant scoping** — `OrgCanonicalTag` carries direct `organisation` FK; every read/write filters by org (CLAUDE.md §9). P22 has no user-facing endpoint, but the model must be org-scoped from day one so Phase 25's Tags page inherits correct isolation. |
| V5 Input Validation | yes | GPT output validated via Pydantic (`EnrichmentResult`, canonical normalizer). Review text already moderated (`moderate_input`). Never trust the model for the label-format invariant (D-05). |
| V6 Cryptography | no | — |

### Known Threat Patterns for Django + GPT pipeline
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Cross-tenant canonical-tag leakage | Information Disclosure | Direct `organisation` FK + org-filtered queries; vocab injection scoped to `review.organisation_id` only |
| Prompt-injection via review text influencing canonical labels | Tampering | Server-side label normalizer (D-05) bounds output to Title Case ≤3 words; review text already moderated; English-only enforced |
| Cost/DoS via unbounded vocabulary growth in prompt | DoS (cost) | Top-N cap (D-02); token cost bounded (~150–300 extra tokens); tracked in AiUsageLog |
| Logging review PII in prompts | Information Disclosure | CLAUDE.md §22 — review text must not be logged at INFO+; existing pipeline complies; canonical work adds no new logging of review content |

## Sources

### Primary (HIGH confidence)
- Codebase (direct reads): `apps/integrations/openai/parser.py`, `prompts.py`, `client.py`; `apps/reviews/services/enrichment.py`, `models.py`, `tasks.py`, `tests/factories.py`, `tests/test_enrichment_service.py`; `apps/integrations/openai/tests/test_parser.py`, `factories.py`, `fixtures/enrichment_success.json`; `config/settings/base.py`; `pyproject.toml` — verified versions (openai 2.33.0, pydantic 2.13.3) and exact integration seams.
- `.planning/research/SUMMARY.md` — relational `ReviewTag` ground truth; no `canonical_tag_id` exists.
- `.planning/phases/22-.../22-CONTEXT.md` — locked decisions D-01..D-05 + discretion.
- `docs/completed/ReviewBee_Canonical_Tag_Requirements_v1.0.md` §6.4 (token cost ~150–300/review; 300 tags ≈ 1,800 tokens) — extracted via XML.
- OpenAI Structured Outputs guide — required-fields / nullable-union rule. https://developers.openai.com/api/docs/guides/structured-outputs
- Celery Tasks docs — `rate_limit` is per-worker-instance, not global; formats `/s` `/m` `/h`. https://docs.celeryq.dev/en/stable/userguide/tasks.html

### Secondary (MEDIUM confidence)
- OpenAI Developer Community — "Optional Values not working" with Responses API + Pydantic (confirms nullable-union requirement). https://community.openai.com/t/using-responses-api-with-structured-output-and-pydantic-optional-values-not-working/1309774
- Celery issue #5732 — rate limiting with multiple workers (confirms divide-by-worker-count workaround). https://github.com/celery/celery/issues/5732

### Tertiary (LOW confidence)
- None relied upon.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libs already pinned + in use, versions verified in pyproject.toml
- Architecture: HIGH — extends existing, directly-read code seams
- Pitfalls: HIGH — both top risks (Structured Outputs nullable fields; Celery per-worker rate_limit) verified against official docs

**Research date:** 2026-06-10
**Valid until:** 2026-07-10 (stable internal codebase; OpenAI Structured Outputs + Celery rate_limit semantics are stable APIs)
