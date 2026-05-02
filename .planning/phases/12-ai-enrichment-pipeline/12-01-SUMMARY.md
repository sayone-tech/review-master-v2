---
phase: 12-ai-enrichment-pipeline
plan: "01"
subsystem: ai-enrichment
tags: [dependencies, model, migration, serializer, frontend-types, openai, langsmith, pydantic]
dependency_graph:
  requires: []
  provides:
    - openai==2.33.0 installed and lockfile updated
    - langsmith==0.8.0 installed and lockfile updated
    - pydantic==2.13.3 installed and lockfile updated
    - OPENAI_API_KEY, OPENAI_MODEL, OPENAI_MAX_RETRIES, LANGSMITH_* settings in base.py
    - LangSmith tracing forced off in test settings
    - Review.extracted_action_items JSONField with default=list
    - Migration 0004_review_extracted_action_items.py
    - ReviewReadSerializer surfaces extracted_action_items
    - ReviewFactory has extracted_action_items default
    - Frontend ExtractedActionItem type + ReviewRow.extracted_action_items
  affects:
    - Plans 12-02 through 12-08 (all depend on these foundations)
tech_stack:
  added:
    - openai==2.33.0 (OpenAI Python SDK)
    - langsmith==0.8.0 (LangSmith tracing SDK)
    - pydantic==2.13.3 (structured output parsing)
  patterns:
    - mypy ignore_missing_imports overrides for openai.* and langsmith.* stubs
    - ClassVar[list] annotation on factory attributes (RUF012 compliance)
    - os.environ set before from .base import * to disable LangSmith before any import
key_files:
  created:
    - apps/reviews/migrations/0004_review_extracted_action_items.py
  modified:
    - pyproject.toml (dependencies + mypy overrides)
    - uv.lock (new dependency pins)
    - .pre-commit-config.yaml (mypy hook additional_dependencies)
    - config/settings/base.py (OpenAI/LangSmith settings block)
    - config/settings/test.py (LangSmith disabled, LANGSMITH_ENABLED=False)
    - apps/reviews/models.py (extracted_action_items field)
    - apps/reviews/serializers.py (extracted_action_items in ReviewReadSerializer)
    - apps/reviews/tests/factories.py (explicit defaults, ClassVar[list])
    - frontend/src/widgets/review-management/types.ts (ExtractedActionItem interface, ReviewRow update)
decisions:
  - Exact version pins used (openai==2.33.0 not ^1.55.0) — RESEARCH.md verified live PyPI 2026-05-02; CLAUDE.md §14.9 was stale with older ranges
  - LangSmith forced off in test settings via os.environ before from .base import * — ruff isort moves import os to top which is actually safer (env set even earlier before any module init)
  - JSONField used over Postgres ArrayField for extracted_action_items — cross-DB safe for SQLite test runner; stores list-of-dicts natively as jsonb on Postgres
  - ClassVar[list] = [] annotation on factory attributes — fixes RUF012 mutable class attribute lint error
  - mypy overrides for openai.* and langsmith.* added since those packages ship no full mypy stubs
metrics:
  duration_minutes: 5
  completed_date: "2026-05-02"
  tasks_completed: 2
  files_modified: 9
---

# Phase 12 Plan 01: Foundation — Dependencies, Settings, and Model Field Summary

**One-liner:** Phase 12 bootstrap — pin openai==2.33.0/langsmith==0.8.0/pydantic==2.13.3, configure AI settings, add Review.extracted_action_items JSONField with migration and frontend types.

## What Was Built

This plan establishes the prerequisite infrastructure for the entire AI enrichment pipeline. Every subsequent Phase 12 plan assumes these foundations are in place.

### 1. Dependency Installation

Three new libraries added to `pyproject.toml` in alphabetical order:
- `openai==2.33.0` — uses the Responses API (not available in ^1.55.0 from CLAUDE.md §14.9)
- `langsmith==0.8.0` — tracing SDK (^0.2.0 in CLAUDE.md was stale)
- `pydantic==2.13.3` — structured output parsing

`uv lock` updated the lockfile. Additional packages resolved: orjson, pydantic-core, requests-toolbelt, sniffio, tqdm, typing-inspection, uuid-utils, xxhash, zstandard.

**Why exact pins, not ranges:** RESEARCH.md verified live PyPI on 2026-05-02. The CLAUDE.md §14.9 versions (`^1.55.0`, `^0.2.0`) are stale — the Responses API in openai==2.33.0 is incompatible with the older client interface. Exact pins prevent silent API breakage from minor version bumps.

### 2. mypy Stubs

Neither `openai` nor `langsmith` ship complete mypy stubs. Added `[[tool.mypy.overrides]]` block in `pyproject.toml`:
```toml
[[tool.mypy.overrides]]
module = ["openai.*", "langsmith.*", "langsmith.run_helpers"]
ignore_missing_imports = true
```

Both packages also added to `.pre-commit-config.yaml` mypy hook `additional_dependencies` so the isolated pre-commit environment can install them alongside the existing celery/channels/etc. entries.

