# Phase 22: Canonical Tag Foundation & Mapping Pipeline - Pattern Map

**Mapped:** 2026-06-10
**Files analyzed:** 9 (3 new/optional, 6 modified)
**Analogs found:** 9 / 9 (all in-repo — this is an "extend, don't invent" phase)

> Every file in this phase extends an existing, directly-read seam. The closest
> analog for almost every change lives in the *same file* being modified. The
> planner should instruct executors to mirror the surrounding conventions exactly
> rather than introduce new idioms.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `apps/reviews/models.py` — new `OrgCanonicalTag` model | model | CRUD | `apps/reviews/models.py` `ReviewTag` (same file) + `apps/integrations/openai/models.py` `AiPricing` (TextChoices + UniqueConstraint + org-FK) | exact |
| `apps/reviews/models.py` — `ReviewTag.canonical_tag` FK | model (migration) | CRUD | `Review.replied_by` nullable `SET_NULL` FK (`models.py:60`) | exact |
| `apps/reviews/migrations/00XX_*.py` | migration | — | existing `apps/reviews/migrations/` (nullable-col + index, no backfill) | role-match |
| `apps/integrations/openai/parser.py` — `Tag` schema + `canonical` validator | model (schema) | transform | `EnrichmentResult.max_five_tags` field_validator (same file) | exact |
| `apps/integrations/openai/prompts.py` — vocab injection + version bump | utility | transform | `build_enrichment_messages` + `SYSTEM_PROMPT` (same file) | exact |
| `apps/reviews/services/enrichment.py` — `_persist_success` fold-in | service | CRUD / event-driven | `_persist_success` ReviewTag delete-then-`bulk_create` block (same file, lines 91-128) | exact |
| `apps/reviews/selectors/canonical_tags.py` (NEW, optional) | selector | request-response | `apps/reviews/selectors/*` (CLAUDE.md §5 selector pattern) + derive-on-read aggregate | role-match |
| `apps/reviews/tasks.py` — `rate_limit` on `enrich_review_task` | task | event-driven | `enrich_review_task` decorator (same file, lines 168-175) | exact |
| `config/settings/base.py` — vocab cap + rate-limit settings | config | — | OpenAI/enrichment `env.int(...)` block (lines 157-174) | exact |
| `apps/reviews/tests/factories.py` — `OrgCanonicalTagFactory` | test | — | `ReviewTagFactory` (same file) | exact |
| test files (parser/prompts/tasks/enrichment/models) | test | — | `test_parser.py`, `test_prompts.py`, `test_tasks.py` (existing) | exact |

## Shared Patterns

### Tenant scoping (CLAUDE.md §9) — direct `organisation` FK
**Source:** `apps/reviews/models.py:34-39` (Review) and `apps/integrations/openai/models.py:61-66` (AiUsageLog)
**Apply to:** the new `OrgCanonicalTag` model.
```python
organisation = models.ForeignKey(
    "organisations.Organisation",
    on_delete=models.CASCADE,
    related_name="reviews",   # -> "canonical_tags" for OrgCanonicalTag
    db_index=True,
)
```
Every read/write of `OrgCanonicalTag` filters by `organisation_id`. In the hot
path the org id is already loaded: `enrich_review` uses
`select_related("shop__organisation")` (enrichment.py:428) and resolves
`review.organisation_id` with no extra query.

### TimeStampedModel base (CTAG-01 timestamps)
**Source:** `apps/common/models.py:8-13`
**Apply to:** `OrgCanonicalTag` — inherit `TimeStampedModel` for `created_at`/`updated_at` (do NOT redeclare them). Note `ReviewTag` currently inherits plain `models.Model`; `OrgCanonicalTag` needs timestamps so use `TimeStampedModel` like `Review`/`AiPricing` do.

### TextChoices enum convention
**Source:** `apps/reviews/models.py:129-132` (`ReviewTag.Polarity`) and `apps/integrations/openai/models.py:56-59` (`AiUsageLog.Status`)
**Apply to:** `OrgCanonicalTag.PolarityType` (`always_positive`/`always_negative`/`mixed`) and the Pydantic `Tag.polarity_type` `Literal`.
```python
class Polarity(models.TextChoices):
    POSITIVE = "positive", "Positive"
    NEUTRAL = "neutral", "Neutral"
    NEGATIVE = "negative", "Negative"
```

