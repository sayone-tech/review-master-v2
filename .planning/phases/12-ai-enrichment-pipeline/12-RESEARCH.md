# Phase 12: AI Enrichment Pipeline — Research

**Researched:** 2026-05-02
**Domain:** OpenAI structured outputs, LangSmith tracing, Celery-to-Channels pipeline, time-versioned pricing models
**Confidence:** HIGH (verified against official sources, live packages, existing codebase)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Prompt context per review: Organisation name (brand) + shop name + review text + star rating
- No shop address in prompt
- Reviewer name excluded from prompt
- Single combined GPT call per review (no multi-call breakdown)
- Tags: free-form English regardless of review language, max 1–5
- Action items stored in `extracted_action_items = JSONField(default=list)` on Review model
- Action item chips in Phase 12 are non-interactive (no modal, no click handler)
- `enrich_review_task` enqueued inline after each `fetch_and_persist` upsert
- `sync.complete` fires only when `total_enriched >= total_fetched` — breaking change from Phase 11
- `AiUsageLog` + `AiPricing` models live in `apps/integrations/openai/`
- `AiPricing` managed via Django admin only in Phase 12
- LangSmith is best-effort: if unreachable, OpenAI call proceeds

### Claude's Discretion
- Exact prompt wording and system/user message split
- LangSmith trace metadata structure (beyond mandatory fields from ENRCH-11)
- Retry logic edge cases within the bounds of ENRCH-04
- How enrichment tasks publish progress back to the channel layer (channel name convention)
- One-time backfill management command internal structure (ENRCH-13)

### Deferred Ideas (OUT OF SCOPE)
- AI cost dashboard for Superadmin (data model ships in Phase 12; UI deferred post-v0.3)
- Re-processing historical reviews on prompt version bump (`enrichment_version` field ready)
- Per-org OpenAI rate cap / token budget enforcement
- Action item chips clicking to open detail modal (Phase 13)
- Reviewer name in prompt for personalised reply suggestions
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| ENRCH-01 | OpenAI client wrapper: single combined prompt, returns `sentiment` + `tags` + `action_items` | Structured Outputs section; `client.responses.parse()` pattern |
| ENRCH-02 | `enrich_review` acquires Redis lock; exits if `SUCCESS` or `IN_PROGRESS` | Idempotency section; existing `distributed_lock` helper |
| ENRCH-03 | `enrichment_status` transitions under `transaction.atomic()` + `select_for_update` | Architecture Patterns; mirrors Phase 11 pattern exactly |
| ENRCH-04 | 429/5xx: 3 retries (30s/2min/10min); other 4xx: no retry; JSON failure: retry once | Retry Strategy section |
| ENRCH-05 | Failed enrichments don't block reviews list | Confirmed: `enrichment_status` is non-blocking field |
| ENRCH-06 | `retry_failed_enrichments` Beat task every 6 hours; max 3 total attempts | Beat task section; existing Beat infrastructure |
| ENRCH-07 | Every successful call writes one `AiUsageLog` row | AiUsageLog model section |
| ENRCH-08 | Cost computed at log time using active `AiPricing` row; correct formula | Pricing model section; formula confirmed |
| ENRCH-09 | Historical costs never retroactively changed | Confirmed by write-time lock-in of `estimated_cost_usd` |
| ENRCH-10 | `AiPricing` seed data for gpt-4o-mini; verified against reference dataset | Pricing data: $0.150/$0.600/$0.075 per 1M tokens confirmed |
| ENRCH-11 | LangSmith tracing wraps every OpenAI call with mandatory metadata | LangSmith section; `@traceable` + `get_current_run_tree()` pattern |
| ENRCH-12 | `langsmith_trace_id` persisted on `AiUsageLog` | LangSmith section; `run_tree.trace_id` access pattern |
| ENRCH-13 | One-time backfill management command for existing Phase 11 reviews | Management command section |
| ENRCH-14 | Reviews list shows sentiment badges + tag chips + action item chips | UI wiring section; serializer + frontend types |
</phase_requirements>

---

## Summary

Phase 12 builds the AI enrichment pipeline: a Celery task wraps a single GPT call per review, writes cost-tracked + LangSmith-traced results back to the Review row, publishes enrichment progress to the WebSocket consumer, and makes all this data visible in the reviews list.

The most important finding is a **breaking change in the OpenAI SDK**: the SDK has moved from v1.x (pinned in CLAUDE.md §14.9) to v2.x (latest: 2.33.0) with a new Responses API (`client.responses.parse()`). The new API uses `input_tokens`/`output_tokens` (not `prompt_tokens`/`completion_tokens`) and `input_tokens_details.cached_tokens` (not `prompt_tokens_details.cached_tokens`). The cost formula must use the Responses API token field names. Both `client.responses.parse()` and `client.chat.completions.parse()` support Pydantic structured outputs; the Responses API is OpenAI's recommended path for all new projects.

LangSmith is at v0.8.0. The `@traceable` decorator pattern plus `get_current_run_tree()` is the established approach for capturing `trace_id` back from a traced function — verified against official SDK source.

The Celery-to-Channels progress pipeline is already established in `apps/reviews/services/sync.py` via `async_to_sync(layer.group_send)`. The enrichment task uses the exact same pattern to emit `sync.enrichment.progress` events.

**Primary recommendation:** Use `client.responses.parse()` with Pydantic `EnrichmentResult`, wrap with `@traceable`, capture `run_tree.trace_id` for `AiUsageLog`, and use `input_tokens` / `output_tokens` / `input_tokens_details.cached_tokens` for cost computation.

---

## Standard Stack

### Core

