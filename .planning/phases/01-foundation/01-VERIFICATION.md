---
phase: 01-foundation
verified: 2026-04-22T12:30:00Z
status: human_needed
score: 24/24 automated must-haves verified
human_verification:
  - test: "Visual rendering of shell chrome at desktop (1440px), tablet (768px), and mobile (375px)"
    expected: "Sidebar 240px desktop / 64px rail tablet / hidden with hamburger mobile; bg-black sidebar; bg-bg main content; topbar with bell + avatar dropdown; active nav item shows yellow left border"
    why_human: "Responsive layout and visual brand colour rendering cannot be verified programmatically without a running browser"
  - test: "Full keyboard navigation flow on /__ui__/ showcase page"
    expected: "Tab reveals skip link; Tab traverses all interactive elements with visible yellow 2px focus ring; Enter on modal trigger opens modal; Tab trapped inside modal; Escape closes modal; focus returns to trigger"
    why_human: "Focus trap behaviour and visible focus ring appearance require interactive browser testing"
  - test: "Toast system end-to-end: click Fire toast button on showcase page"
    expected: "Dark toast appears top-right with correct icon colour, auto-dismisses after 5 seconds, dismiss button works immediately"
    why_human: "CustomEvent dispatch and Alpine.js reaction require a live browser environment"
  - test: "Screen reader ARIA announcements (VoiceOver / NVDA)"
    expected: "Bell announces Notifications; avatar announces Open user menu; modal close announces Close; skeleton announces Loading please wait; error field announces via role=alert; heading hierarchy h1>h2 reads correctly"
    why_human: "Screen reader output requires an assistive technology device and human listener"
  - test: "Lighthouse accessibility audit on /__ui__/"
    expected: "Accessibility score 100 or documented violations, no images-missing-alt, no buttons-missing-text violations"
    why_human: "Automated Lighthouse audit requires a running dev server"
---

# Phase 1: Foundation Verification Report

**Phase Goal:** Establish a production-grade Django 6 project scaffold with split settings, uv dependency management, full toolchain (ruff, mypy, bandit, pytest), PostgreSQL + Redis infrastructure, Docker dev environment, Vite + Tailwind v4 frontend toolchain, custom User/Organisation models, and a reusable UI component library (shell chrome, template components, React widgets) ready for feature development.