### UniqueConstraint + named indexes in `Meta`
**Source:** `apps/reviews/models.py:142-159` (ReviewTag) and `apps/integrations/openai/models.py:39-49` (AiPricing)
**Apply to:** `OrgCanonicalTag` unique `(organisation, label)` + the `(organisation, -review_count)` index. Use `ClassVar[list[...]]` typing exactly as the existing models do (mypy strict, CLAUDE.md §17).
```python
class Meta:
    db_table = "reviews_orgcanonicaltag"
    constraints: ClassVar[list[models.BaseConstraint]] = [
        models.UniqueConstraint(
            fields=["organisation", "label"],
            name="uniq_orgcanonicaltag_org_label",
        ),
    ]
    indexes: ClassVar[list[models.Index]] = [
        models.Index(fields=["organisation", "-review_count"],
                     name="orgcanon_org_count_idx"),
    ]
```

### transaction.atomic() write block (CTAG-06)
**Source:** `apps/reviews/services/enrichment.py:91-128`
**Apply to:** canonical lookup/insert + FK population — fold INTO this existing block, never a second one. Events stay outside (see anti-pattern below).

---

## Pattern Assignments

### `apps/reviews/models.py` — `OrgCanonicalTag` model + `ReviewTag.canonical_tag` FK (CTAG-01, CTAG-02, CTAG-08)

**Analog:** `ReviewTag` (same file, lines 128-162) for shape; `Review.replied_by` (lines 60-67) for the nullable `SET_NULL` FK; `AiPricing` (`openai/models.py:29-52`) for TextChoices-free unique-constraint + QuerySet pattern if a manager is wanted.

**Existing `ReviewTag` to mirror** (lines 128-159):
```python
class ReviewTag(models.Model):
    class Polarity(models.TextChoices):
        POSITIVE = "positive", "Positive"
        NEUTRAL = "neutral", "Neutral"
        NEGATIVE = "negative", "Negative"

    review = models.ForeignKey("reviews.Review", on_delete=models.CASCADE, related_name="tags")
    label = models.CharField(max_length=100, db_index=True)
    polarity = models.CharField(max_length=10, choices=Polarity.choices)

    class Meta:
        db_table = "reviews_reviewtag"
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=["review", "label", "polarity"],
                name="uniq_reviewtag_review_label_polarity",
            ),
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=["review", "label"], name="reviewtag_review_label_idx"),
        ]
```

**New nullable FK to ADD to `ReviewTag`** — mirror `Review.replied_by` (lines 60-67) for the `SET_NULL` idiom:
```python
canonical_tag = models.ForeignKey(
    "reviews.OrgCanonicalTag", null=True, blank=True,
    on_delete=models.SET_NULL,      # deleting a canonical tag must NOT cascade-delete review tags (Phase 25 merge re-points)
    related_name="review_tags", db_index=True,
)
```
- **DO NOT** add `canonical_tag` to the existing `uniq_reviewtag_review_label_polarity` constraint — leaving it out keeps the delete-then-`bulk_create` race guard (lines 144-155) intact. (Research §Pattern 2, Pitfall 8.)
- **New `OrgCanonicalTag` model** inherits `TimeStampedModel` (NOT plain `models.Model` like ReviewTag) so it gets `created_at`/`updated_at`. `review_count = PositiveIntegerField(default=0)` is a **cache column, never incremented inline** (D-03 — see anti-pattern). `polarity_type` uses the `PolarityType` TextChoices.

**Migration:** single migration adds `OrgCanonicalTag` + the nullable FK + index. **No backfill** (CTAG-08). Existing `ReviewTag` rows keep `canonical_tag = NULL` and stay valid. Run `makemigrations --check` (CI gate, CLAUDE.md §19). Nullable-col add is metadata-only on PG 11+ (research §Runtime State; A2).

---

### `apps/integrations/openai/parser.py` — `Tag` schema extension + canonical normalizer (CTAG-04, D-01, D-05)