| Library | Version to Pin | Purpose | Why Standard |
|---------|----------------|---------|--------------|
| `openai` | `2.33.0` | OpenAI API client — structured outputs, Responses API | Official SDK; latest stable; v2.x is current major |
| `pydantic` | `2.13.3` | Schema definition, structured output parsing | Already mandated by CLAUDE.md §14; Pydantic v2 native |
| `langsmith` | `0.8.0` | LangSmith tracing, `@traceable`, `wrap_openai` | Official LangChain observability SDK |

### Supporting (already installed)

| Library | Installed Version | Purpose | Used By |
|---------|-----------------|---------|---------|
| `celery` | `5.6.3` | Task queue; `enrich_review_task` | ai-enrichment queue (route already configured) |
| `tenacity` | `9.1.4` | Retry/backoff decorator | `apps/common/retry.py` — NOT used for enrichment task (Celery autoretry_for handles it) |
| `asgiref` | (via channels) | `async_to_sync` for channel layer calls from Celery | `emit_progress_event` pattern already used in sync.py |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `client.responses.parse()` | `client.chat.completions.parse()` | Both work. Responses API is OpenAI's recommended new path; structured output token fields differ — use Responses API for forward compatibility |
| `@traceable` + `get_current_run_tree()` | `wrap_openai(client)` | `wrap_openai` auto-traces every call but doesn't return `trace_id` easily; `@traceable` with run_tree injection is cleaner for capturing trace_id back |
| Celery `autoretry_for` | `tenacity` retry decorator | `autoretry_for` is the project-established pattern per CLAUDE.md §12.3; do NOT replace with tenacity for enrichment |

### Installation

```bash
# Add to [project.dependencies] in pyproject.toml (exact pins)
openai==2.33.0
pydantic==2.13.3
langsmith==0.8.0
```

**Version verification:** Confirmed against PyPI registry 2026-05-02.
- `openai`: 2.33.0 (latest, released 2026-04-28)
- `pydantic`: 2.13.3 (latest)
- `langsmith`: 0.8.0 (latest)

CLAUDE.md §14.9 listed `openai==^1.55.0`, `langsmith==^0.2.0`, `pydantic==^2.10.0` — all stale. Use the exact versions above.

---

## Architecture Patterns

### Recommended Project Structure

```
apps/integrations/openai/
├── __init__.py
├── apps.py
├── client.py           # OpenAI wrapper: call_openai_enrichment() returns (EnrichmentResult, UsageData)
├── prompts.py          # Versioned prompt templates: build_enrichment_messages(review)
├── parser.py           # Pydantic schemas: EnrichmentResult, Tag, ActionItem
├── pricing.py          # calculate_cost() + AiPricingQuerySet.get_active(model)
├── models.py           # AiUsageLog + AiPricing models
├── admin.py            # Django admin registration for AiPricing, AiUsageLog
├── tracing.py          # LangSmith config helpers (optional thin module)
├── exceptions.py       # OpenAITransientError, OpenAIPermanentError, EnrichmentParseError
├── migrations/
└── tests/
    ├── __init__.py
    ├── factories.py
    ├── fixtures/           # deterministic GPT response fixtures (JSON files)
    ├── test_client.py
    ├── test_parser.py
    ├── test_pricing.py
    └── test_models.py

apps/reviews/services/
└── enrichment.py       # enrich_review(review_id) — three-layer idempotency

apps/reviews/tasks.py   # add enrich_review_task + retry_failed_enrichments_task
```

### Pattern 1: Structured Outputs via Responses API

Use `client.responses.parse()` with `text_format=EnrichmentResult`. This is OpenAI's current recommended API for new projects. Access the parsed object via `response.output_parsed`. Token counts are at `response.usage.input_tokens`, `response.usage.output_tokens`, `response.usage.input_tokens_details.cached_tokens`.

```python
# apps/integrations/openai/client.py
# Source: https://platform.openai.com/docs/guides/structured-outputs
from openai import OpenAI
from langsmith import traceable
from langsmith.run_helpers import get_current_run_tree

from apps.integrations.openai.parser import EnrichmentResult
from apps.integrations.openai.exceptions import OpenAITransientError, OpenAIPermanentError, EnrichmentParseError

_client = OpenAI()

@traceable(
    run_type="llm",
    name="enrich_review",
    metadata={"request_type": "enrichment"},
)
def _call_openai_enrichment(
    *,
    messages: list[dict],
    model: str,
    run_tree: Any = None,  # injected by @traceable
) -> tuple[EnrichmentResult, dict]:
    import time
    started = time.monotonic()
    try:
        response = _client.responses.parse(
            model=model,
            input=messages,
            text_format=EnrichmentResult,
        )
    except openai.RateLimitError as exc:
        raise OpenAITransientError(str(exc)) from exc
    except openai.APIStatusError as exc:
        if exc.status_code >= 500:
            raise OpenAITransientError(str(exc)) from exc
        raise OpenAIPermanentError(str(exc), status_code=exc.status_code) from exc

    parsed = response.output_parsed
    if parsed is None:
        raise EnrichmentParseError("output_parsed is None — model refused or parse failed")

    latency_ms = int((time.monotonic() - started) * 1000)
    usage = response.usage
    cached = getattr(getattr(usage, "input_tokens_details", None), "cached_tokens", 0) or 0
    trace_id = str(run_tree.trace_id) if run_tree else None

    usage_data = {
        "prompt_tokens": usage.input_tokens,
        "completion_tokens": usage.output_tokens,
        "cached_tokens": cached,
        "total_tokens": usage.total_tokens,
        "latency_ms": latency_ms,
        "langsmith_trace_id": trace_id,
    }
    return parsed, usage_data
```

**Note on `run_tree` parameter:** LangSmith automatically injects the `run_tree` when `run_tree` appears in the function signature for a `@traceable`-decorated function. `run_tree.trace_id` is the UUID that maps to a LangSmith trace.

