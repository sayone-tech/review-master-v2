---
phase: 01-foundation
verified: 2026-04-23T09:00:00Z
status: human_needed
score: 24/24 automated must-haves verified
re_verification:
  previous_status: human_needed
  previous_score: 24/24
  gaps_closed:
    - "Gap A: Mobile sidebar stale Alpine copy — sidebar now reads $store.nav?.mobileOpen directly"
    - "Gap B: Missing vite_react_refresh in head.html + incorrect vite_asset placement in showcase.html — both fixed"
  gaps_remaining: []
  regressions: []
human_verification:
  - test: "Visual rendering of shell chrome at desktop (1440px), tablet (768px), and mobile (375px)"
    expected: "Sidebar 240px desktop / 64px rail tablet / hidden with hamburger mobile; bg-black sidebar; bg-bg main content; topbar with bell + avatar dropdown; active nav item shows yellow left border"
    why_human: "Responsive layout and visual brand colour rendering cannot be verified programmatically without a running browser"
  - test: "Mobile sidebar drawer — hamburger opens sidebar overlay"
    expected: "Clicking hamburger button causes sidebar to slide in as a 260px overlay drawer on mobile viewport; backdrop appears behind; clicking backdrop closes drawer"
    why_human: "Alpine.js $store.nav.mobileOpen reactivity and CSS transition require a live browser at mobile viewport width"
  - test: "Full keyboard navigation flow on /__ui__/ showcase page"
    expected: "Tab reveals skip link; Tab traverses all interactive elements with visible yellow 2px focus ring; Enter on modal trigger opens modal; Tab trapped inside modal; Escape closes modal; focus returns to trigger"
    why_human: "Focus trap behaviour and visible focus ring appearance require interactive browser testing"
  - test: "React widgets render on /__ui__/ — Modal, ConfirmModal, DataTable, Toast buttons"
    expected: "showcase-root div is populated by mounted showcase.tsx; Modal trigger button visible; clicking opens modal; ConfirmModal trigger visible; DataTable demo renders; Toast fire buttons emit toasts"
    why_human: "React entrypoint mounting and CustomEvent bridge require a live browser with Vite dev server running"
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

**Verified:** 2026-04-23T09:00:00Z
**Status:** human_needed
**Re-verification:** Yes — after gap closure via plan 01-06 (two UAT gaps closed)

---

## Re-verification Summary

| Gap | Description | Previous Status | Current Status |
|-----|-------------|-----------------|----------------|
| Gap A | Mobile sidebar stale Alpine copy (`mobileOpen` was initialised from store once at mount, never updated on store mutation) | FAILING | CLOSED |
| Gap B | `{% vite_react_refresh %}` absent from `head.html`; `{% vite_asset %}` for showcase.tsx placed inside `{% block content %}` instead of `{% block extra_js %}` | FAILING | CLOSED |

No regressions detected in the 24 previously-passing automated checks.

---

## Plan 01-06 Must-Haves Verification

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Clicking the hamburger button on mobile causes the sidebar to slide in as a drawer overlay | VERIFIED (automated partial) / NEEDS HUMAN | `topbar.html` line 15: `@click="$store.nav.mobileOpen = true"`; `sidebar.html` line 12: `:class="$store.nav?.mobileOpen ? '!flex !fixed !w-[260px]' : ''"` reads store directly, no stale local copy. Backdrop: `x-show="$store.nav?.mobileOpen"`. Full visual behaviour requires browser. |
| 2 | The `/__ui__/` showcase page mounts the React entrypoint and renders Modal, ConfirmModal, DataTable, and Toast demo buttons | VERIFIED (automated partial) / NEEDS HUMAN | `head.html` lines 11–12: `{% vite_hmr_client %}` then `{% vite_react_refresh %}` (correct order); `showcase.html` lines 82–84: `{% vite_asset 'src/entrypoints/showcase.tsx' %}` is inside `{% block extra_js %}`, NOT inside `{% block content %}`; `id="showcase-root"` mount point present at line 77. Actual React render requires browser. |