**Analog:** `EnrichmentResult.max_five_tags` field_validator (same file, lines 33-37) — the exact mutating-validator idiom to mirror for D-05.

**Existing validator to mirror** (lines 16-37):
```python
class Tag(BaseModel):
    label: str
    polarity: Literal["positive", "negative", "neutral"]

class EnrichmentResult(BaseModel):
    sentiment: Literal["positive", "neutral", "negative"]
    tags: list[Tag]
    action_items: list[ActionItem]

    @field_validator("tags")
    @classmethod
    def max_five_tags(cls, v: list[Tag]) -> list[Tag]:
        # Defensive: prompt enforces <=5, validator guarantees it server-side.
        return v[:5]
```

**Extension** — add `canonical: str` (plain required) + `polarity_type` as a **nullable union with NO default** (Structured Outputs strict-mode requirement, Pitfall 1), plus a **field-level mutating validator** mirroring `max_five_tags` (Pitfall 7):
```python
class Tag(BaseModel):
    label: str
    polarity: Literal["positive", "negative", "neutral"]
    canonical: str
    polarity_type: Literal["always_positive", "always_negative", "mixed"] | None   # NO `= None`

    @field_validator("canonical")
    @classmethod
    def normalize_canonical(cls, v: str) -> str:
        # D-05: Title Case, <=3 words, server-side — mirror max_five_tags (mutating validator).
        ...
```
- **NEVER** add a `pattern`/`constr` JSON-schema constraint to enforce the format — the SDK strips/rejects it (Pitfall 1 & 7). Enforce only via the post-parse `field_validator`.
- The shared `PolarityType` literal values must match the model's `OrgCanonicalTag.PolarityType` TextChoices exactly.

---

### `apps/integrations/openai/prompts.py` — vocab injection + version bump (CTAG-03, CTAG-04, CTAG-05)

**Analog:** `build_enrichment_messages` + `SYSTEM_PROMPT` (same file, lines 19-74). The English-only rule is already present (lines 27-28) — extend it to canonical labels.

**Existing builder to extend** (lines 56-74):
```python
def build_enrichment_messages(*, review: Any) -> list[dict[str, str]]:
    brand = review.shop.organisation.name
    shop_name = review.shop.name
    user_payload = (
        f"Brand: {brand}\n"
        f"Shop: {shop_name}\n"
        f"Star rating: {review.star_rating} of 5\n"
        f"Review text:\n{review.comment or '(no comment provided)'}"
    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_payload},
    ]
```
- Add a `canonical_vocab: list[str] | None = None` kwarg; append a vocab block to the user payload (map-or-propose instruction). Keep prompt context = brand + shop + rating + text only (Phase 12 lock — NO address, NO reviewer name).
- **Bump `ENRICHMENT_PROMPT_VERSION` 3 → 4** (line 19). Do NOT trigger bulk re-enrichment (deferred). Note `REPLY_GENERATION_PROMPT_VERSION` is a separate constant — do not touch it.

**⚠ Threading seam (load-bearing):** `call_openai_enrichment` calls `build_enrichment_messages(review=review)` at `apps/integrations/openai/client.py:200` with NO vocab arg today. The vocab must thread: `enrich_review` (fetch vocab via selector) → `call_openai_enrichment(review=..., canonical_vocab=...)` (new param at client.py ~190) → `build_enrichment_messages(review=..., canonical_vocab=...)` (line 200). The planner must update **all three signatures**, not just the prompt builder.

---

### `apps/reviews/services/enrichment.py` — fold canonical mapping into `_persist_success` (CTAG-06, CTAG-07)

**Analog:** the existing ReviewTag delete-then-`bulk_create` block in `_persist_success` (same file, lines 91-128).

**Existing block to extend** (lines 91-128):
```python
with transaction.atomic():
    Review.objects.filter(pk=review.pk).update(
        enrichment_status=Review.EnrichmentStatus.SUCCESS,
        sentiment=result.sentiment,
        extracted_action_items=[...],
        enrichment_version=models.F("enrichment_version") + 1,
    )
    ReviewTag.objects.filter(review_id=review.pk).delete()
    ReviewTag.objects.bulk_create(
        [ReviewTag(review_id=review.pk, label=tag.label.title(), polarity=tag.polarity)
         for tag in result.tags]
    )
    AiUsageLog.objects.create(...)   # EXACTLY ONE row — keep it exactly one (CTAG-07)
```