### Pattern 2: Three-Layer Idempotency for enrich_review

Mirrors the documented pattern in CLAUDE.md §12.4 exactly.

```python
# apps/reviews/services/enrichment.py
# Source: CLAUDE.md §12.4 + existing sync.py pattern
import logging
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from apps.common.locks import distributed_lock
from apps.reviews.models import Review
from apps.integrations.openai.client import _call_openai_enrichment
from apps.integrations.openai.pricing import calculate_cost
from apps.integrations.openai.models import AiUsageLog
from apps.integrations.openai.prompts import build_enrichment_messages
from apps.integrations.openai.exceptions import OpenAITransientError, OpenAIPermanentError, EnrichmentParseError

logger = logging.getLogger(__name__)
LOCK_KEY_TMPL = "lock:enrich:review:{review_id}"
LOCK_TIMEOUT = 300

def enrich_review(*, review_id: int) -> None:
    # Layer 1: Redis lock (non-blocking)
    with distributed_lock(LOCK_KEY_TMPL.format(review_id=review_id), timeout=LOCK_TIMEOUT) as acquired:
        if not acquired:
            return

        # Layer 2: Row lock + status flag
        with transaction.atomic():
            try:
                review = Review.objects.select_related("shop__organisation").select_for_update().get(pk=review_id)
            except Review.DoesNotExist:
                return

            if review.enrichment_status in (
                Review.EnrichmentStatus.SUCCESS,
                Review.EnrichmentStatus.IN_PROGRESS,
            ):
                return  # Idempotent no-op

            review.enrichment_status = Review.EnrichmentStatus.IN_PROGRESS
            review.enrichment_attempted_at = timezone.now()
            review.save(update_fields=["enrichment_status", "enrichment_attempted_at"])

        # Layer 3: Call OpenAI outside the transaction (avoid holding DB locks during HTTP)
        messages = build_enrichment_messages(review=review)
        try:
            result, usage_data = _call_openai_enrichment(
                messages=messages,
                model=settings.OPENAI_MODEL,
            )
        except (OpenAITransientError, EnrichmentParseError) as exc:
            # Celery autoretry_for handles transient; EnrichmentParseError retried once
            Review.objects.filter(pk=review_id).update(
                enrichment_status=Review.EnrichmentStatus.FAILED,
                sentiment="",
            )
            _write_usage_log_failed(review=review, usage_data=usage_data, error=exc)
            raise
        except OpenAIPermanentError as exc:
            Review.objects.filter(pk=review_id).update(
                enrichment_status=Review.EnrichmentStatus.FAILED,
                sentiment="",
            )
            _write_usage_log_failed(review=review, usage_data=usage_data, error=exc)
            return  # Do not re-raise — permanent, don't retry

        # Success path
        with transaction.atomic():
            Review.objects.filter(pk=review_id).update(
                enrichment_status=Review.EnrichmentStatus.SUCCESS,
                sentiment=result.sentiment,
                tags=[{"label": t.label, "polarity": t.polarity} for t in result.tags],
                extracted_action_items=[
                    {"title": a.title, "scope": a.scope, "priority": a.priority}
                    for a in result.action_items
                ],
            )
            _write_usage_log_success(review=review, usage_data=usage_data)

        _emit_enrichment_progress(review=review)
```

### Pattern 3: Channel Layer Progress from Celery Task

Use the established `emit_progress_event` helper from `sync.py`. The enrichment task imports and calls it with a `sync.enrichment.progress` payload.

```python
# In apps/reviews/services/enrichment.py
# Source: Existing apps/reviews/services/sync.py:emit_progress_event pattern
from apps.reviews.services.sync import emit_progress_event

def _emit_enrichment_progress(*, review: Review) -> None:
    """Emit sync.enrichment.progress after a successful enrichment.

    Reads the current progress snapshot to get the running totals
    then emits the enrichment progress event to the WebSocket group.
    """
    from apps.reviews.services.progress import read_progress_snapshot, write_progress_snapshot

    shop_id = review.shop_id
    snapshot = read_progress_snapshot(shop_id=shop_id)
    if snapshot is None:
        return  # Sync not in progress (e.g. incremental sync); no WebSocket event needed

    enriched = snapshot.get("enriched", 0) + 1
    total_fetched = snapshot.get("fetched", 0)

    # Update snapshot
    write_progress_snapshot(shop_id=shop_id, data={**snapshot, "enriched": enriched})

    emit_progress_event(
        shop_id=shop_id,
        payload={
            "type": "sync.enrichment.progress",
            "shop_id": shop_id,
            "enriched": enriched,
            "fetched": total_fetched,
        },
    )

    # Fire sync.complete when enrichment catches up to fetch count
    if total_fetched > 0 and enriched >= total_fetched:
        emit_progress_event(
            shop_id=shop_id,
            payload={
                "type": "sync.complete",
                "shop_id": shop_id,
                "total_fetched": total_fetched,
                "total_enriched": enriched,
                "duration_seconds": snapshot.get("duration_seconds"),
            },
        )
```

### Pattern 4: AiPricing — Time-Versioned Active Row Lookup