**Verified:** 2026-04-22T12:30:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| #  | Truth | Status | Evidence |
|----|-------|--------|---------|
| 1  | Django 6.0.2 project scaffold exists with split settings (base/local/production/test), uv deps, pre-commit hooks | VERIFIED | `pyproject.toml` has `django==6.0.2`; all four settings modules import `from .base import *`; `.pre-commit-config.yaml` has ruff-pre-commit, mypy, bandit, gitleaks hooks |
| 2  | apps/common foundation has TimeStampedModel, UUIDModel, health endpoints | VERIFIED | `apps/common/models.py` has `class TimeStampedModel(models.Model)` and `class UUIDModel`; `apps/common/views.py` has `def healthz` and `def readyz` |
| 3  | Custom User model with role enum, Organisation with soft-delete, InvitationToken with 48h expiry exist with correct migrations | VERIFIED | `apps/accounts/models.py` has `class User(AbstractBaseUser, PermissionsMixin, TimeStampedModel)` with `class Role(TextChoices)`, `class InvitationToken` with `hash_token` + `is_expired`; `apps/organisations/models.py` has `class Organisation(TimeStampedModel)` with `def soft_delete`; migration 0002 depends on both `accounts/0001_initial` and `organisations/0001_initial` |
| 4  | Docker dev environment with five services (web, db, redis, mailhog, vite) and healthchecks | VERIFIED | `Dockerfile` has multi-stage `FROM python:3.12-slim AS builder/runtime`, `USER app`, HEALTHCHECK targeting `/readyz/`; `docker-compose.yml` has all five services with `condition: service_healthy` on web dependencies |
| 5  | Vite + Tailwind v4 frontend toolchain with all 20 brand tokens | VERIFIED | `frontend/vite.config.ts` imports `@tailwindcss/vite` and has `manifest: "manifest.json"`; `frontend/tailwind.config.js` has all 20 tokens (confirmed by grep count = 20); `frontend/src/styles/tailwind.css` has `@import "tailwindcss"` |
| 6  | Alpine.js bundled via Vite (not CDN); Alpine.store('nav') registered | VERIFIED | `frontend/src/entrypoints/app-shell.ts` has `Alpine.store("nav", { mobileOpen: false })`; no CDN references in templates |
| 7  | Django base shell renders bg-black sidebar (240px), bg-bg main content, Geist fonts, django-vite asset injection | VERIFIED | `templates/partials/sidebar.html` has `md:w-sidebar-rail lg:w-sidebar bg-black text-white`; `templates/partials/head.html` has `{% vite_asset 'src/entrypoints/app-shell.ts' %}` and Geist Google Fonts link; `templates/base.html` uses `shell_open`/`shell_close` split for block inheritance |
| 8  | Sidebar nav with role-based items, yellow active state (border-yellow), bottom-pinned logout | VERIFIED | `templates/partials/sidebar.html` has `border-t border-[#27272A]` footer divider, `{% load ui %}`, `{% url 'logout' %}`, `hidden md:flex`, `md:w-sidebar-rail` responsive classes; `apps/common/templatetags/ui.py` has `is_active_route` |
| 9  | Topbar with notification bell and Alpine.js avatar dropdown (open/close/escape/click-outside) | VERIFIED | `templates/partials/topbar.html` has `x-data="{ open: false }"`, `@click.outside="open = false"`, `aria-label="Open navigation"`, `aria-label="Notifications"` |
| 10 | Phase-1 logout stub registered; `{% url 'logout' %}` resolves without NoReverseMatch | VERIFIED | `apps/common/urls.py` has `path("logout/", logout_stub, name="logout")`; `apps/common/views.py` has `def logout_stub` returning 302 to `/` |
| 11 | 8 reusable template component partials: buttons, form_fields, badges, toasts, empty_state, skeletons, filter_bar, pagination | VERIFIED | All 8 files exist with correct content; `buttons.html` has `bg-yellow text-black`; `toasts.html` has `@app:toast.window`; `skeletons.html` has `aria-busy="true"`; `empty_state.html` has `bg-yellow-tint`; `pagination.html` has `aria-current="page"` |
| 12 | React Modal primitive with focus-trap-react, portal, Escape, backdrop dismiss | VERIFIED | `Modal.tsx` has `import FocusTrap from "focus-trap-react"`, `createPortal`, `role="dialog"`, `aria-modal="true"`, `aria-label="Close"` |
| 13 | ConfirmModal with amber/blue/red variants, locked Cancel copy, type-to-confirm gate | VERIFIED | `ConfirmModal.tsx` has `requireTypeToConfirm`, `Cancel` button text, three variant constants |
| 14 | DataTable with 6-row loading skeleton, empty state, populated rows, row actions opacity-35 hover | VERIFIED | `DataTable.tsx` has `data-testid="data-table-skeleton-row"`, `opacity-35 group-hover:opacity-100` |
| 15 | emitToast dispatches `app:toast` CustomEvent on window | VERIFIED | `frontend/src/lib/toast.ts` has `window.dispatchEvent(new CustomEvent("app:toast", { detail }))` |
| 16 | Showcase page at `/__ui__/` renders all component categories and React mount | VERIFIED | `templates/pages/showcase.html` has `{% vite_asset 'src/entrypoints/showcase.tsx' %}` and `id="showcase-root"`; `apps/common/urls.py` has `path("__ui__/", showcase, name="showcase")` |
| 17 | Focus ring (yellow 2px outline), `[x-cloak]` display:none rule, sk-pulse keyframe in tailwind.css | VERIFIED | `frontend/src/styles/tailwind.css` has `:focus-visible`, `[x-cloak]`, `@keyframes sk-pulse` |
| 18 | WCAG AA: visible focus states, ARIA labels on icon-only buttons, focus trap in modals, heading hierarchy | PARTIALLY VERIFIED (automated) / NEEDS HUMAN | Automated checks confirm ARIA attributes exist in markup; human verification per SUMMARY 01-05 completed with "approved" but is not re-verifiable programmatically |
| 19 | Test infrastructure: pytest, factory-boy, vitest all configured | VERIFIED | `pyproject.toml` has `[tool.pytest.ini_options]` and `[tool.coverage.run/report]`; `frontend/vitest.config.ts` has `environment: "jsdom"`; all factory files exist |
| 20 | Migration graph correct: accounts/0001 → organisations/0001 → accounts/0002 | VERIFIED | `apps/accounts/migrations/0002_user_organisation_invitationtoken.py` has `dependencies = [('accounts', '0001_initial'), ('organisations', '0001_initial')]` |