**Extension** — resolve canonical FKs inside the SAME atomic block, between delete and `bulk_create`:
- `org_id = review.organisation_id` (already loaded via `select_related("shop__organisation")` at line 428).
- **Batch-resolve to avoid N+1** (Pitfall 3, CLAUDE.md §6.9): one `OrgCanonicalTag.objects.filter(organisation_id=org_id, label__in=labels)` SELECT → `bulk_create(..., ignore_conflicts=True)` the missing ones → re-SELECT to map FKs. `ignore_conflicts=True` is the race-safe idiom that **does not poison the outer transaction** (Pitfall 4, vs `get_or_create` which would abort it).
- Populate `ReviewTag.canonical_tag=fk` in the existing `bulk_create` list comp.
- **`review_count` is NOT touched here** (D-03 derive-on-read — the single most important divergence from spec wording; Pitfall 5).
- `_emit_enrichment_progress` (line 131) and `_schedule_action_item_promotion` (line 139) stay AFTER commit — keep canonical work strictly inside the atomic block.
- The `_persist_success_no_comment` path (lines 210-234) has no tags → no canonical work, but its `ReviewTag.objects.filter(...).delete()` stays.

---

### `apps/reviews/selectors/canonical_tags.py` (NEW, optional) — vocab fetch + derive-on-read count (CTAG-03, D-02, D-03)