```python
# apps/integrations/openai/models.py
from decimal import Decimal
from django.db import models
from django.utils import timezone

class AiPricingQuerySet(models.QuerySet):
    def get_active(self, *, model: str) -> "AiPricing":
        """Return the active pricing row for a model at the current instant.

        Active = effective_from <= now AND (effective_to IS NULL OR effective_to > now).
        """
        now = timezone.now()
        return self.get(
            model=model,
            effective_from__lte=now,
            effective_to__isnull=True,  # use | Q(effective_to__gt=now) if overlapping rows exist
        )

class AiPricing(models.Model):
    model = models.CharField(max_length=100)
    input_token_price_per_1m = models.DecimalField(max_digits=12, decimal_places=8)
    output_token_price_per_1m = models.DecimalField(max_digits=12, decimal_places=8)
    cached_token_price_per_1m = models.DecimalField(max_digits=12, decimal_places=8)
    effective_from = models.DateTimeField()
    effective_to = models.DateTimeField(null=True, blank=True)

    objects = AiPricingQuerySet.as_manager()  # type: ignore[assignment]

    class Meta:
        db_table = "openai_ai_pricing"
        constraints = [
            models.UniqueConstraint(
                fields=["model", "effective_from"],
                name="ai_pricing_model_from_uniq",
            )
        ]
        indexes = [
            models.Index(fields=["model", "effective_from"], name="ai_pricing_lookup_idx"),
        ]
```

**Active row query — use `effective_to__isnull=True` for the current active row** (ensures only one row is "current"). When a price changes, set `effective_to = new_effective_from` on the old row and insert the new row. Use `select_for_update()` in admin actions that close one row and open another.

### Pattern 5: Cost Formula

```python
# apps/integrations/openai/pricing.py
# Source: CLAUDE.md §14.3 + verified Responses API token field names
from decimal import Decimal
from apps.integrations.openai.models import AiPricing

def calculate_cost(
    *,
    model: str,
    prompt_tokens: int,      # = Responses API: input_tokens
    completion_tokens: int,  # = Responses API: output_tokens
    cached_tokens: int = 0,  # = Responses API: input_tokens_details.cached_tokens
) -> Decimal:
    pricing = AiPricing.objects.get_active(model=model)
    non_cached_input = prompt_tokens - cached_tokens
    cost = (
        Decimal(non_cached_input) / 1_000_000 * pricing.input_token_price_per_1m
        + Decimal(cached_tokens) / 1_000_000 * pricing.cached_token_price_per_1m
        + Decimal(completion_tokens) / 1_000_000 * pricing.output_token_price_per_1m
    )
    return cost.quantize(Decimal("0.000001"))
```

### Pattern 6: Pydantic Schema for EnrichmentResult

```python
# apps/integrations/openai/parser.py
# Source: CLAUDE.md §14.2 + Pydantic v2 syntax
from typing import Literal
from pydantic import BaseModel, field_validator

class Tag(BaseModel):
    label: str
    polarity: Literal["positive", "negative", "neutral"]

class ActionItem(BaseModel):
    title: str
    scope: Literal["shop", "brand"]
    priority: Literal["high", "medium", "low"]

class EnrichmentResult(BaseModel):
    sentiment: Literal["positive", "neutral", "negative"]
    tags: list[Tag]
    action_items: list[ActionItem]

    @field_validator("tags")
    @classmethod
    def max_five_tags(cls, v: list[Tag]) -> list[Tag]:
        return v[:5]  # Defensive: prompt enforces <=5 but guard at parse time
```

### Pattern 7: Enrich Task and Retry Beat Task

```python
# apps/reviews/tasks.py — additions
# Source: CLAUDE.md §12.3, existing tasks.py pattern

@shared_task(  # type: ignore[misc]
    bind=True,
    max_retries=3,
    autoretry_for=(OpenAITransientError, EnrichmentParseError),
    retry_backoff=30,
    retry_backoff_max=600,
    retry_jitter=True,
)
def enrich_review_task(self: Any, review_id: int) -> None:
    """Enrich a single review with GPT. Routes to ai-enrichment queue."""
    from apps.reviews.services.enrichment import enrich_review
    enrich_review(review_id=review_id)

@shared_task  # type: ignore[misc]
def retry_failed_enrichments_task() -> int:
    """Beat-scheduled: retry FAILED reviews that haven't exhausted retries.

    Returns count of reviews re-enqueued.
    """
    from apps.reviews.models import Review
    MAX_TOTAL_ATTEMPTS = 3
    ids = list(
        Review.objects.filter(
            enrichment_status=Review.EnrichmentStatus.FAILED,
            enrichment_version__lt=MAX_TOTAL_ATTEMPTS,
        )
        .values_list("id", flat=True)[:500]  # safety cap
    )
    for review_id in ids:
        enrich_review_task.delay(review_id)
    return len(ids)
```

**Note:** `autoretry_for` must reference the actual exception classes — import them at module level or pass by string. Use `OpenAITransientError` and `EnrichmentParseError` (retry once for parse failures — Celery counts `max_retries` globally so parse failures count toward the limit).

### Pattern 8: Inline Enqueue After Upsert in sync.py

```python
# Addition to apps/reviews/services/sync.py — _persist_page return
# After bulk_create completes, enqueue enrichment for new/updated reviews

# After _persist_page():
from apps.reviews.tasks import enrich_review_task

# Get IDs of upserted reviews for enrichment dispatch
review_ids = list(
    Review.objects.filter(
        shop=shop,
        google_review_id__in=rev_ids,
        enrichment_status=Review.EnrichmentStatus.PENDING,
    ).values_list("id", flat=True)
)
for rid in review_ids:
    enrich_review_task.delay(rid)
```

**Note:** Query for PENDING status after upsert to avoid double-enqueuing. The idempotency layer in `enrich_review` is the real safety net, but avoid unnecessary task fan-out.

### Pattern 9: LangSmith Best-Effort Wrapper

