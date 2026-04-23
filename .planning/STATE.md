---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: unknown
stopped_at: Completed 03-06 tasks 1-3; awaiting human-verify checkpoint (Task 4)
last_updated: "2026-04-23T10:28:10.826Z"
progress:
  total_phases: 5
  completed_phases: 3
  total_plans: 15
  completed_plans: 15
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-22)

**Core value:** Superadmins can provision and manage organisations, allocate store slots, and control Org Admin access — the foundational control plane every subsequent phase depends on.
**Current focus:** Phase 03 — organisation-management

## Current Position

Phase: 03 (organisation-management) — EXECUTING
Plan: 1 of 6

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
| Phase 03-organisation-management P01 | 4 | 2 tasks | 14 files |
| Phase 01-foundation P01 | 10 | 2 tasks | 28 files |
| Phase 01-foundation P03 | 6 | 3 tasks | 20 files |
| Phase 01-foundation P02 | 12 | 3 tasks | 17 files |
| Phase 01-foundation P04 | 6 | 2 tasks | 20 files |
| Phase 01-foundation P05 | 12 | 2 tasks | 21 files |
| Phase 01-foundation P05 | 2 | 3 tasks | 1 files |
| Phase 02-authentication P01 | 8 | 3 tasks | 5 files |
| Phase 02-authentication P02 | 8 | 3 tasks | 15 files |
| Phase 02-authentication P03 | 6 | 3 tasks | 10 files |
| Phase 03-organisation-management P02 | 9 | 2 tasks | 12 files |
| Phase 03-organisation-management P03 | 9 | 2 tasks | 12 files |
| Phase 03-organisation-management P04 | 14m | 2 tasks | 12 files |
| Phase 03-organisation-management P05 | 26m | 2 tasks | 7 files |
| Phase 01-foundation P06 | 5 | 2 tasks | 4 files |
| Phase 03-organisation-management P06 | 3m | 3 tasks | 6 files |

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
- [Phase 02-authentication]: LoginRateThrottle overrides parse_rate: DRF parse_rate uses period[0] which breaks '10/15min'; override handles multi-unit periods via regex
- [Phase 02-authentication]: test.py CACHES throttle alias uses locmem.LocMemCache to keep tests fast and independent of Redis
- [Phase 02-authentication]: Email field inlined in login.html (not via form_fields component) because UI-SPEC requires right-aligned Forgot password? in label row — component lacks extra_attrs support
- [Phase 02-authentication]: organisations placeholder view added before Django admin in URL order so /admin/organisations/ redirects to /login/ (not /admin/login/) per AUTH-05 test requirements
- [Phase 02-authentication]: conftest autouse fixture clears throttle LocMemCache before each test — prevents rate-limit state bleed between test_login_rate_limit and subsequent tests
- [Phase 02-authentication]: CustomPasswordResetConfirmView.form_valid adds flash AFTER super().form_valid — token invalidated first, then message queued
- [Phase 02-authentication]: Flash message is EXACTLY 'Password updated. Please sign in.' per CONTEXT.md locked copy
- [Phase 02-authentication]: Hand-inlined CSS in password_reset.html email — premailer integration deferred to Phase 4
- [Phase 02-authentication]: test_password_reset_expired mocks default_token_generator._now() +1s — Django documents _now() as designed for mocking
- [Phase 03-organisation-management 01-01]: dict[str, object] used for email context parameter to satisfy mypy strict mode
- [Phase 03-organisation-management 01-01]: xfail(strict=False) for Wave 0 scaffolds so CI stays green; downstream plans remove markers when implementing
- [Phase 03-organisation-management 01-01]: Test fixture templates _test.html/_test.txt use underscore prefix to indicate test-only artifacts
- [Phase 03-organisation-management]: json_script receives Python list (not JSON string) to avoid double-encoding in template
- [Phase 03-organisation-management]: pagination.html uses has_previous/has_next guards instead of |default filter to prevent EmptyPage exceptions
- [Phase 03-organisation-management]: org-table-root div placed outside the empty/non-empty conditional so React mount point is always present
- [Phase 03-organisation-management]: SimpleRouter used (not DefaultRouter): avoids DRF api-root at '/' conflicting with Django home view
- [Phase 03-organisation-management]: json_script tag: pass Python list not JSON string to avoid double-encoding in organisation list template
- [Phase 03-organisation-management]: EditOrgModal uses const currentOrg = org after early null-return guard to satisfy TypeScript strict null checks inside async submit closure
- [Phase 03-organisation-management]: CreateOrgModal test uses form.dispatchEvent(submit) because jsdom does not support HTML form= cross-element association
- [Phase 03-organisation-management]: Actions column in OrgTable satisfied by DataTable auto-emitted th aria-label=Actions when renderRowActions is provided — no explicit DataTableColumn added
- [Phase 03-organisation-management]: Store allocation upper cap at 1000 to match CreateOrgModal client-side validation
- [Phase 03-organisation-management]: DeleteConfirmModal uses null-guard return to force ConfirmModal remount, resetting typed state on each open
- [Phase 03-organisation-management]: StoreAllocationModal captures currentOrg const post null-guard for TypeScript strict null safety in async closure
- [Phase 01-foundation]: Alpine sidebar must read $store.nav.mobileOpen live — never copy store value into local x-data at mount time
- [Phase 01-foundation]: vite_react_refresh must appear immediately after vite_hmr_client in head.html for @vitejs/plugin-react dev mode
- [Phase 01-foundation]: block extra_js placed after </main> so script injection bypasses DOM ordering constraints; showcase vite_asset moved there from block content
- [Phase 03-organisation-management]: React 18 StrictMode + inline handler prop to a useEffect listener registrar causes click listener to be absent at click time — stabilise with useCallback([])
- [Phase 03-organisation-management]: Tailwind overflow-hidden on a wrapper breaks child position:sticky — prefer overflow-x-auto on the scroll container only
- [Phase 03-organisation-management]: Mount-point divs for React widgets must live inside the conditional that guards their data, otherwise the widget visually overrides server-rendered empty states

### Pending Todos

None yet.

### Blockers/Concerns

- Phase 1: User model (AUTH_USER_MODEL) must be set and migrated before any other app references it. Do not create Organisation or InvitationToken migrations until accounts/0001 exists.

## Session Continuity

Last session: 2026-04-23T10:28:10.824Z
Stopped at: Completed 03-06 tasks 1-3; awaiting human-verify checkpoint (Task 4)
Resume file: None