**Score:** 2/2 automated checks verified (both require human confirmation of visual/interactive result)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `templates/partials/sidebar.html` | Alpine sidebar that reacts to `$store.nav.mobileOpen` live store value | VERIFIED | Line 3: `x-data="{ collapsed: false }"` — no `mobileOpen` in local state. Line 12: `:class="$store.nav?.mobileOpen ? '!flex !fixed !w-[260px]' : ''"`. Lines 77–79: backdrop also reads `$store.nav?.mobileOpen`. Zero bare `mobileOpen` references that bypass the store. |
| `templates/partials/head.html` | Vite React Refresh preamble required for @vitejs/plugin-react in dev mode | VERIFIED | Line 11: `{% vite_hmr_client %}`. Line 12: `{% vite_react_refresh %}`. Correct order, immediately adjacent. |
| `templates/base.html` | `extra_js` block rendered after `</main>` for script injection without DOM ordering issues | VERIFIED | Line 11: `</main>`. Line 12: `{% block extra_js %}{% endblock %}`. Line 13: `{% include "partials/shell_close.html" %}`. Order is correct. |
| `templates/pages/showcase.html` | `vite_asset` tag placed in `extra_js` block (not inside content block) | VERIFIED | Lines 82–84: `{% block extra_js %}` / `{% vite_asset 'src/entrypoints/showcase.tsx' %}` / `{% endblock %}`. Block content ends at line 80. Asset is outside and after content block. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `templates/partials/head.html` | `src/entrypoints/showcase.tsx` | `{% vite_react_refresh %}` preamble enables React HMR module execution | WIRED | `vite_react_refresh` present at line 12, after `vite_hmr_client` at line 11 |
| Hamburger button in `topbar.html` | `templates/partials/sidebar.html` `<aside>` | `$store.nav.mobileOpen` read directly (not via stale local copy) | WIRED | `topbar.html:15` sets `$store.nav.mobileOpen = true`; `sidebar.html:12` `:class` binds to `$store.nav?.mobileOpen` directly |

---

## Full Phase Goal Achievement

### Observable Truths (All Plans)