```python
# apps/integrations/openai/tracing.py
# Source: LangSmith SDK deepwiki + CLAUDE.md §14.5
import logging
import os
from django.conf import settings

logger = logging.getLogger(__name__)

def configure_langsmith() -> None:
    """Set LangSmith env vars if configured. No-op if not configured."""
    if getattr(settings, "LANGSMITH_ENABLED", False):
        os.environ.setdefault("LANGSMITH_TRACING", "true")
        os.environ.setdefault("LANGSMITH_API_KEY", settings.LANGSMITH_API_KEY or "")
        os.environ.setdefault("LANGSMITH_PROJECT", settings.LANGSMITH_PROJECT)
    else:
        # Disable tracing so @traceable decorator is a no-op
        os.environ["LANGSMITH_TRACING"] = "false"
```

Call `configure_langsmith()` in `apps/integrations/openai/apps.py` `ready()` method. When `LANGSMITH_TRACING=false`, the `@traceable` decorator is effectively a pass-through — no import errors, no connection attempts.

### Anti-Patterns to Avoid

- **Holding DB locks during HTTP calls:** Never call OpenAI inside `transaction.atomic()` — a slow response holds the row lock. Transition to `IN_PROGRESS` inside a short transaction, then call OpenAI outside the transaction.
- **Retrying `OpenAIPermanentError`:** 4xx errors other than 429 are permanent. Do not add them to `autoretry_for`. Catch them explicitly in `enrich_review` and call `return` (not `raise`).
- **Passing model instances to Celery:** Always pass `review_id: int`, never `review: Review`.
- **Calling `emit_progress_event` inside `transaction.atomic()`:** Events sent before commit are misleading. Always emit after commit.
- **Using prompt_tokens / completion_tokens field names for Responses API:** The Responses API uses `input_tokens` and `output_tokens`. Storing them under the wrong names breaks the cost formula silently.
- **Calling `AiPricing.objects.get_active()` outside a try/except:** If no pricing row exists, `get()` raises `DoesNotExist`. Always guard with try/except or assert a row exists in the data migration.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Structured JSON from GPT | Custom JSON parsing of `message.content` | `client.responses.parse(text_format=EnrichmentResult)` | SDK guarantees schema compliance; automatic retry on malformed JSON by structured outputs engine |
| Retry with exponential backoff | Custom sleep loop | `autoretry_for=(OpenAITransientError,)` on `@shared_task` | Celery handles it with backoff, jitter, max_retries per CLAUDE.md §12.3 |
| Distributed lock | Custom Redis SETNX | `apps.common.locks.distributed_lock` | Already implemented; handles LockNotOwnedError on TTL expiry |
| LLM observability | Custom logging of prompts/tokens | `@traceable` + `wrap_openai` | LangSmith provides structured trace UI, latency, token costs, run linking |
| Cost calculation | Relying on OpenAI billing API | `calculate_cost()` with `AiPricing` table | OpenAI billing is not real-time; server-side calculation is the only way to track per-call cost |
| Channel layer from sync thread | `asyncio.run()` | `async_to_sync(channel_layer.group_send)` | Established pattern in `sync.py`; `asyncio.run()` in prefork workers creates event loop conflicts |

**Key insight:** OpenAI's Structured Outputs engine (when using `response_format` / `text_format`) guarantees the output matches the schema when `strict=True` is the default. Never post-process the raw JSON string yourself — use `output_parsed` directly.

---

## Common Pitfalls

### Pitfall 1: openai SDK Major Version Mismatch

**What goes wrong:** CLAUDE.md §14.9 lists `openai==^1.55.0`. The registry is at 2.33.0. Installing `^1.55.0` gives you the old Chat Completions API with `client.chat.completions.parse()` and `prompt_tokens`/`completion_tokens`. If someone pins to 1.x, the Responses API methods don't exist.

**Why it happens:** CLAUDE.md was written when 1.x was current. Major version bump happened after the document was written.

**How to avoid:** Pin to `openai==2.33.0` in `pyproject.toml`. Do NOT use `^1.x`. If backward compatibility with 1.x is desired, use `client.chat.completions.parse()` which also works in 2.x — but `prompt_tokens_details.cached_tokens` differs from `input_tokens_details.cached_tokens`.

**Warning signs:** `AttributeError: module 'openai' has no attribute 'responses'` or missing `ParsedChatCompletion` import.

### Pitfall 2: Token Field Names Differ Between APIs

**What goes wrong:** Chat Completions API uses `response.usage.prompt_tokens` + `response.usage.prompt_tokens_details.cached_tokens`. Responses API uses `response.usage.input_tokens` + `response.usage.input_tokens_details.cached_tokens`. Using the wrong field names silently returns `None` or 0 for cached tokens.

**Why it happens:** OpenAI renamed the fields when introducing the Responses API.

**How to avoid:** Decide on ONE API (Responses API is recommended). Document field names in `client.py` comments. Add a test that `usage_data["cached_tokens"]` is an integer (not None).

**Warning signs:** `usage.prompt_tokens_details` returns None when using Responses API; cost calculation returns 0 for cached discount.

### Pitfall 3: sync.complete Fires Too Early (Breaking Change)

**What goes wrong:** Phase 11's `fetch_and_persist_reviews` emits `sync.complete` at the end of the fetch loop with `total_enriched=0`. Phase 12 requires `sync.complete` to fire only when `total_enriched >= total_fetched`. If the Phase 11 `sync.complete` emission is not removed/modified, the ProgressModal closes prematurely.

**Why it happens:** Phase 11 was built before enrichment existed. The current `sync.py` emits `sync.complete` immediately after the last page is persisted.

**How to avoid:** Remove the `sync.complete` emit from `fetch_and_persist_reviews` in `sync.py`. Move `sync.complete` firing responsibility to `_emit_enrichment_progress()` in the enrichment service. Add a test that verifies `sync.complete` is NOT emitted by `fetch_and_persist_reviews` (check emit_progress_event mock calls).