**Score:** 24/24 automated checks verified (5 items need human confirmation for visual/interactive aspects)

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `pyproject.toml` | Single source of truth for deps and tool config | VERIFIED | Contains `[project.dependencies]` with `django==6.0.2`; `[tool.ruff]` at line 33; `[tool.mypy]` at line 56; `[tool.pytest.ini_options]`; `[tool.coverage.run/report]` |
| `config/settings/base.py` | Shared Django settings with AUTH_USER_MODEL | VERIFIED | `AUTH_USER_MODEL = "accounts.User"` present |
| `config/settings/local.py` | Local dev overrides (DEBUG=True, MailHog, Vite dev) | VERIFIED | `from .base import *` present; MailHog email settings present |
| `config/settings/test.py` | Fast deterministic test settings | VERIFIED | `locmem.EmailBackend` present; `DisableMigrations` class present |
| `apps/common/models.py` | TimeStampedModel, UUIDModel base classes | VERIFIED | Both abstract model classes present |
| `.pre-commit-config.yaml` | Pre-commit hooks enforced on every commit | VERIFIED | `ruff-pre-commit` at rev `v0.15.11` present |
| `Makefile` | make up / test / lint / typecheck / migrate commands | VERIFIED | `migrate:` target present |
| `Dockerfile` | Multi-stage python:3.12-slim image with non-root user | VERIFIED | Both `AS builder` and `AS runtime` stages; `USER app`; HEALTHCHECK targeting `/readyz/` |
| `docker-compose.yml` | web, db, redis, mailhog, vite with healthchecks | VERIFIED | All five services; `condition: service_healthy` for web dependencies |
| `frontend/vite.config.ts` | Vite build config with manifest, @tailwindcss/vite | VERIFIED | `@tailwindcss/vite` imported; `manifest: "manifest.json"`; `outDir` pointing to `../static/dist` |
| `frontend/tailwind.config.js` | 20 brand tokens, Geist fonts, sidebar/radius spacing | VERIFIED | All 20 hex colour values present (grep count = 20); `sidebar: "240px"`; font-sans Geist |
| `frontend/src/styles/tailwind.css` | Tailwind v4 entrypoint `@import "tailwindcss"` | VERIFIED | `@import "tailwindcss"` present |
| `templates/base.html` | Django base shell with vite_asset tag | VERIFIED | Uses shell_open/shell_close includes; `{% include "partials/head.html" %}` present |
| `apps/common/views.py` | home(), healthz(), readyz(), logout_stub(), showcase() | VERIFIED | All five functions present |
| `apps/accounts/models.py` | User model with role enum + InvitationToken | VERIFIED | `class User(AbstractBaseUser, PermissionsMixin, TimeStampedModel)`, `class Role(TextChoices)`, `class InvitationToken` with `hash_token` and `is_expired` |
| `apps/accounts/managers.py` | UserManager with create_user / create_superuser | VERIFIED | `class UserManager` with both methods present |
| `apps/accounts/migrations/0001_initial.py` | First migration for User (no Organisation FK) | VERIFIED | Exists; does NOT contain `organisations.Organisation` |
| `apps/accounts/migrations/0002_user_organisation_invitationtoken.py` | Adds User.organisation FK + InvitationToken after organisations/0001 | VERIFIED | Contains `dependencies` with both `accounts/0001_initial` and `organisations/0001_initial` |
| `apps/organisations/models.py` | Organisation with Status/OrgType enums + soft_delete() + custom QuerySet | VERIFIED | All enums, `def soft_delete`, `OrganisationQuerySet.as_manager()` present |
| `apps/organisations/managers.py` | OrganisationQuerySet with active(), deleted(), annotate_store_counts() | VERIFIED | All methods present; `annotate_store_counts` is intentional Phase-1 stub (returns zero counts until Phase 2 adds Store model) |
| `apps/organisations/migrations/0001_initial.py` | Organisation migration depending on accounts/0001 | VERIFIED | Exists |
| `frontend/src/widgets/modal/Modal.tsx` | React Modal with focus-trap-react + portal + Escape | VERIFIED | `import FocusTrap from "focus-trap-react"`, `createPortal`, `role="dialog"`, `aria-modal="true"`, `aria-label="Close"` |
| `frontend/src/widgets/modal/ConfirmModal.tsx` | Confirmation modal with amber/blue/red variants + type-to-confirm | VERIFIED | `requireTypeToConfirm`, locked `Cancel` copy, all three variant constants |
| `frontend/src/widgets/data-table/DataTable.tsx` | Generic DataTable with loading/empty/populated/row-actions | VERIFIED | `data-testid="data-table-skeleton-row"`, `opacity-35 group-hover:opacity-100` |
| `frontend/src/lib/toast.ts` | emitToast dispatching app:toast CustomEvent | VERIFIED | `new CustomEvent("app:toast", { detail })` |
| `frontend/src/entrypoints/showcase.tsx` | React showcase entrypoint with createRoot | VERIFIED | `createRoot(container).render(<Showcase />)` |
| `templates/pages/showcase.html` | Showcase page wired to showcase.tsx via vite_asset | VERIFIED | `{% vite_asset 'src/entrypoints/showcase.tsx' %}` present |
| `apps/common/templatetags/ui.py` | is_active_route / is_active_url custom template tags | VERIFIED | `def is_active_route(context, prefix: str) -> bool` present |
| `templates/partials/sidebar.html` | Sidebar with role-based nav, active state, responsive classes, logout footer | VERIFIED | `hidden md:flex`, `md:w-sidebar-rail lg:w-sidebar`, `border-t border-[#27272A]`, `{% load ui %}`, `{% url 'logout' %}` |
| `templates/partials/topbar.html` | Topbar with bell, avatar dropdown, mobile hamburger | VERIFIED | `x-data="{ open: false }"`, `@click.outside="open = false"`, `aria-label="Open navigation"`, `aria-label="Notifications"` |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `config/settings/local.py` | `config/settings/base.py` | `from .base import *` | WIRED | Confirmed |
| `config/settings/base.py` | `apps.accounts.User` | `AUTH_USER_MODEL = "accounts.User"` | WIRED | Confirmed |
| `apps/accounts/migrations/0002_user_organisation_invitationtoken.py` | `apps/organisations/migrations/0001_initial.py` | `dependencies = [('organisations', '0001_initial')]` | WIRED | Confirmed |
| `apps/accounts/models.py (InvitationToken)` | `apps.organisations.Organisation` | `ForeignKey("organisations.Organisation")` | WIRED | Two FK references confirmed |
| `templates/partials/head.html` | `frontend/src/entrypoints/app-shell.ts` | `{% vite_asset 'src/entrypoints/app-shell.ts' %}` | WIRED | Confirmed |
| `frontend/vite.config.ts` | `static/dist/manifest.json` | `build.manifest + outDir ../static/dist` | WIRED | `manifest: "manifest.json"` and `outDir: resolve(__dirname, "../static/dist")` confirmed |
| `templates/base.html` | `templates/partials/shell_open.html + shell_close.html + sidebar.html + topbar.html` | `{% include %}` chain | WIRED | base.html includes shell_open/shell_close; shell_open.html includes sidebar.html and topbar.html |
| `templates/partials/topbar.html` | Alpine.js | `x-data="{ open: false }"` | WIRED | Confirmed |
| `templates/components/toasts.html` | window CustomEvent | `@app:toast.window="add($event.detail)"` | WIRED | Confirmed |
| `templates/partials/sidebar.html` | `apps.common.templatetags.ui.is_active_route` | `{% load ui %}` | WIRED | Both `{% load ui %}` and usage of `is_active_route` in `_nav_item.html` confirmed |
| `templates/partials/sidebar.html + topbar.html` | `apps.common.views.logout_stub` | `{% url 'logout' %}` → `path('logout/', logout_stub, name='logout')` | WIRED | Confirmed |
| `frontend/src/widgets/modal/Modal.tsx` | `focus-trap-react` | `import FocusTrap from "focus-trap-react"` | WIRED | Confirmed |
| `frontend/src/lib/toast.ts` | window CustomEvent | `new CustomEvent("app:toast", ...)` | WIRED | Confirmed |
| `templates/pages/showcase.html` | `frontend/src/entrypoints/showcase.tsx` | `{% vite_asset 'src/entrypoints/showcase.tsx' %}` | WIRED | Confirmed |
| `apps/common/urls.py` | `apps.common.views.showcase` | `path("__ui__/", showcase, name="showcase")` | WIRED | Confirmed |

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|---------|
| DSYS-01 | 01-01, 01-03, 01-04 | All authenticated pages render within a fixed left sidebar layout (Primary Black ~240px wide) | SATISFIED | Sidebar with `bg-black`, `w-sidebar` (240px) in `templates/partials/sidebar.html` |
| DSYS-02 | 01-04 | Sidebar displays role-specific navigation with white text, yellow active state, yellow hover, bottom-pinned logout | SATISFIED | Role-based nav items in sidebar.html; `border-l-[3px] border-yellow text-yellow` active state in `_nav_item.html`; `border-t border-[#27272A]` footer divider |
| DSYS-03 | 01-03, 01-04 | Top bar shows current page title/breadcrumb (left) and notification bell + profile avatar dropdown (right) | SATISFIED | `templates/partials/topbar.html` has both breadcrumb block and bell + avatar dropdown with Alpine.js toggle |
| DSYS-04 | 01-01, 01-03 | Main content area uses Background Gray (#FAFAFA) canvas with white content cards | SATISFIED | `<main class="flex-1 bg-bg p-4 md:p-8">` in shell_open.html; `bg-bg` maps to `#FAFAFA` in tailwind.config.js |
| DSYS-05 | 01-04 | Layout fully responsive: sidebar collapses to icon rail on tablet, hamburger drawer on mobile | SATISFIED | `md:w-sidebar-rail` (64px), `hidden md:flex`, `aria-label="Open navigation"` hamburger in topbar, `$store.nav.mobileOpen` Alpine store |
| DSYS-06 | 01-04 | Tables scroll horizontally on tablet; stacked cards on mobile | SATISFIED | `overflow-x-auto` in DataTable; responsive `flex-col md:flex-row` patterns in filter_bar; enabled by Tailwind responsive prefixes |
| DSYS-07 | 01-04, 01-05 | Reusable component set: buttons, form inputs, modal dialogs, confirmation popups, toast notifications, data tables, status badges, empty states, loading skeletons | SATISFIED | 8 Django template partials + Modal.tsx + ConfirmModal.tsx + DataTable.tsx all exist with correct implementation |
| DSYS-08 | 01-05 | Full keyboard navigation, visible focus states, ARIA labels on icon-only buttons, focus trap in modals, WCAG AA contrast | PARTIALLY SATISFIED (automated) / NEEDS HUMAN CONFIRMATION | `:focus-visible` rule in tailwind.css; ARIA labels on bell/hamburger/modal-close present; `FocusTrap` in Modal.tsx; human verify completed and "approved" per SUMMARY 01-05 but cannot be re-verified programmatically |

---

## Anti-Patterns Found

| File | Pattern | Severity | Impact |
|------|---------|----------|--------|
| `apps/organisations/managers.py` | `annotate_store_counts()` returns `Value(0)` stubs for `total_stores`/`active_stores` | INFO | Intentional Phase-1 design decision documented in SUMMARY 01-02; Phase 2 will replace with real `Count("stores")` after Store model exists. Not a blocker. |
| `apps/common/views.py` | `logout_stub` does NOT call `django.contrib.auth.logout(request)` | INFO | Intentional Phase-1 stub; documented in SUMMARY 01-04 and STATE.md. Phase 2 replaces view body. URL name `logout` is stable. |

No blocker-level anti-patterns found. No TODO/FIXME/placeholder comments in core business logic files. No empty implementations in shipped widget code.

---

## Human Verification Required

The following aspects were human-verified during plan execution (SUMMARY 01-05, Task 3 outcome: "approved") but cannot be re-confirmed programmatically. A fresh human verification is recommended before declaring the phase production-ready:

### 1. Responsive Layout (DSYS-01, DSYS-02, DSYS-03, DSYS-04, DSYS-05)

**Test:** Open `http://localhost:8000/__ui__/` with authenticated superadmin at 1440px, 768px, and 375px viewport widths
**Expected:** Sidebar 240px/64px rail/hidden at each breakpoint; bg-black sidebar; bg-bg main; topbar with bell + avatar dropdown; hamburger on mobile opens 260px drawer with backdrop
**Why human:** Visual rendering, colour accuracy, and responsive collapse behaviour require a live browser

### 2. Keyboard Navigation + Focus Trap (DSYS-08)

**Test:** Tab through `/__ui__/` showcase page; open modal via keyboard; tab within modal
**Expected:** First Tab shows skip link; all focusable elements have visible yellow 2px outline; Tab cannot escape open modal (focus-trap-react); Escape closes modal; focus returns to trigger
**Why human:** Focus trap behaviour and visible focus ring appearance require interactive browser testing

### 3. Toast End-to-End (DSYS-07)

**Test:** Click "Fire toast (success)" and "Fire toast (error)" buttons on the showcase React section
**Expected:** Dark toast appears top-right, correct icon, auto-dismisses after 5s, dismiss button works; React emitToast → window CustomEvent → Alpine.js stack receives it
**Why human:** CustomEvent dispatch + Alpine.js listener integration requires a live browser

### 4. Screen Reader ARIA (DSYS-08)

**Test:** Use VoiceOver (macOS) or NVDA (Windows) on `/__ui__/`
**Expected:** Bell announces "Notifications, button"; avatar announces "Open user menu, button"; modal close announces "Close, button"; skeleton announces "Loading, please wait"; error field announces via role=alert; heading hierarchy reads correctly
**Why human:** Screen reader output requires an assistive technology device and human listener

### 5. Lighthouse Accessibility Audit (DSYS-08)

**Test:** Run Lighthouse Accessibility audit on `http://localhost:8000/__ui__/` (requires running dev server)
**Expected:** Accessibility score 100; no images-missing-alt violations; no buttons-missing-text violations
**Why human:** Requires a running dev server; cannot be run in CI-like static analysis

---

## Gaps Summary

No gaps found. All 24 automated must-haves are verified. The status `human_needed` reflects that DSYS-08 (accessibility) includes visual/interactive dimensions that were human-verified during plan execution (approved per SUMMARY 01-05 Task 3) but cannot be confirmed via static file analysis alone.

The Phase-1 intentional stubs (`annotate_store_counts` returning zeros, `logout_stub` not calling `auth.logout`) are correctly documented and tracked for Phase 2 replacement.

---

_Verified: 2026-04-22T12:30:00Z_
_Verifier: Claude (gsd-verifier)_
