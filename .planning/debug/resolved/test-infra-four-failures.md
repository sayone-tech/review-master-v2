---
status: resolved
trigger: "Four pre-existing test failures in Phase 11/12 test infrastructure"
created: 2026-05-03T00:00:00Z
updated: 2026-05-03T00:00:00Z
---

## Current Focus

hypothesis: single root cause — wrong settings module loaded
test: ran the four failing tests after adding --ds=config.settings.test to pytest addopts
expecting: all four pass
next_action: completed — full suite green

## Symptoms

(see top of file — symptoms_prefilled)

## Eliminated

- hypothesis: tests need individual fixes (separate bugs)
  evidence: a single change to pytest addopts fixed all four
  timestamp: investigation

## Evidence

- timestamp: 1
  checked: config/settings/test.py
  found: Already contained CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True, CHANNEL_LAYERS InMemoryChannelLayer, LANGSMITH_ENABLED=False, LANGSMITH_API_KEY=None
  implication: test.py is correct; the file simply isn't being loaded

- timestamp: 2
  checked: pytest header on initial run
  found: "django: version: 6.0.2, settings: config.settings.local (from env)"
  implication: pytest-django was using the env var DJANGO_SETTINGS_MODULE=config.settings.local from docker-compose, NOT the pyproject.toml ini option

- timestamp: 3
  checked: pytest-django plugin source (priority order)
  found: --ds option > DJANGO_SETTINGS_MODULE env var > ini option (DJANGO_SETTINGS_MODULE in pyproject.toml)
  implication: env var silently overrides pyproject.toml; need a way to win over env

- timestamp: 4
  checked: ran full failing-test set after adding --ds=config.settings.test to addopts
  found: all 4 pass; header now reads "settings: config.settings.test (from option)"
  implication: confirmed root cause — wrong settings module

- timestamp: 5
  checked: full pytest suite after fix
  found: 623 passed, 0 failures
  implication: no regressions

## Resolution

root_cause: |
  pytest-django resolves DJANGO_SETTINGS_MODULE in this priority order:
    1. --ds CLI option
    2. DJANGO_SETTINGS_MODULE env var
    3. pyproject.toml [tool.pytest.ini_options] DJANGO_SETTINGS_MODULE
  The docker-compose web container sets DJANGO_SETTINGS_MODULE=config.settings.local
  for the web server, and pytest inherits that env var. So the test runner was
  loading config.settings.local instead of config.settings.test, which meant:
    - FAIL 3: CELERY_TASK_ALWAYS_EAGER not defined in local.py -> AttributeError
    - FAIL 4: CHANNEL_LAYERS in local.py uses RedisChannelLayer
    - FAIL 1: LANGSMITH_ENABLED was True (LANGSMITH_API_KEY present from .env), so
              the @traceable wrapper actually traced and returned a real trace_id
    - FAIL 2: The test patches channels.layers.InMemoryChannelLayer.group_discard,
              but the runtime layer was channels_redis.core.RedisChannelLayer, so
              the patch never intercepted any call -> await_count == 0
  All four failures share this single root cause.

fix: |
  Added `--ds=config.settings.test` to pytest addopts in pyproject.toml. The --ds
  CLI option has the highest priority in pytest-django's settings resolution and
  guarantees the test settings module is loaded regardless of the surrounding
  environment.

verification: |
  - The four originally failing tests now all pass.
  - Full pytest suite: 623 passed, 0 failures, 0 errors.
  - pytest header confirms: "settings: config.settings.test (from option)".

files_changed:
  - pyproject.toml