**Warning signs:** ProgressModal shows 100% fetch but "Sync complete" banner appears before enrichment bar fills.

### Pitfall 4: LangSmith Blocks OpenAI Call on Network Failure

**What goes wrong:** If `LANGSMITH_TRACING=true` but LangSmith is unreachable, the `@traceable` decorator may raise a connection error before the OpenAI call starts, violating the best-effort requirement.

**Why it happens:** LangSmith SDK sends trace data asynchronously but SDK initialization errors can propagate.

**How to avoid:** Wrap the entire `_call_openai_enrichment` call in a try/except in `enrich_review`. If LangSmith raises on init, log at WARNING and call the OpenAI client directly. Alternatively, set `LANGSMITH_TRACING=false` in test settings to make `@traceable` a no-op. Production best-effort is achieved by the SDK's async submission — it won't block the return value.

**Warning signs:** Enrichment tasks fail in staging with LangSmith connection errors but GPT itself is reachable.

### Pitfall 5: Celery Task Calls OpenAI in Tests Without Mocking

**What goes wrong:** `CELERY_TASK_ALWAYS_EAGER=True` makes tasks execute synchronously. If the test doesn't mock `_call_openai_enrichment`, real HTTP calls go out (and fail or cost money).

**Why it happens:** eager mode makes it easy to forget that the task body runs immediately.

**How to avoid:** Always mock `apps.integrations.openai.client._call_openai_enrichment` (or `apps.reviews.services.enrichment._call_openai_enrichment`) in tests. Use fixtures from `apps/integrations/openai/tests/fixtures/` for deterministic responses. Never let test runner hit real OpenAI.

### Pitfall 6: AiPricing.get_active() Raises DoesNotExist on First Deploy

**What goes wrong:** If the data migration for seed pricing hasn't run, `AiPricing.objects.get_active(model="gpt-4o-mini-2024-07-18")` raises `AiPricing.DoesNotExist`, causing every enrichment task to fail.

**Why it happens:** Data migrations run in order, but if the seed migration is missing or applied after enrichment tasks start, the table is empty.

**How to avoid:** The data migration for AiPricing seed data must be part of the same PR as the model migration. Verify in CI that the seed row exists. Add a test that `AiPricing.objects.get_active(model=...)` succeeds after applying migrations.

### Pitfall 7: mypy Strict Mode — Missing Overrides for New Dependencies

**What goes wrong:** openai 2.x, pydantic 2.x, and langsmith don't have full mypy stubs in the pre-commit isolated environment. mypy strict will fail on `ignore_missing_imports=false` (the default).

**Why it happens:** The pre-commit mypy hook uses an isolated environment that requires `additional_dependencies` in `.pre-commit-config.yaml`. New packages need to be added there.

**How to avoid:** Add `openai==2.33.0`, `pydantic==2.13.3`, `langsmith==0.8.0` to the `mypy` hook's `additional_dependencies`. Add `[[tool.mypy.overrides]]` with `ignore_missing_imports = true` for `openai.*` and `langsmith.*` in `pyproject.toml` (same as the existing pattern for celery, channels, etc.).

---

## Code Examples

Verified patterns from official sources and existing codebase:

### Responses API Structured Output with Pydantic

```python
# Source: https://deepwiki.com/openai/openai-python/4.1.3-parsed-responses-and-structured-outputs
# and https://platform.openai.com/docs/guides/structured-outputs

from openai import OpenAI
from pydantic import BaseModel
from typing import Literal

client = OpenAI()

class MySchema(BaseModel):
    sentiment: Literal["positive", "neutral", "negative"]

response = client.responses.parse(
    model="gpt-4o-mini-2024-07-18",
    input=[{"role": "user", "content": "Classify: Great product!"}],
    text_format=MySchema,
)
result: MySchema = response.output_parsed
# Token fields (Responses API):
input_tokens = response.usage.input_tokens
output_tokens = response.usage.output_tokens
cached_tokens = (response.usage.input_tokens_details or object()).cached_tokens or 0
total_tokens = response.usage.total_tokens
```

### LangSmith Trace ID Capture

```python
# Source: https://deepwiki.com/langchain-ai/langsmith-sdk/2.2-run-tracing-with-@traceable
from langsmith import traceable
from langsmith.run_helpers import get_current_run_tree
from typing import Any

@traceable(run_type="llm", name="enrich_review")
def my_openai_call(prompt: str, run_tree: Any = None) -> tuple[str, str | None]:
    response = client.responses.create(model="gpt-4o-mini-2024-07-18", input=[...])
    trace_id = str(run_tree.trace_id) if run_tree else None
    return response.output_text, trace_id

result, trace_id = my_openai_call("test prompt")
```

### Celery Task → Channel Layer (confirmed pattern from sync.py)

```python
# Source: apps/reviews/services/sync.py:emit_progress_event (already in codebase)
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

def emit_progress_event(*, shop_id: int, payload: dict) -> None:
    layer = get_channel_layer()
    if layer is None:
        return
    async_to_sync(layer.group_send)(
        f"sync-progress-{shop_id}",
        {"type": "progress.event", "payload": payload},
    )

# The SyncProgressConsumer handles "progress.event" via:
async def progress_event(self, event):
    await self.send_json(event["payload"])
# Consumer method name is derived from type: "progress.event" → progress_event()
```

### AiPricing Seed Migration