**Analog:** CLAUDE.md §5 selector pattern (read-only, `*`-kwargs, returns data). No existing selector in `apps/reviews/selectors/` reads canonical tags yet (it's new), so this is a role-match.

- `get_org_vocabulary(*, organisation_id: int, limit: int) -> list[str]` — `OrgCanonicalTag.objects.filter(organisation_id=...).order_by("-review_count")[:limit]`, returns labels. `limit` from `settings.CANONICAL_VOCAB_INJECT_LIMIT` (default ~200, D-02). Called from `enrich_review` before the OpenAI call.
- Derive-on-read aggregate (Phase 25 consumer; P22 just supports it):
  `.annotate(derived_count=Count("review_tags", distinct=True))` via the `canonical_tag` `related_name`.

---

### `apps/reviews/tasks.py` — `rate_limit` on `enrich_review_task` (QUEUE-02)

**Analog:** the `enrich_review_task` decorator (same file, lines 168-175).

**Existing decorator to extend** (lines 168-175):
```python
@shared_task(  # type: ignore[misc]
    bind=True,
    max_retries=3,
    autoretry_for=(OpenAITransientError, EnrichmentParseError),
    retry_backoff=30,
    retry_backoff_max=600,
    retry_jitter=True,
)
def enrich_review_task(self: Any, review_id: int) -> None:
```
**Extension** — add `rate_limit=settings.ENRICHMENT_RATE_LIMIT` (import `from django.conf import settings`). **CRITICAL caveat (D-06, Pitfall 6, Assumption A1):** Celery `rate_limit` is **PER-WORKER, not global**. Do NOT write a comment or test claiming "global ~500/min". Document the per-worker semantics and that true-global (Redis token bucket) is deferred to Phase 23. Set the env value as `target ÷ expected_workers` (e.g. `"125/m"` for 500÷4). Format strings: `"<n>/s"`, `"<n>/m"`, `"<n>/h"`. The task body stays unchanged.

---

### `config/settings/base.py` — vocab cap + rate-limit settings

**Analog:** the OpenAI/enrichment `env`/`env.int` block (lines 157-174).

**Existing block to mirror** (lines 157-174):
```python
OPENAI_MODEL = env("OPENAI_MODEL", default="gpt-4o-mini-2024-07-18")
OPENAI_REVIEW_TEXT_MAX_CHARS = env.int("OPENAI_REVIEW_TEXT_MAX_CHARS", default=4000)
INITIAL_SYNC_PAGE_SIZE = env.int("INITIAL_SYNC_PAGE_SIZE", default=50)
ENRICHMENT_BATCH_SIZE = env.int("ENRICHMENT_BATCH_SIZE", default=10)
```
**Add** (same idiom, alongside the enrichment settings):
```python
CANONICAL_VOCAB_INJECT_LIMIT = env.int("CANONICAL_VOCAB_INJECT_LIMIT", default=200)  # D-02
ENRICHMENT_RATE_LIMIT = env("ENRICHMENT_RATE_LIMIT", default="125/m")  # QUEUE-02; PER-WORKER (D-06)
```
Also add both to `.env.example` (research §Runtime State). `CELERY_TASK_ROUTES` (lines 120-126) already routes `enrich_review_task` to `ai-enrichment` — unchanged.

---

### `apps/reviews/tests/factories.py` — `OrgCanonicalTagFactory` (CTAG-01)

**Analog:** `ReviewTagFactory` (same file, lines 38-44) + `OrganisationFactory` SubFactory usage in `ReviewFactory` (lines 15-19).

**Existing factory to mirror** (lines 38-44):
```python
class ReviewTagFactory(DjangoModelFactory):
    class Meta:
        model = ReviewTag
    review = factory.SubFactory(ReviewFactory)
    label = factory.Faker("word")
    polarity = "positive"
```
**New** `OrgCanonicalTagFactory`: `organisation = factory.SubFactory(OrganisationFactory)`, `label = factory.Sequence(lambda n: f"Canonical {n}")`, `polarity_type = OrgCanonicalTag.PolarityType.MIXED`, `review_count = 0`.

---

### Test files (CTAG-01..08, QUEUE-02)

**Analogs (extend existing, do not invent new structure):**
- **`apps/integrations/openai/tests/test_parser.py`** (read in full) — add `canonical` + nullable `polarity_type` parse cases and a normalization (Title Case ≤3 words) case. Mirror `test_truncates_tags_over_five` (lines 30-37) for the mutating-validator assertion. **Update `tests/fixtures/enrichment_success.json`** (or add a fixture) so existing tags include `canonical` + `polarity_type` (Wave 0 gap — `test_parses_known_good_fixture` line 20 will break otherwise).
- **`apps/integrations/openai/tests/test_prompts.py`** — add vocab-injection cases and a `ENRICHMENT_PROMPT_VERSION == 4` assertion (mirror `test_prompt_version_constant_is_one` at line 29 and `test_user_payload_contains_brand_shop_rating_and_comment` at line 65).
- **`apps/reviews/tests/test_tasks.py`** — add `test_enrich_review_task_has_rate_limit` asserting the task carries `rate_limit` from the setting. Mirror `test_enrich_review_task_calls_service` (line 77) and `test_initial_backfill_dispatched_to_google_sync_queue` (line 63) for inspecting task config.
- **`apps/reviews/tests/test_enrichment_service.py`** — add canonical FK populate, atomic-rollback, idempotency (re-enrich → no dup `OrgCanonicalTag`, no miscount), and a `CaptureQueriesContext` query-count ceiling test (CLAUDE.md §6.9). Patch the service seam `apps.reviews.services.enrichment.call_openai_enrichment` (research §Code Examples), NOT the SDK. Extend the existing one-`AiUsageLog`-row assertion (CTAG-07).
- **`apps/reviews/tests/test_models.py`** — add `OrgCanonicalTag` creation, unique `(org, label)`, and null-`canonical_tag` validity (CTAG-08) cases.

## No Analog Found

None. Every file has a strong in-repo analog (most in the same file being modified). The only genuinely new file — `selectors/canonical_tags.py` — follows the established CLAUDE.md §5 selector convention and the derive-on-read aggregate shape spelled out in research §Pitfall 5.

## Metadata

**Analog search scope:** `apps/reviews/` (models, services, tasks, selectors, tests), `apps/integrations/openai/` (parser, prompts, models, client, tests), `apps/common/models.py`, `apps/organisations/tests/factories.py`, `config/settings/base.py`
**Files scanned:** 12 read in full or in targeted ranges
**Pattern extraction date:** 2026-06-10