| # | Truth | Status | Evidence |
|----|-------|--------|---------|
| 1 | Django 6.0.2 project scaffold exists with split settings (base/local/production/test), uv deps, pre-commit hooks | VERIFIED | `pyproject.toml` has `django==6.0.2`; all four settings modules import `from .base import *`; `.pre-commit-config.yaml` has ruff-pre-commit, mypy, bandit, gitleaks hooks |
| 2 | apps/common foundation has TimeStampedModel, UUIDModel, health endpoints | VERIFIED | `apps/common/models.py` has both abstract model classes; `apps/common/views.py` has `def healthz` and `def readyz` |
| 3 | Custom User model with role enum, Organisation with soft-delete, InvitationToken with 48h expiry exist with correct migrations | VERIFIED | `apps/accounts/models.py` has `class User(AbstractBaseUser, PermissionsMixin, TimeStampedModel)` with `class Role(TextChoices)`, `class InvitationToken` with `hash_token` + `is_expired`; `apps/organisations/models.py` has `class Organisation` with `def soft_delete`; migration 0002 depends on both `accounts/0001_initial` and `organisations/0001_initial` |
| 4 | Docker dev environment with five services (web, db, redis, mailhog, vite) and healthchecks | VERIFIED | `Dockerfile` has multi-stage `FROM python:3.12-slim AS builder/runtime`, `USER app`, HEALTHCHECK targeting `/readyz/`; `docker-compose.yml` has all five services with `condition: service_healthy` on web dependencies |
| 5 | Vite + Tailwind v4 frontend toolchain with all 20 brand tokens | VERIFIED | `frontend/vite.config.ts` imports `@tailwindcss/vite` and has `manifest: "manifest.json"`; `frontend/tailwind.config.js` has all 20 tokens; `frontend/src/styles/tailwind.css` has `@import "tailwindcss"` |
| 6 | Alpine.js bundled via Vite (not CDN); Alpine.store('nav') registered | VERIFIED | `frontend/src/entrypoints/app-shell.ts` line 12: `Alpine.store("nav", { mobileOpen: false, ... })`; no CDN references in templates |
| 7 | Django base shell renders bg-black sidebar, bg-bg main content, Geist fonts, django-vite asset injection | VERIFIED | `sidebar.html` has `bg-black text-white`; `head.html` has `{% vite_asset 'src/entrypoints/app-shell.ts' %}` and Geist Google Fonts link; `base.html` uses shell_open/shell_close/extra_js split for block inheritance |
| 8 | Sidebar nav with role-based items, yellow active state (border-yellow), bottom-pinned logout | VERIFIED | `sidebar.html` has role-conditional nav blocks, `border-t border-[#27272A]` footer divider, `{% url 'logout' %}`; `_nav_item.html` has `border-l-[3px] border-yellow text-yellow` active state |
| 9 | Topbar with notification bell and Alpine.js avatar dropdown (open/close/escape/click-outside) | VERIFIED | `topbar.html` has `x-data="{ open: false }"`, `@click.outside="open = false"`, ARIA labels on bell and hamburger |
| 10 | Phase-1 logout stub registered; `{% url 'logout' %}` resolves without NoReverseMatch | VERIFIED | `apps/common/urls.py` has `path("logout/", logout_stub, name="logout")`; `apps/common/views.py` has `def logout_stub` returning 302 |
| 11 | 8 reusable template component partials: buttons, form_fields, badges, toasts, empty_state, skeletons, filter_bar, pagination | VERIFIED | All 8 files exist with correct content |
| 12 | React Modal primitive with focus-trap-react, portal, Escape, backdrop dismiss | VERIFIED | `Modal.tsx` has `import FocusTrap from "focus-trap-react"`, `createPortal`, `role="dialog"`, `aria-modal="true"` |
| 13 | ConfirmModal with amber/blue/red variants, locked Cancel copy, type-to-confirm gate | VERIFIED | `ConfirmModal.tsx` has `requireTypeToConfirm`, locked `Cancel` copy, three variant constants |
| 14 | DataTable with 6-row loading skeleton, empty state, populated rows, row actions opacity-35 hover | VERIFIED | `DataTable.tsx` has `data-testid="data-table-skeleton-row"`, `opacity-35 group-hover:opacity-100` |
| 15 | emitToast dispatches `app:toast` CustomEvent on window | VERIFIED | `frontend/src/lib/toast.ts` has `new CustomEvent("app:toast", { detail })` |
| 16 | Showcase page at `/__ui__/` renders all component categories and React mount | VERIFIED | `showcase.html` has `id="showcase-root"` mount point; `{% vite_asset 'src/entrypoints/showcase.tsx' %}` in `{% block extra_js %}` (not content block); `apps/common/urls.py` has `path("__ui__/", showcase, name="showcase")` |
| 17 | Focus ring (yellow 2px outline), `[x-cloak]` display:none rule, sk-pulse keyframe in tailwind.css | VERIFIED | `frontend/src/styles/tailwind.css` has `:focus-visible`, `[x-cloak]`, `@keyframes sk-pulse` |
| 18 | WCAG AA: visible focus states, ARIA labels on icon-only buttons, focus trap in modals, heading hierarchy | PARTIALLY VERIFIED (automated) / NEEDS HUMAN | Automated checks confirm ARIA attributes exist in markup; human verification per SUMMARY 01-05 completed and "approved" |
| 19 | Test infrastructure: pytest, factory-boy, vitest all configured | VERIFIED | `pyproject.toml` has `[tool.pytest.ini_options]` and `[tool.coverage.run/report]`; `frontend/vitest.config.ts` has `environment: "jsdom"`; factory files exist |
| 20 | Migration graph correct: accounts/0001 → organisations/0001 → accounts/0002 | VERIFIED | `apps/accounts/migrations/0002_user_organisation_invitationtoken.py` has correct `dependencies` list |
| 21 | Mobile sidebar: hamburger sets store; sidebar `<aside>` reads live store (no stale copy) | VERIFIED | `topbar.html:15` sets `$store.nav.mobileOpen = true`; `sidebar.html:12` `:class` binds `$store.nav?.mobileOpen` directly; `x-data` has no `mobileOpen` local copy |
| 22 | React HMR preamble: `{% vite_react_refresh %}` present in head.html after `{% vite_hmr_client %}` | VERIFIED | `head.html` lines 11–12 confirm correct order |
| 23 | `{% block extra_js %}` present in base.html after `</main>`, before shell_close | VERIFIED | `base.html` lines 11–13 confirm correct position |
| 24 | showcase.tsx vite_asset tag is inside `{% block extra_js %}`, NOT inside `{% block content %}` | VERIFIED | `showcase.html` lines 80–84 confirm asset in extra_js block |