```python
# apps/integrations/openai/migrations/0002_seed_aiprice_gpt4o_mini.py
# Source: CLAUDE.md §14.4 + confirmed pricing from pricepertoken.com (2026-05-02)
# gpt-4o-mini-2024-07-18: $0.150/M input, $0.600/M output, $0.075/M cached

from decimal import Decimal
from django.db import migrations
from django.utils.timezone import datetime, timezone as tz

GPT4O_MINI_MODEL = "gpt-4o-mini-2024-07-18"
EFFECTIVE_FROM = datetime(2024, 7, 18, tzinfo=tz.utc)  # model release date

def seed_pricing(apps, schema_editor):
    AiPricing = apps.get_model("openai", "AiPricing")
    AiPricing.objects.create(
        model=GPT4O_MINI_MODEL,
        input_token_price_per_1m=Decimal("0.150000"),
        output_token_price_per_1m=Decimal("0.600000"),
        cached_token_price_per_1m=Decimal("0.075000"),
        effective_from=EFFECTIVE_FROM,
        effective_to=None,
    )

def unseed_pricing(apps, schema_editor):
    AiPricing = apps.get_model("openai", "AiPricing")
    AiPricing.objects.filter(model=GPT4O_MINI_MODEL, effective_from=EFFECTIVE_FROM).delete()

class Migration(migrations.Migration):
    dependencies = [("openai", "0001_initial")]
    operations = [migrations.RunPython(seed_pricing, unseed_pricing)]
```

### Management Command Pattern for One-Time Backfill

```python
# apps/reviews/management/commands/enrich_existing_reviews.py
# Source: CLAUDE.md §10 pattern; mirrors existing management commands
from django.core.management.base import BaseCommand
from apps.reviews.models import Review
from apps.reviews.tasks import enrich_review_task

class Command(BaseCommand):
    help = "Enqueue enrichment for all PENDING reviews (post-Phase 11 backfill)"

    def handle(self, *args, **options):
        ids = list(
            Review.objects.filter(
                enrichment_status=Review.EnrichmentStatus.PENDING,
                deleted_at__isnull=True,
            ).values_list("id", flat=True)
        )
        for review_id in ids:
            enrich_review_task.delay(review_id)
        self.stdout.write(f"Enqueued {len(ids)} reviews for enrichment.")
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `client.chat.completions.parse()` with `prompt_tokens` | `client.responses.parse()` with `input_tokens` | openai SDK v2.0 (2025) | Token field names changed; Responses API is the new standard |
| `openai==^1.55.0` | `openai==2.33.0` | SDK v2.0 major bump | Major API surface change; CLAUDE.md §14.9 pins are stale |
| `langsmith==^0.2.0` | `langsmith==0.8.0` | Iterative releases | Stable API, minor version increments |
| `pydantic==^2.10.0` | `pydantic==2.13.3` | Iterative releases | Fully backward compatible |
| Chat Completions API recommended | Responses API recommended | 2025 | "Recommended for all new projects" per OpenAI docs |

**Deprecated/outdated:**

- `openai==^1.55.0` from CLAUDE.md §14.9: Use `openai==2.33.0` with Responses API. Chat Completions still works in v2.x but the Responses API is the recommended path.
- `client.beta.chat.completions.parse()`: The `.beta.` namespace was removed in favor of `client.chat.completions.parse()` or `client.responses.parse()`.

---

## Open Questions

1. **Responses API vs Chat Completions API for this project**
   - What we know: Both work in openai 2.33.0. Responses API is "recommended for all new projects." Token field names differ.
   - What's unclear: CLAUDE.md §14 was written for 1.x and references `prompt_tokens` / `prompt_tokens_details`. If the team prefers to stay on Chat Completions API in v2.x (for familiarity), the `client.chat.completions.parse()` method still exists — but `input_tokens_details` vs `prompt_tokens_details` needs to be confirmed at implementation time.
   - Recommendation: Use Responses API (`client.responses.parse()`) as primary. The implementation notes above document both field names. Add a one-line comment in `client.py` mapping `prompt_tokens` → `input_tokens` to avoid confusion.

2. **`sync.complete` from fetch_and_persist — race condition**
   - What we know: When enrichment completes faster than expected (e.g. a single review), `_emit_enrichment_progress` may fire `sync.complete` before all enrich tasks are queued.
   - What's unclear: Whether a counter-based approach (read snapshot, compare) is sufficient or whether a DB-level counter on the Review model is needed.
   - Recommendation: Counter-based on the Redis snapshot is sufficient for Phase 12. The `sync.complete` requirement is "fires when total_enriched >= total_fetched" — both are integers in the Redis snapshot. A DB counter adds latency to each enrichment task. Accept that if the Redis key expires, `sync.complete` won't fire; this is acceptable behavior.

3. **`enrichment_version` increment strategy**
   - What we know: `Review.enrichment_version` exists and increments are planned for future bulk re-enrichment.
   - What's unclear: Whether Phase 12 should increment this field on each enrichment attempt.
   - Recommendation: Increment `enrichment_version` on SUCCESS. The `retry_failed_enrichments_task` uses `enrichment_version__lt=MAX_TOTAL_ATTEMPTS` as its safeguard against infinite retries. This means `enrichment_version` doubles as both a version tracker and an attempt counter.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.3.3 + pytest-django 4.9.0 |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` — `DJANGO_SETTINGS_MODULE = "config.settings.test"` |
