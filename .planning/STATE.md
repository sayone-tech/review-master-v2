---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: unknown
stopped_at: Phase 2 UI-SPEC approved
last_updated: "2026-04-22T16:32:19.655Z"
progress:
  total_phases: 5
  completed_phases: 1
  total_plans: 5
  completed_plans: 5
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-22)

**Core value:** Superadmins can provision and manage organisations, allocate store slots, and control Org Admin access — the foundational control plane every subsequent phase depends on.
**Current focus:** Phase 01 — foundation

## Current Position

Phase: 01 (foundation) — EXECUTING
Plan: 4 of 5

## Performance Metrics

**Velocity:**

- Total plans completed: 1
- Average duration: ~10 min
- Total execution time: 0.17 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| - | - | - | - |

**Recent Trend:**

- Last 5 plans: none yet
- Trend: -

*Updated after each plan completion*
| Phase 01-foundation P01 | 10 | 2 tasks | 28 files |
| Phase 01-foundation P03 | 6 | 3 tasks | 20 files |
| Phase 01-foundation P02 | 12 | 3 tasks | 17 files |
| Phase 01-foundation P04 | 6 | 2 tasks | 20 files |
| Phase 01-foundation P05 | 12 | 2 tasks | 21 files |
| Phase 01-foundation P05 | 2 | 3 tasks | 1 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- Init: Django templates + Tailwind for shell; React only for complex interactive widgets
- Init: Amazon SES via django-ses for all transactional email
- Init: Django session auth (not JWT) for Phase 1
- Init: Soft-delete for organisations; permanent purge deferred to a future scheduled job
- Init: Invitation tokens via TimestampSigner — 48-hour expiry, single-use enforced
- 01-01: django-upgrade target 5.1 (6.0 not yet supported by django-upgrade 1.22.2)
- 01-01: django-stubs django_settings_module set to config.settings.test (accounts app not yet created)
- 01-01: test.py overrides AUTH_USER_MODEL=auth.User until Plan 02 creates custom User
- [Phase 01-foundation]: django-upgrade target 5.1 (not 6.0): django-upgrade 1.22.2 does not support 6.0 as a target-version argument
- [Phase 01-foundation]: mypy django_settings_module uses config.settings.test so pre-commit hook works before apps.accounts exists
- [Phase 01-foundation]: test.py uses AUTH_USER_MODEL=auth.User temporarily; will be changed when Plan 02 creates custom User model
- [Phase 01-foundation]: 01-03: Tailwind v4 @tailwindcss/vite plugin used over PostCSS — v4 ships its own Vite plugin
- [Phase 01-foundation]: 01-03: DJANGO_VITE dev_mode=True in config/settings/test.py to avoid needing a Vite build during pytest
- [Phase 01-foundation]: 01-03: Alpine.js bundled via Vite entry (no CDN) to prevent double-init issues
- [Phase 01-foundation]: User.organisation FK deferred to accounts/0002 migration to break circular dependency with organisations/0001
- [Phase 01-foundation]: annotate_store_counts() is Phase 1 stub returning zeros until Phase 2 adds Store model
- [Phase 01-foundation]: InvitationToken uses SHA-256 (hashlib) for token hashing; token_hash stored in DB as 64-char hex digest
- [Phase 01-foundation]: 01-04: User.full_name used in sidebar/topbar templates (not first_name/last_name — matches Plan 01-02 model)
- [Phase 01-foundation]: 01-04: logout_stub registered as name='logout' in Phase 1; Phase 2 swaps view body, URL name is stable
- [Phase 01-foundation]: 01-04: Alpine.store('nav') for mobile drawer; app:toast CustomEvent schema { kind, title, msg }
- [Phase 01-foundation]: 01-05: focus-trap-react fallbackFocus=document.body required for jsdom compatibility in vitest tests
- [Phase 01-foundation]: 01-05: vitest.config.ts uses esbuild JSX transform (not @vitejs/plugin-react) due to vite version mismatch
- [Phase 01-foundation]: 01-05: base.html restructured with shell_open/shell_close split to fix Django block inheritance through include tags

### Pending Todos

None yet.

### Blockers/Concerns

- Phase 1: User model (AUTH_USER_MODEL) must be set and migrated before any other app references it. Do not create Organisation or InvitationToken migrations until accounts/0001 exists.

## Session Continuity

Last session: 2026-04-22T16:32:19.649Z
Stopped at: Phase 2 UI-SPEC approved
Resume file: .planning/phases/02-authentication/02-UI-SPEC.md