### 3. OpenAI / LangSmith Settings

Added to `config/settings/base.py` after the `CHANNEL_LAYERS` block:
- `OPENAI_API_KEY` — required at runtime, default `""` for local dev
- `OPENAI_MODEL` — default `"gpt-4o-mini-2024-07-18"`
- `OPENAI_MAX_RETRIES` — default `3`
- `LANGSMITH_API_KEY` — optional, default `None`
- `LANGSMITH_PROJECT` — default `f"review-platform-{ENVIRONMENT}"`
- `LANGSMITH_ENABLED` — derived `bool(LANGSMITH_API_KEY)`
- `INITIAL_SYNC_PAGE_SIZE` — default `50`
- `ENRICHMENT_BATCH_SIZE` — default `10`
- `INCREMENTAL_SYNC_INTERVAL_HOURS` — default `6`
- `INCREMENTAL_SYNC_JITTER_MINUTES` — default `30`

### 4. LangSmith Disabled in Tests

`config/settings/test.py` sets `os.environ["LANGSMITH_TRACING"] = "false"` before `from .base import *` (ruff isort moves the import to the top, which is actually safer — env var set before any module initialisation). This ensures `@traceable` is a pass-through in tests and no network calls are made.

**Why this matters (RESEARCH.md Pitfall 4):** LangSmith SDK may attempt an async submission on import if `LANGSMITH_TRACING` is not disabled. Setting the env var at module level before any langsmith import is the authoritative pattern.

### 5. Review.extracted_action_items Field

Added to `Review` model after the `tags` field:
```python
extracted_action_items = models.JSONField(default=list, blank=True)
```

Migration `0004_review_extracted_action_items.py` uses `migrations.AddField` — cross-DB safe JSONField (no Postgres-specific ArrayField), automatically reversible, existing rows default to `[]`.

**Why JSONField over Postgres ArrayField:** The test runner uses SQLite in-memory. JSONField works on both; ArrayField requires Postgres. The storage shape is a list-of-dicts `[{title, scope, priority}]` which maps naturally to jsonb on Postgres.

### 6. Serializer Update

`ReviewReadSerializer.Meta.fields` now includes `"extracted_action_items"` immediately after `"tags"`. The existing `read_only_fields = fields` pattern covers it automatically — no additional annotation needed.

### 7. Frontend Types

`frontend/src/widgets/review-management/types.ts` now exports:
```typescript
export type ActionItemScope = "shop" | "brand";
export type ActionItemPriority = "high" | "medium" | "low";

export interface ExtractedActionItem {
  title: string;
  scope: ActionItemScope;
  priority: ActionItemPriority;
}
```

And `ReviewRow` includes:
```typescript
extracted_action_items: ExtractedActionItem[];
```

This shape mirrors the Pydantic `ActionItem` schema that Plan 02 will define in `apps/integrations/openai/parser.py`.

### 8. ReviewFactory Defaults

`ReviewFactory` now has explicit defaults:
```python
tags: ClassVar[list] = []
extracted_action_items: ClassVar[list] = []
```

`ClassVar` annotation required by ruff `RUF012` (mutable class attribute warning). Both fields remain overridable per-test.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] RUF012: Mutable class attribute in ReviewFactory**
- **Found during:** Task 2 (pre-commit hook on commit attempt)
- **Issue:** `tags: list = []` and `extracted_action_items: list = []` triggered ruff RUF012 — mutable default values for class attributes
- **Fix:** Added `from typing import ClassVar` import and annotated both attributes as `ClassVar[list]`
- **Files modified:** `apps/reviews/tests/factories.py`
- **Commit:** b8a9694 (included in Task 2 commit after fix)

**2. [Rule 1 - Auto-fix] ruff isort moved `import os` before `from .base import *` in test.py**
- **Found during:** Task 1 (ruff-check auto-fix on pre-commit)
- **Issue:** Plan specified `import os  # noqa: E402` placement after the `from .base import *` line, but ruff isort correctly moves stdlib imports to top
- **Fix:** Accepted ruff's reordering — the env vars are set before `from .base import *` which is actually safer (env set before any module init from base)
- **Files modified:** `config/settings/test.py`
- **Impact:** No functional change; `LANGSMITH_ENABLED = False` and `LANGSMITH_API_KEY = None` still override base.py values correctly

## Self-Check

**Files created/exist:**
- `apps/reviews/migrations/0004_review_extracted_action_items.py` — exists
- `config/settings/base.py` — OPENAI_API_KEY present
- `config/settings/test.py` — LANGSMITH_TRACING=false present

**Commits:**
- `c16c5a8` — chore(12-01): dependencies + settings
- `b8a9694` — feat(12-01): model field + migration + serializer + factory + frontend type

**Tests:** 69 passed (all reviews tests)
**TypeScript:** npx tsc --noEmit exits 0
**Migrations:** makemigrations --check reports "No changes detected"