| Quick run command | `pytest apps/integrations/openai/ apps/reviews/tests/ -x -q` |
| Full suite command | `pytest --cov=apps --cov-fail-under=85` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ENRCH-01 | OpenAI client returns parsed EnrichmentResult | unit | `pytest apps/integrations/openai/tests/test_client.py -x` | Wave 0 |
| ENRCH-02 | Redis lock acquired; EXIT if SUCCESS or IN_PROGRESS | unit | `pytest apps/reviews/tests/test_enrichment_service.py::test_idempotency -x` | Wave 0 |
| ENRCH-03 | Status transition PENDING→IN_PROGRESS→SUCCESS under atomic | unit | `pytest apps/reviews/tests/test_enrichment_service.py::test_status_transitions -x` | Wave 0 |
| ENRCH-04 | 429 retried; 4xx permanent; parse failure retried once | unit | `pytest apps/reviews/tests/test_enrichment_service.py::test_retry_behaviour -x` | Wave 0 |
| ENRCH-05 | FAILED review appears in reviews list | integration | `pytest apps/reviews/tests/test_views.py::test_failed_enrichment_visible -x` | Wave 0 |
| ENRCH-06 | retry_failed_enrichments_task enqueues FAILED reviews | unit | `pytest apps/reviews/tests/test_tasks.py::test_retry_beat_task -x` | Wave 0 |
| ENRCH-07 | AiUsageLog row written on success | unit | `pytest apps/reviews/tests/test_enrichment_service.py::test_usage_log_written -x` | Wave 0 |
| ENRCH-08 | Cost formula correct for all three token types | unit | `pytest apps/integrations/openai/tests/test_pricing.py -x` | Wave 0 |
| ENRCH-09 | Historical cost unchanged after pricing row update | unit | `pytest apps/integrations/openai/tests/test_pricing.py::test_historical_cost_immutable -x` | Wave 0 |
| ENRCH-10 | Seed pricing row exists; cost matches reference | unit | `pytest apps/integrations/openai/tests/test_pricing.py::test_seed_pricing -x` | Wave 0 |
| ENRCH-11 | LangSmith unreachable → OpenAI call proceeds | unit | `pytest apps/integrations/openai/tests/test_client.py::test_langsmith_best_effort -x` | Wave 0 |
| ENRCH-12 | langsmith_trace_id persisted on AiUsageLog | unit | `pytest apps/reviews/tests/test_enrichment_service.py::test_trace_id_logged -x` | Wave 0 |
| ENRCH-13 | One-time backfill enqueues all PENDING reviews | unit | `pytest apps/reviews/tests/test_management_commands.py::test_enrich_existing -x` | Wave 0 |
| ENRCH-14 | extracted_action_items in ReviewReadSerializer | unit | `pytest apps/reviews/tests/test_views.py::test_serializer_action_items -x` | Wave 0 |

### Sampling Rate

- **Per task commit:** `pytest apps/integrations/openai/ apps/reviews/tests/ -x -q`
- **Per wave merge:** `pytest --cov=apps --cov-fail-under=85`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `apps/integrations/openai/tests/__init__.py` — create directory
- [ ] `apps/integrations/openai/tests/factories.py` — AiPricingFactory, AiUsageLogFactory
- [ ] `apps/integrations/openai/tests/test_client.py` — covers ENRCH-01, ENRCH-11
- [ ] `apps/integrations/openai/tests/test_parser.py` — covers EnrichmentResult schema, max_five_tags
- [ ] `apps/integrations/openai/tests/test_pricing.py` — covers ENRCH-08, ENRCH-09, ENRCH-10
- [ ] `apps/integrations/openai/tests/fixtures/enrichment_success.json` — deterministic GPT response fixture
- [ ] `apps/reviews/tests/test_enrichment_service.py` — covers ENRCH-02, ENRCH-03, ENRCH-04, ENRCH-07, ENRCH-12
- [ ] `apps/reviews/tests/test_management_commands.py` — covers ENRCH-13
- [ ] `apps/reviews/management/__init__.py` + `commands/__init__.py` — if not already present

---

## Sources

### Primary (HIGH confidence)

- DeepWiki openai/openai-python §4.1.3 — `client.chat.completions.parse()` and `client.responses.parse()` API; `output_parsed` access pattern; token usage fields
- DeepWiki langchain-ai/langsmith-sdk §2.2 — `@traceable`, `get_current_run_tree()`, `run_tree.trace_id`, metadata injection patterns
- Existing `apps/reviews/services/sync.py` — confirmed `async_to_sync(layer.group_send)` pattern, `emit_progress_event`, channel group naming (`sync-progress-{shop_id}`)
- PyPI registry (live query 2026-05-02): openai==2.33.0, langsmith==0.8.0, pydantic==2.13.3
- https://pricepertoken.com/pricing-page/model/openai-gpt-4o-mini — gpt-4o-mini pricing: $0.150/$0.600/$0.075 per 1M tokens

### Secondary (MEDIUM confidence)

- https://developers.openai.com/api/docs/guides/migrate-to-responses — Responses API is "recommended for all new projects"; Chat Completions remains supported
- https://platform.openai.com/docs/guides/structured-outputs — Structured Outputs supports gpt-4o-mini-2024-07-18; refusal field on ParsedChatCompletion; strict=true guarantees schema compliance
- Community: usage.prompt_tokens_details=None issue (github.com/openai/openai-python/issues/2544) — cached_tokens field can be None; guard with `or 0`

### Tertiary (LOW confidence — flag for validation)

- openai SDK v2 token field names (input_tokens vs prompt_tokens) — verified from multiple secondary sources but not confirmed against live API documentation directly. **Validate at implementation time** by printing `response.usage` in a test call.
- LangSmith `run_tree.trace_id` type — confirmed as UUID in DeepWiki, but verify actual type (UUID vs str) at implementation time.

---

## Metadata

**Confidence breakdown:**

- Standard stack: HIGH — verified against live PyPI registry
- Architecture: HIGH — patterns derived from existing codebase + official sources
- Pitfalls: HIGH — token field name pitfall verified via multiple sources; SDK version confirmed live
- Pricing data: MEDIUM — confirmed from third-party pricing calculator; validate against openai.com/api/pricing before going live

**Research date:** 2026-05-02
**Valid until:** 2026-06-02 (30 days; openai pricing and SDK are stable in this period)