**Score:** 24/24 automated checks verified

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `pyproject.toml` | Single source of truth for deps and tool config | VERIFIED | Contains `[project.dependencies]` with `django==6.0.2`; `[tool.ruff]`; `[tool.mypy]`; `[tool.pytest.ini_options]`; `[tool.coverage.run/report]` |
| `config/settings/base.py` | Shared Django settings with AUTH_USER_MODEL | VERIFIED | `AUTH_USER_MODEL = "accounts.User"` present |
| `config/settings/local.py` | Local dev overrides (DEBUG=True, MailHog, Vite dev) | VERIFIED | `from .base import *` present; MailHog email settings present |
| `config/settings/test.py` | Fast deterministic test settings | VERIFIED | `locmem.EmailBackend` present; `DisableMigrations` class present |
| `apps/common/models.py` | TimeStampedModel, UUIDModel base classes | VERIFIED | Both abstract model classes present |
| `.pre-commit-config.yaml` | Pre-commit hooks enforced on every commit | VERIFIED | `ruff-pre-commit` at rev `v0.15.11` present |
| `Makefile` | make up / test / lint / typecheck / migrate commands | VERIFIED | `migrate:` target present |
| `Dockerfile` | Multi-stage python:3.12-slim image with non-root user | VERIFIED | Both `AS builder` and `AS runtime` stages; `USER app`; HEALTHCHECK targeting `/readyz/` |
| `docker-compose.yml` | web, db, redis, mailhog, vite with healthchecks | VERIFIED | All five services; `condition: service_healthy` for web dependencies |
| `frontend/vite.config.ts` | Vite build config with manifest, @tailwindcss/vite | VERIFIED | `@tailwindcss/vite` imported; `manifest: "manifest.json"`; `outDir` pointing to `../static/dist` |
| `frontend/tailwind.config.js` | 20 brand tokens, Geist fonts, sidebar/radius spacing | VERIFIED | All 20 hex colour values present; `sidebar: "240px"`; font-sans Geist |
| `frontend/src/styles/tailwind.css` | Tailwind v4 entrypoint `@import "tailwindcss"` | VERIFIED | `@import "tailwindcss"` present |
| `templates/base.html` | Django base shell with vite_asset tag and extra_js block | VERIFIED | `{% include "partials/head.html" %}` present; `{% block extra_js %}{% endblock %}` after `</main>` |
| `apps/common/views.py` | home(), healthz(), readyz(), logout_stub(), showcase() | VERIFIED | All five functions present |
| `apps/accounts/models.py` | User model with role enum + InvitationToken | VERIFIED | `class User(AbstractBaseUser, PermissionsMixin, TimeStampedModel)`, `class Role(TextChoices)`, `class InvitationToken` with `hash_token` and `is_expired` |
| `apps/accounts/managers.py` | UserManager with create_user / create_superuser | VERIFIED | `class UserManager` with both methods present |
| `apps/accounts/migrations/0001_initial.py` | First migration for User (no Organisation FK) | VERIFIED | Exists; does NOT contain `organisations.Organisation` |
| `apps/accounts/migrations/0002_user_organisation_invitationtoken.py` | Adds User.organisation FK + InvitationToken after organisations/0001 | VERIFIED | Contains correct `dependencies` list |
| `apps/organisations/models.py` | Organisation with Status/OrgType enums + soft_delete() + custom QuerySet | VERIFIED | All enums, `def soft_delete`, `OrganisationQuerySet.as_manager()` present |
| `apps/organisations/managers.py` | OrganisationQuerySet with active(), deleted(), annotate_store_counts() | VERIFIED | All methods present; `annotate_store_counts` is intentional Phase-1 stub |
| `apps/organisations/migrations/0001_initial.py` | Organisation migration depending on accounts/0001 | VERIFIED | Exists |
| `frontend/src/widgets/modal/Modal.tsx` | React Modal with focus-trap-react + portal + Escape | VERIFIED | `import FocusTrap from "focus-trap-react"`, `createPortal`, `role="dialog"`, `aria-modal="true"` |
| `frontend/src/widgets/modal/ConfirmModal.tsx` | Confirmation modal with amber/blue/red variants + type-to-confirm | VERIFIED | `requireTypeToConfirm`, locked `Cancel` copy, all three variant constants |
| `frontend/src/widgets/data-table/DataTable.tsx` | Generic DataTable with loading/empty/populated/row-actions | VERIFIED | `data-testid="data-table-skeleton-row"`, `opacity-35 group-hover:opacity-100` |
| `frontend/src/lib/toast.ts` | emitToast dispatching app:toast CustomEvent | VERIFIED | `new CustomEvent("app:toast", { detail })` |
| `frontend/src/entrypoints/showcase.tsx` | React showcase entrypoint with createRoot | VERIFIED | `createRoot(container).render(<Showcase />)` |
| `templates/pages/showcase.html` | Showcase page wired to showcase.tsx via vite_asset in extra_js block | VERIFIED | `{% vite_asset 'src/entrypoints/showcase.tsx' %}` inside `{% block extra_js %}` (lines 82–84) |
| `apps/common/templatetags/ui.py` | is_active_route / is_active_url custom template tags | VERIFIED | `def is_active_route(context, prefix: str) -> bool` present |
| `templates/partials/sidebar.html` | Sidebar with role-based nav, active state, responsive classes, logout footer, live store binding | VERIFIED | `x-data="{ collapsed: false }"` (no stale mobileOpen); `:class="$store.nav?.mobileOpen ? ..."` on line 12; `bg-black text-white`; `hidden md:flex`; `md:w-sidebar-rail lg:w-sidebar` |
| `templates/partials/head.html` | head.html with vite_hmr_client then vite_react_refresh then app-shell asset | VERIFIED | Lines 11–14: `vite_hmr_client`, `vite_react_refresh`, stylesheet, `vite_asset 'src/entrypoints/app-shell.ts'` |
| `templates/partials/topbar.html` | Topbar with bell, avatar dropdown, mobile hamburger setting store | VERIFIED | `@click="$store.nav.mobileOpen = true"` on hamburger; `x-data="{ open: false }"`, `@click.outside="open = false"` on avatar dropdown |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `config/settings/local.py` | `config/settings/base.py` | `from .base import *` | WIRED | Confirmed |
| `config/settings/base.py` | `apps.accounts.User` | `AUTH_USER_MODEL = "accounts.User"` | WIRED | Confirmed |
| `apps/accounts/migrations/0002` | `apps/organisations/migrations/0001_initial.py` | `dependencies = [('organisations', '0001_initial')]` | WIRED | Confirmed |
| `apps/accounts/models.py (InvitationToken)` | `apps.organisations.Organisation` | `ForeignKey("organisations.Organisation")` | WIRED | Confirmed |
| `templates/partials/head.html` | `frontend/src/entrypoints/app-shell.ts` | `{% vite_asset 'src/entrypoints/app-shell.ts' %}` | WIRED | Confirmed at line 14 |
| `templates/partials/head.html` | React HMR | `{% vite_react_refresh %}` | WIRED | Confirmed at line 12, after vite_hmr_client |
| `frontend/vite.config.ts` | `static/dist/manifest.json` | `build.manifest + outDir ../static/dist` | WIRED | `manifest: "manifest.json"` and correct `outDir` confirmed |
| `templates/base.html` | `templates/partials/shell_open.html + shell_close.html + sidebar.html + topbar.html` | `{% include %}` chain | WIRED | base.html includes shell_open/shell_close; shell_open.html includes sidebar.html and topbar.html |
| `templates/base.html` | `{% block extra_js %}` | After `</main>`, before shell_close | WIRED | Lines 11–13 confirm correct order |
| `templates/partials/topbar.html` | `templates/partials/sidebar.html` | `$store.nav.mobileOpen = true` → `$store.nav?.mobileOpen` `:class` | WIRED | Hamburger sets store; sidebar reads store live with no local copy |
| `templates/partials/topbar.html` | Alpine.js | `x-data="{ open: false }"` | WIRED | Confirmed |
| `templates/components/toasts.html` | window CustomEvent | `@app:toast.window="add($event.detail)"` | WIRED | Confirmed |
| `templates/partials/sidebar.html` | `apps.common.templatetags.ui.is_active_route` | `{% load ui %}` | WIRED | Both `{% load ui %}` and usage in `_nav_item.html` confirmed |
| `templates/partials/sidebar.html + topbar.html` | `apps.common.views.logout_stub` | `{% url 'logout' %}` | WIRED | Confirmed |
| `frontend/src/widgets/modal/Modal.tsx` | `focus-trap-react` | `import FocusTrap from "focus-trap-react"` | WIRED | Confirmed |
| `frontend/src/lib/toast.ts` | window CustomEvent | `new CustomEvent("app:toast", ...)` | WIRED | Confirmed |
| `templates/pages/showcase.html` | `frontend/src/entrypoints/showcase.tsx` | `{% vite_asset 'src/entrypoints/showcase.tsx' %}` in `{% block extra_js %}` | WIRED | Confirmed at lines 82–84; correctly outside `{% block content %}` |
| `apps/common/urls.py` | `apps.common.views.showcase` | `path("__ui__/", showcase, name="showcase")` | WIRED | Confirmed |

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|---------|
| DSYS-01 | 01-01, 01-03, 01-04 | All authenticated pages render within a fixed left sidebar layout (Primary Black ~240px wide) | SATISFIED | Sidebar with `bg-black`, `w-sidebar` (240px) in `templates/partials/sidebar.html` |
| DSYS-02 | 01-04 | Sidebar displays role-specific navigation with white text, yellow active state, yellow hover, bottom-pinned logout | SATISFIED | Role-based nav items in sidebar.html; `border-l-[3px] border-yellow text-yellow` active state in `_nav_item.html`; `border-t border-[#27272A]` footer divider |
| DSYS-03 | 01-03, 01-04 | Top bar shows current page title/breadcrumb (left) and notification bell + profile avatar dropdown (right) | SATISFIED | `templates/partials/topbar.html` has both breadcrumb block and bell + avatar dropdown with Alpine.js toggle |
| DSYS-04 | 01-01, 01-03, 01-06 | Main content area uses Background Gray (#FAFAFA) canvas with white content cards | SATISFIED | `<main class="flex-1 bg-bg p-4 md:p-8">` in shell_open.html; `bg-bg` maps to `#FAFAFA`; `{% block extra_js %}` slot does not disrupt content area |
| DSYS-05 | 01-04, 01-06 | Layout fully responsive: sidebar collapses to icon rail on tablet, hamburger drawer on mobile | SATISFIED (automated) / NEEDS HUMAN | `md:w-sidebar-rail` (64px), `hidden md:flex`; hamburger in topbar sets `$store.nav.mobileOpen = true`; sidebar `<aside>` reads live store value directly (gap A closed). Drawer behaviour requires browser confirmation. |
| DSYS-06 | 01-04 | Tables scroll horizontally on tablet; stacked cards on mobile | SATISFIED | `overflow-x-auto` in DataTable; responsive `flex-col md:flex-row` patterns in filter_bar |
| DSYS-07 | 01-04, 01-05, 01-06 | Reusable component set: buttons, form inputs, modal dialogs, confirmation popups, toast notifications, data tables, status badges, empty states, loading skeletons | SATISFIED (automated) / NEEDS HUMAN for React mount | 8 Django template partials + Modal.tsx + ConfirmModal.tsx + DataTable.tsx all exist; showcase.tsx vite_asset correctly placed in extra_js block (gap B closed). Actual React widget rendering requires browser. |
| DSYS-08 | 01-05 | Full keyboard navigation, visible focus states, ARIA labels on icon-only buttons, focus trap in modals, WCAG AA contrast | PARTIALLY SATISFIED (automated) / NEEDS HUMAN CONFIRMATION | `:focus-visible` rule in tailwind.css; ARIA labels on bell/hamburger/modal-close present; `FocusTrap` in Modal.tsx; human verify completed and "approved" per SUMMARY 01-05 |

---

## Anti-Patterns Found

| File | Pattern | Severity | Impact |
|------|---------|----------|--------|
| `apps/organisations/managers.py` | `annotate_store_counts()` returns `Value(0)` stubs for `total_stores`/`active_stores` | INFO | Intentional Phase-1 design decision documented in SUMMARY 01-02; Phase 2 replaces with real `Count("stores")` after Store model exists. Not a blocker. |
| `apps/common/views.py` | `logout_stub` does NOT call `django.contrib.auth.logout(request)` | INFO | Intentional Phase-1 stub; documented in SUMMARY 01-04 and STATE.md. Phase 2 replaces view body. URL name `logout` is stable. |

No blocker-level anti-patterns found. No TODO/FIXME/placeholder comments in core business logic files. No empty implementations in shipped widget code.

---

## Human Verification Required

The following aspects require a live browser for full confirmation. Items 1 and 3 are newly surfaced by the gap-closure work in plan 01-06. Items 2, 4, 5, 6, 7 carry over from the initial verification.

### 1. Mobile Sidebar Drawer — Gap A confirmation (DSYS-05)

**Test:** Open `http://localhost:8000/__ui__/` on a 375px mobile viewport (or Chrome DevTools mobile emulation). Click the hamburger button in the topbar.
**Expected:** Sidebar slides in as a 260px overlay drawer from the left; a dark backdrop appears behind; clicking the backdrop closes the drawer; the hamburger toggle is coherent (open/close state matches drawer visibility)
**Why human:** Alpine.js `$store.nav.mobileOpen` reactivity and CSS overlay transitions require a live browser at mobile viewport width. Static analysis confirms the correct store binding is in place but cannot execute Alpine.

### 2. Full Keyboard Navigation + Focus Trap (DSYS-08)

**Test:** Tab through `/__ui__/` showcase page; open modal via keyboard; tab within modal
**Expected:** First Tab shows skip link; all focusable elements have visible yellow 2px outline; Tab cannot escape open modal (focus-trap-react); Escape closes modal; focus returns to trigger
**Why human:** Focus trap behaviour and visible focus ring appearance require interactive browser testing

### 3. React Widgets Render on /__ui__/ — Gap B confirmation (DSYS-07)

**Test:** Open `http://localhost:8000/__ui__/` with Vite dev server running. Inspect the `#showcase-root` div.
**Expected:** showcase.tsx mounts successfully; Modal trigger button is visible; clicking it opens a modal; ConfirmModal trigger visible; DataTable demo renders with skeleton/populated states; Toast fire buttons dispatch toasts
**Why human:** React entrypoint mounting, `@vitejs/plugin-react` React Refresh preamble, and CustomEvent bridge all require a live browser with Vite dev server. Static analysis confirms the `{% vite_react_refresh %}` tag and correct `{% block extra_js %}` placement are in place.

### 4. Toast System End-to-End (DSYS-07)

**Test:** Click "Fire toast (success)" and "Fire toast (error)" buttons on the showcase React section
**Expected:** Dark toast appears top-right, correct icon, auto-dismisses after 5s, dismiss button works; React `emitToast` → window CustomEvent → Alpine.js stack receives it
**Why human:** CustomEvent dispatch + Alpine.js listener integration requires a live browser

### 5. Screen Reader ARIA (DSYS-08)

**Test:** Use VoiceOver (macOS) or NVDA (Windows) on `/__ui__/`
**Expected:** Bell announces "Notifications, button"; avatar announces "Open user menu, button"; modal close announces "Close, button"; skeleton announces "Loading, please wait"; error field announces via role=alert; heading hierarchy reads correctly
**Why human:** Screen reader output requires an assistive technology device and human listener

### 6. Visual Responsive Layout (DSYS-01 through DSYS-05)

**Test:** Open `http://localhost:8000/__ui__/` at 1440px, 768px, and 375px viewport widths
**Expected:** Sidebar 240px/64px rail/hidden at each breakpoint; bg-black sidebar; bg-bg main; topbar with bell + avatar dropdown; active nav item shows yellow left border
**Why human:** Visual rendering, colour accuracy, and responsive collapse behaviour require a live browser

### 7. Lighthouse Accessibility Audit (DSYS-08)

**Test:** Run Lighthouse Accessibility audit on `http://localhost:8000/__ui__/` (requires running dev server)
**Expected:** Accessibility score 100; no images-missing-alt violations; no buttons-missing-text violations
**Why human:** Requires a running dev server; cannot be run in CI-like static analysis

---

## Gaps Summary

No automated gaps remain. The two UAT gaps closed by plan 01-06 are fully verified:

- **Gap A** (stale Alpine copy): `templates/partials/sidebar.html` `x-data` no longer initialises a local `mobileOpen` copy. All three `mobileOpen` references in the file read `$store.nav?.mobileOpen` or `$store.nav.mobileOpen` directly.
- **Gap B** (missing React Refresh + wrong asset placement): `{% vite_react_refresh %}` is present in `head.html` immediately after `{% vite_hmr_client %}`; `{% block extra_js %}` exists in `base.html` after `</main>`; `{% vite_asset 'src/entrypoints/showcase.tsx' %}` is inside `{% block extra_js %}` in `showcase.html`, not inside `{% block content %}`.

The status `human_needed` reflects that DSYS-05 (mobile drawer visual behaviour), DSYS-07 (React widget mount), and DSYS-08 (accessibility) include visual/interactive dimensions that cannot be confirmed via static file analysis alone. No automated blocker remains.

---

_Verified: 2026-04-23T09:00:00Z_
_Verifier: Claude (gsd-verifier)_
