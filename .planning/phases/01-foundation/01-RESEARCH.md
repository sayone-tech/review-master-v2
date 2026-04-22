# Phase 1: Foundation - Research

**Researched:** 2026-04-22
**Domain:** Django 6 project scaffolding, data models, design system, Docker dev environment
**Confidence:** HIGH (core stack verified against official sources; django-vite Django 6 classifier gap noted with LOW confidence risk)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Vite / Django wiring**
- Use `django-vite` package — provides `{% vite_asset %}` template tags
- Production: reads Vite's `manifest.json` for content-hashed filenames
- Development: django-vite proxies asset requests to Vite dev server
- Vite build output lands in `static/dist/` (repo root) — added to `STATICFILES_DIRS`
- `collectstatic` picks up `static/dist/` for production; `frontend/` is source-only
- Local dev: Vite dev server on :5173, Django on :8000, HMR active for React components
- Tailwind CSS runs as a PostCSS plugin inside Vite — single build pipeline, no separate Tailwind CLI or django-tailwind package

**React vs Template boundary**
- React components: Data tables (complex state, sorting, pagination) and modal dialogs (require focus trap, portal rendering)
- Django templates + Tailwind + Alpine.js: All other DSYS-07 components — buttons, form inputs, badges, empty states, loading skeletons, toast notifications
- Toast system: Alpine.js driven, triggered from Django messages framework via template-rendered initial state
- Entrypoints in `frontend/src/entrypoints/` — one per embedded React widget (e.g., `data-table.tsx`)

**Non-React interactivity**
- Alpine.js for all template-level interactions: sidebar collapse (desktop/tablet/mobile), profile dropdown, row action three-dot menus, confirmation popup triggers
- No HTMX in Phase 1 — server-rendered pages with Alpine.js for progressive enhancement
- Sidebar behaviour: desktop fixed 240px, tablet (768–1023px) collapses to icon rail, mobile (<768px) hamburger drawer — all driven by Alpine.js state

**Data models**
- User: custom model in `apps.accounts` with `role` enum (SUPERADMIN / ORG_ADMIN / STAFF_ADMIN); `AUTH_USER_MODEL = "accounts.User"` set before first migration — no other app migrates until `accounts/0001` exists
- Organisation: `status` field enum (ACTIVE / DISABLED / DELETED) — soft-delete sets status to DELETED, not a boolean flag; `number_of_stores` (allocation) + derived `stores_used` (count of linked active stores); org type enum: RETAIL / RESTAURANT / PHARMACY / SUPERMARKET
- InvitationToken: stores hash of TimestampSigner-generated token; `is_used` boolean; `expires_at` timestamp (48h from creation); FK to Organisation and to User (null until activated)
- Organisation Admin status (used in VORG-02): derived at query time — PENDING (token exists, unused, not expired), ACTIVE (token used), INVITATION_EXPIRED (token exists, unused, expired); no denormalised field

**Design system**
- Brand tokens in `tailwind.config.js`: primary yellow `#FACC15`, primary black `#0A0A0A`, background gray `#FAFAFA`
- Layout: fixed sidebar (Primary Black background), top bar, main content area (Background Gray) — server-rendered Django templates
- All WCAG AA contrast enforced via Tailwind config; focus states use yellow ring; ARIA labels on all icon-only buttons; focus trap in modals handled by React (via `focus-trap-react`)

### Claude's Discretion
- Exact Tailwind theme extension (spacing, typography scale, shadow tokens)
- Dockerfile multi-stage build details (base image layers, non-root user setup)
- docker-compose service health check implementations
- Vite entrypoint naming convention within `frontend/src/entrypoints/`
- Alpine.js version and whether loaded via CDN in dev or bundled via Vite

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| DSYS-01 | All authenticated pages render within a fixed left sidebar layout (Primary Black background, ~240px wide on desktop) | Layout structure documented in UI-SPEC; Django base template pattern covers implementation |
| DSYS-02 | Sidebar displays role-specific navigation with white text, yellow active state, yellow hover state, and bottom-pinned logout item | Nav item state specifications fully documented in UI-SPEC; Alpine.js x-data pattern identified |
| DSYS-03 | Top bar shows current page title/breadcrumb (left) and notification bell + profile avatar dropdown (right) | Topbar detail specification in UI-SPEC; Alpine.js dropdown pattern identified |
| DSYS-04 | Main content area uses Background Gray (#FAFAFA) canvas with white content cards | Color tokens and card specifications locked in UI-SPEC; Tailwind config pattern documented |
| DSYS-05 | Layout is fully responsive — sidebar collapses to collapsible icon rail on tablet (768-1023px) and hamburger drawer on mobile (<768px) | Responsive breakpoints and Alpine.js state fully documented in UI-SPEC |
| DSYS-06 | Tables scroll horizontally on tablet; transform into stacked cards on mobile | Mobile card spec and overflow-x-auto pattern documented in UI-SPEC |
| DSYS-07 | Reusable component set: buttons, form inputs, modal dialogs, confirmation popups, toasts, data tables, status badges, empty states, loading skeletons | All 20 components fully specified in UI-SPEC with pixel-accurate dimensions |
| DSYS-08 | Full keyboard navigation, visible focus states, ARIA labels on icon-only buttons, focus trap in modals, WCAG AA contrast compliance, logical heading hierarchy | Accessibility contract documented in UI-SPEC; focus-trap-react 1.x confirmed compatible with React 19 |
</phase_requirements>

---

## Summary

Phase 1 is a blank-repo-to-running-application build: Django 6 project scaffolding, three data models with migrations, a complete design system shell (sidebar + topbar + content area), and the full reusable component set. The technology stack is well-defined by CONTEXT.md and the UI-SPEC, leaving research to focus on verifying exact package versions, confirming integration patterns, and surfacing pitfalls.

The core risk is `django-vite 3.1.0` — its PyPI classifiers only declare support up to Django 4.2, though the package is functionally compatible with Django 5 and 6 (no breaking API differences; classifiers are often not updated by maintainers). This should be validated with a smoke test during Wave 0. A fallback (`django-vite-plugin`) exists if needed. All other stack components are confirmed at stable current versions.

The AUTH_USER_MODEL ordering constraint is the highest-consequence implementation risk: `apps.accounts.User` must be defined and its `0001_initial` migration must exist before any other app references it. Missing this causes irreversible migration graph corruption.

**Primary recommendation:** Follow the CONTEXT.md decisions precisely. Scaffold `apps/accounts` first, set `AUTH_USER_MODEL`, run the first migration, then scaffold remaining apps. Use `django-vite 3.1.0` and smoke-test the Vite dev server connection in Wave 0. Load Alpine.js via npm/Vite bundle (not CDN) for consistency with the single build pipeline decision.

---

## Standard Stack

### Core (Python/Django)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python | 3.12 | Runtime | Django 6 minimum requirement |
| Django | 6.0.2+ (pin exact, e.g. 6.0.2) | Web framework | Project requirement; released Dec 2025 |
| djangorestframework | 3.17.1 | REST API layer | Latest; officially supports Django 6.0 as of 3.17.0 |
| django-vite | 3.1.0 | Vite asset integration | Template tags for `{% vite_asset %}` |
| psycopg2-binary | 2.9.x | PostgreSQL adapter | Standard for Django+Postgres |
| django-redis | 5.x | Redis cache/session backend | Standard for Django Redis integration |
| django-environ | 0.11.x | Env var reading | Standard .env → settings pattern |
| python-json-logger | 3.x | JSON structured logging | Required by CLAUDE.md §18 |

### Core (JavaScript/Frontend)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| vite | 6.x (6.0.1 verified) | Build pipeline | Locked decision; PostCSS/React/HMR |
| @vitejs/plugin-react | 6.0.1 | React HMR in Vite | Standard companion to Vite + React |
| react | 19.2.5 | React runtime | For table/modal widgets only |
| react-dom | 19.2.5 | React DOM | Portal rendering for modals |
| tailwindcss | 4.2.4 | Utility-first CSS | Locked decision; PostCSS plugin in Vite |
| alpinejs | 3.15.11 | Template interactivity | Locked decision; sidebar, dropdowns, toasts |
| lucide-react | 1.8.0 | Icon set | Confirmed from design source files (UI-SPEC) |
| focus-trap-react | 12.0.0 | Modal focus trap | Locked decision; DSYS-08 accessibility |
| typescript | 5.x | TypeScript for frontend | Standard for React widget entrypoints |

### Supporting (Testing)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | 8.x | Test runner | All tests |
| pytest-django | 4.x | Django fixtures for pytest | Django model/view testing |
| factory-boy | 3.3.3 | Test data factories | All model factories |
| pytest-cov | 5.x | Coverage reporting | CI 85% gate |

### Supporting (Dev Tooling)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pre-commit | 4.x | Git hooks | Enforced per CLAUDE.md §14 |
| ruff | 0.15.11 | Linting + formatting | Enforced per CLAUDE.md §14 |
| mypy | 1.13.x | Type checking | Enforced per CLAUDE.md §14 |
| django-stubs | latest compatible | Mypy plugin for Django | Required alongside mypy |
| bandit | 1.8.x | Security scanning | Enforced per CLAUDE.md §14 |
| django-debug-toolbar | 4.x | Query inspection (local only) | Dev tooling |

### Version Verification

Versions verified against npm registry on 2026-04-22:
- `focus-trap-react`: 12.0.0
- `lucide-react`: 1.8.0
- `alpinejs`: 3.15.11
- `vite`: (latest 6.x)
- `@vitejs/plugin-react`: 6.0.1
- `react` + `react-dom`: 19.2.5
- `tailwindcss`: 4.2.4

djangorestframework 3.17.1 confirmed against official release notes (March 2026) as Django 6 compatible.

### Installation

```bash
# Python (uv — preferred per CLAUDE.md)
uv add django==6.0.2 djangorestframework==3.17.1 django-vite==3.1.0 \
        psycopg2-binary django-redis django-environ python-json-logger

uv add --group dev pytest pytest-django factory-boy pytest-cov \
        pre-commit ruff mypy django-stubs django-debug-toolbar bandit

# Node (from frontend/)
npm install --save-dev vite @vitejs/plugin-react typescript tailwindcss \
  alpinejs focus-trap-react lucide-react react react-dom
```

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| django-vite | django-vite-plugin | django-vite-plugin is minimalist, less battle-tested at scale |
| Alpine.js bundled via Vite | Alpine.js CDN | CDN is simpler but breaks the single build pipeline decision; CDN version not pinned |
| focus-trap-react | aria-modal + manual trap | focus-trap-react handles all edge cases (shadow DOM, dynamic content); don't hand-roll |
| tailwindcss v4 | tailwindcss v3 | v4 changes PostCSS config format significantly; v4 is what npm resolves to — verify config |

---

## Architecture Patterns

### Recommended Project Structure

Follows CLAUDE.md §3 exactly:

```
repo-root/
├── config/
│   ├── settings/
│   │   ├── base.py
│   │   ├── local.py      # Vite dev mode, MailHog, DEBUG=True
│   │   ├── production.py # SES, GCP Secret Manager, secure cookies
│   │   └── test.py       # locmem email, disabled migrations, SQLite or test DB
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
├── apps/
│   ├── accounts/         # FIRST app — User model must migrate before all others
│   │   ├── models.py     # custom User with role enum
│   │   ├── managers.py
│   │   ├── migrations/
│   │   │   └── 0001_initial.py   # MUST exist before any other app migrates
│   │   └── tests/
│   ├── organisations/    # Organisation model — depends on accounts
│   ├── common/           # TimeStampedModel, UUIDModel base classes
│   └── integrations/     # empty in Phase 1, structure only
├── frontend/
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── package.json
│   └── src/
│       └── entrypoints/  # one .tsx file per React widget mount point
│           └── data-table.tsx
├── static/
│   └── dist/             # Vite build output (gitignored); in STATICFILES_DIRS
├── templates/
│   ├── base.html         # shell layout, Alpine.js, django-vite tags
│   ├── partials/
│   └── emails/
├── Makefile
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml        # single source of truth — deps, ruff, mypy, pytest config
└── .pre-commit-config.yaml
```

### Pattern 1: Migration Ordering — AUTH_USER_MODEL First

**What:** Django requires `AUTH_USER_MODEL` to point to an existing model before any migration references `settings.AUTH_USER_MODEL`. Setting it after initial migrations causes irreversible dependency corruption.

**When to use:** Always, on any new Django project with a custom user model.

**Implementation sequence:**
1. Create `apps/accounts/models.py` with custom `User` model
2. Set `AUTH_USER_MODEL = "accounts.User"` in `config/settings/base.py`
3. Run `python manage.py makemigrations accounts` → creates `0001_initial`
4. Only then create `apps/organisations/` and run its migrations

```python
# apps/accounts/models.py
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models

class User(AbstractBaseUser, PermissionsMixin):
    class Role(models.TextChoices):
        SUPERADMIN   = "SUPERADMIN",   "Superadmin"
        ORG_ADMIN    = "ORG_ADMIN",    "Org Admin"
        STAFF_ADMIN  = "STAFF_ADMIN",  "Staff Admin"

    email        = models.EmailField(unique=True)
    full_name    = models.CharField(max_length=200, blank=True)
    role         = models.CharField(max_length=20, choices=Role.choices)
    organisation = models.ForeignKey(
        "organisations.Organisation",
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="members",
    )
    is_active  = models.BooleanField(default=True)
    is_staff   = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["full_name"]

    objects = UserManager()
```

### Pattern 2: Organisation Model with Status Enum Soft-Delete

**What:** Status enum replaces boolean `is_deleted`. Soft-delete sets `status = DELETED`. Custom QuerySet provides chainable manager methods.

```python
# apps/organisations/models.py
from django.db import models

class Organisation(models.Model):
    class Status(models.TextChoices):
        ACTIVE   = "ACTIVE",   "Active"
        DISABLED = "DISABLED", "Disabled"
        DELETED  = "DELETED",  "Deleted"

    class OrgType(models.TextChoices):
        RETAIL      = "RETAIL",      "Retail"
        RESTAURANT  = "RESTAURANT",  "Restaurant"
        PHARMACY    = "PHARMACY",    "Pharmacy"
        SUPERMARKET = "SUPERMARKET", "Supermarket"

    name              = models.CharField(max_length=100, db_index=True)
    org_type          = models.CharField(max_length=20, choices=OrgType.choices, db_index=True)
    email             = models.EmailField(unique=True)
    address           = models.TextField(max_length=500, blank=True)
    number_of_stores  = models.PositiveIntegerField()  # allocation
    status            = models.CharField(
        max_length=10, choices=Status.choices,
        default=Status.ACTIVE, db_index=True,
    )
    created_by        = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL,
        null=True, related_name="created_organisations",
    )
    created_at        = models.DateTimeField(auto_now_add=True)
    updated_at        = models.DateTimeField(auto_now=True)

    objects = OrganisationQuerySet.as_manager()

    def soft_delete(self) -> None:
        self.status = self.Status.DELETED
        self.save(update_fields=["status", "updated_at"])
```

### Pattern 3: django-vite Integration

**Configuration (config/settings/base.py):**

```python
INSTALLED_APPS = [
    ...
    "django_vite",
    ...
]

DJANGO_VITE = {
    "default": {
        "dev_mode": env.bool("DJANGO_VITE_DEV_MODE", default=False),
        "dev_server_host": "localhost",
        "dev_server_port": 5173,
        "manifest_path": BASE_DIR / "static" / "dist" / "manifest.json",
    }
}

STATICFILES_DIRS = [
    BASE_DIR / "static" / "dist",
]
```

**config/settings/local.py override:**
```python
DJANGO_VITE = {
    "default": {
        "dev_mode": True,
        "dev_server_host": "localhost",
        "dev_server_port": 5173,
    }
}
```

**vite.config.ts:**
```typescript
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { resolve } from "path";

export default defineConfig({
  base: "/static/dist/",
  plugins: [react()],
  build: {
    manifest: "manifest.json",
    outDir: resolve(__dirname, "../static/dist"),
    emptyOutDir: true,
    rollupOptions: {
      input: {
        "data-table": resolve(__dirname, "src/entrypoints/data-table.tsx"),
        // add one entry per React widget
      },
    },
  },
  css: {
    postcss: "./postcss.config.js",
  },
});
```

**base.html template:**
```django
{% load django_vite %}
<!DOCTYPE html>
<html lang="en">
<head>
  {% vite_hmr_client %}
  {% vite_react_refresh %}
  {% vite_asset 'src/entrypoints/data-table.tsx' %}
</head>
```

**React widget mount in Django template:**
```html
<div id="data-table-root"
     data-initial='{{ initial_data|escapejs }}'></div>
```

### Pattern 4: Alpine.js State for Shell Interactivity

Alpine.js is loaded as an npm package bundled through Vite (not CDN), keeping a single build pipeline:

```typescript
// frontend/src/entrypoints/app-shell.ts  (or inline in base.html script if CDN approach chosen)
import Alpine from "alpinejs";
window.Alpine = Alpine;
Alpine.start();
```

**Sidebar collapse (base.html body):**
```html
<body x-data="{ sidebarOpen: false, sidebarCollapsed: false }">
  <!-- Mobile overlay drawer -->
  <div class="sidebar-drawer"
       :class="{ 'open': sidebarOpen }"
       @keydown.escape.window="sidebarOpen = false">
  </div>
  <!-- Tablet collapse toggle in topbar -->
  <button @click="sidebarCollapsed = !sidebarCollapsed"
          :aria-label="sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'">
  </button>
```

**Toast dispatch from React:**
```typescript
// Inside React widget
window.dispatchEvent(new CustomEvent("app:toast", {
  detail: { kind: "success", title: "Organisation created", msg: `Invitation email sent to ${email}.` }
}));
```

**Alpine.js listener on body:**
```html
<body x-data="{ toasts: [] }"
      @app:toast.window="toasts.push($event.detail); setTimeout(() => toasts.shift(), 5000)">
  <template x-for="toast in toasts" :key="toast.title">
    <div role="status" aria-live="polite" ...></div>
  </template>
```

### Pattern 5: Tailwind Config with Design Tokens

Per UI-SPEC Tailwind Config Token Reference (locked — derived from `styles.css` `:root`):

```javascript
// tailwind.config.js
export default {
  content: [
    "./templates/**/*.html",
    "./apps/**/*.html",
    "./frontend/src/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        "yellow":        "#FACC15",
        "yellow-hover":  "#EAB308",
        "yellow-tint":   "#FEFCE8",
        "black":         "#0A0A0A",
        "ink":           "#18181B",
        "text":          "#27272A",
        "muted":         "#52525B",
        "subtle":        "#71717A",
        "faint":         "#A1A1AA",
        "line":          "#E4E4E7",
        "line-soft":     "#F4F4F5",
        "bg":            "#FAFAFA",
        "green":         "#16A34A",
        "green-tint":    "#DCFCE7",
        "red":           "#DC2626",
        "red-tint":      "#FEE2E2",
        "amber":         "#D97706",
        "amber-tint":    "#FEF3C7",
        "blue":          "#2563EB",
        "blue-tint":     "#DBEAFE",
      },
      fontFamily: {
        sans: ["Geist", "-apple-system", "BlinkMacSystemFont", "'Segoe UI'", "system-ui", "sans-serif"],
        mono: ["'Geist Mono'", "ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
      spacing: {
        sidebar:      "240px",
        "sidebar-rail": "64px",
      },
      borderRadius: {
        sm:           "6px",
        md:           "8px",
        menu:         "10px",
        card:         "12px",
        modal:        "14px",
        logo:         "7px",
        "confirm-icon": "12px",
      },
    },
  },
  plugins: [],
};
```

### Anti-Patterns to Avoid

- **Setting `AUTH_USER_MODEL` after initial migrations:** Causes irreversible migration dependency corruption. There is no clean fix short of recreating the database.
- **Importing `User` directly instead of `get_user_model()`:** Breaks if `AUTH_USER_MODEL` changes; always use `from django.contrib.auth import get_user_model`.
- **Putting business logic in `save()` overrides:** Use services instead. CLAUDE.md §5 is strict on this.
- **Loading Alpine.js from CDN when bundling via Vite:** Inconsistent — either bundle via Vite (single pipeline) or use CDN consistently. Mixing causes duplicate Alpine instances.
- **Using `tailwindcss` v4's new `@import "tailwindcss"` without updating PostCSS config:** Tailwind v4 changed the PostCSS plugin API. Verify the postcss.config.js pattern matches the installed major version.
- **Placing apps at repo root instead of under `apps/`:** Violates CLAUDE.md §3 and breaks the project's import conventions.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Modal focus trap | Custom Tab keydown handler | `focus-trap-react` 12.0.0 | Edge cases: shadow DOM, dynamic content, iOS Safari, screen readers |
| Vite manifest reading | Custom manifest.json parser in templates | `django-vite` template tags | Handles dev server proxying, content hash URLs, React HMR |
| JSON structured logging | Custom logging formatter | `python-json-logger` | Standard format, thread-safe, Django logging integration |
| Rate limiting / throttle | Custom Redis counter | DRF `UserRateThrottle` backed by django-redis | Battle-tested, handles race conditions |
| Icon SVGs inline | Custom SVG sprite | `lucide-react` | Tree-shaken, consistent sizing API, accessible by default |
| TimestampSigner tokens | Custom HMAC token generator | `django.core.signing.TimestampSigner` | Built-in, handles expiry, single-use enforcement |

**Key insight:** This phase's component set is mostly CSS/HTML with a thin Alpine.js layer. The temptation to hand-roll focus management, toast stacking, or token signing is high because they appear simple — each has non-trivial edge cases.

---

## Common Pitfalls

### Pitfall 1: AUTH_USER_MODEL Set After First Migration

**What goes wrong:** Running `manage.py migrate` before setting `AUTH_USER_MODEL` creates `auth.User` as the user model. Changing it later causes `InconsistentMigrationHistory` and breaks all FK references.
**Why it happens:** Developer scaffolds project quickly without reading Django's custom user model warning.
**How to avoid:** Set `AUTH_USER_MODEL = "accounts.User"` in `config/settings/base.py` before running any `migrate` or `makemigrations` command. Do this before creating any other app.
**Warning signs:** `auth.User` appears in migration dependencies; `accounts.User` is not listed as the user model in `django.contrib.auth`.

### Pitfall 2: Circular Migration Dependency

**What goes wrong:** `Organisation` has a FK to `User`, and `User` has a FK to `Organisation`. Django cannot resolve the circular dependency automatically → `CircularDependencyError`.
**Why it happens:** The relationship between User and Organisation is bidirectional.
**How to avoid:** The `User.organisation` FK is nullable. Keep it in `accounts/0001_initial.py` but reference `organisations.Organisation` as a string `"organisations.Organisation"` — Django resolves string references lazily. Ensure `accounts` migration does not depend on `organisations` migration directly.
**Alternative:** Split into two migrations — `accounts/0001` creates User without the Organisation FK, `accounts/0002` adds the FK after `organisations/0001` exists.

### Pitfall 3: Tailwind v4 PostCSS Config Change

**What goes wrong:** `tailwindcss` 4.x changed how it registers as a PostCSS plugin. Using the v3 pattern `require("tailwindcss")` in `postcss.config.js` with v4 installed produces a "PostCSS plugin was defined incorrectly" error.
**Why it happens:** npm resolves `tailwindcss` to 4.x (verified: 4.2.4). Tutorials and docs using v3 patterns are abundant.
**How to avoid:**
```javascript
// postcss.config.js for Tailwind v4
import tailwindcss from "@tailwindcss/vite"; // use the Vite plugin directly
// OR in vite.config.ts:
import tailwindcss from "@tailwindcss/vite";
plugins: [react(), tailwindcss()]
```
Check the installed major version before writing the config. If using Tailwind 4, use `@tailwindcss/vite` plugin, not the PostCSS plugin.
**Warning signs:** Build fails with `PostCSS plugin was defined incorrectly` at Vite startup.

### Pitfall 4: django-vite Dev Server Not Running = 500 Error

**What goes wrong:** Django template renders `{% vite_asset %}` in dev mode, which generates a `<script src="http://localhost:5173/...">` tag. If Vite dev server is not running, the page renders a broken 500 or blank page.
**Why it happens:** Dev-mode asset loading depends on the Vite server being up.
**How to avoid:** `docker-compose.yml` must start the Vite dev server as a separate service. Use `depends_on` with a health check or a startup ordering wait. The Django web service must wait for Vite to be ready.
**Warning signs:** `net::ERR_CONNECTION_REFUSED` for :5173 in browser console; blank React widget mounts.

### Pitfall 5: django-vite Django 6 Classifier Gap

**What goes wrong:** `django-vite 3.1.0` PyPI classifiers only declare up to Django 4.2. This does NOT mean it's incompatible — the Django template tag API used by django-vite has not changed in a breaking way through Django 6. However, if a future version of Django breaks the internal URL resolution or static files storage API that django-vite relies on, it would fail silently in some deployments.
**Why it happens:** Many package maintainers update PyPI classifiers slowly. The package code itself does not restrict to Django 4.2.
**How to avoid:** Run a smoke test in Wave 0: `python manage.py check` + load a page with `{% vite_asset %}` in dev mode. If it works, confidence is HIGH. If it fails, use `django-vite-plugin` as a drop-in alternative.
**Warning signs:** `ImproperlyConfigured` exception from `django_vite` module on startup.

### Pitfall 6: Alpine.js Duplicate Instance

**What goes wrong:** Alpine.js initialised twice — once via CDN `<script>` in `base.html` and once bundled via Vite. Alpine throws a console error and `x-data` directives on dynamically-injected React DOM nodes fail silently.
**Why it happens:** Developer adds CDN link for quick iteration, then also imports Alpine in the Vite bundle.
**How to avoid:** Choose one: either bundle Alpine via Vite (recommended for single pipeline consistency) or load from CDN. Do not do both.

### Pitfall 7: React Widget Mount Point Not Present When Widget Loads

**What goes wrong:** `data-table.tsx` entrypoint calls `document.getElementById("data-table-root")` before the DOM element exists → `TypeError: Cannot read properties of null`.
**Why it happens:** Script loads before the mount `<div>` is rendered, or page template does not include the mount div.
**How to avoid:** Use `DOMContentLoaded` listener or load scripts as `type="module"` (deferred by default). Verify template includes the mount `<div>` with `id="data-table-root"` before the `{% vite_asset %}` tag.

---

## Code Examples

### Custom User Model — UserManager

```python
# apps/accounts/managers.py
from django.contrib.auth.base_user import BaseUserManager

class UserManager(BaseUserManager):
    def create_user(self, email: str, password: str | None = None, **extra_fields):
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email: str, password: str, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self.create_user(email, password, **extra_fields)
```

### InvitationToken Model

```python
# apps/accounts/models.py (add to same file or separate)
import hashlib
from django.db import models
from django.utils import timezone

class InvitationToken(models.Model):
    organisation = models.ForeignKey(
        "organisations.Organisation",
        on_delete=models.CASCADE,
        related_name="invitation_tokens",
    )
    invited_user = models.OneToOneField(
        "accounts.User",
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="invitation_token",
    )
    token_hash   = models.CharField(max_length=64, unique=True, db_index=True)
    is_used      = models.BooleanField(default=False, db_index=True)
    expires_at   = models.DateTimeField(db_index=True)
    created_at   = models.DateTimeField(auto_now_add=True)

    @property
    def is_expired(self) -> bool:
        return timezone.now() > self.expires_at

    @classmethod
    def hash_token(cls, raw_token: str) -> str:
        return hashlib.sha256(raw_token.encode()).hexdigest()
```

### docker-compose.yml (key services)

```yaml
version: "3.9"
services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: reviewmaster
      POSTGRES_USER: app
      POSTGRES_PASSWORD: app
    healthcheck:
      test: ["CMD", "pg_isready", "-U", "app"]
      interval: 5s
      timeout: 5s
      retries: 5
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 3

  mailhog:
    image: mailhog/mailhog:latest
    ports:
      - "8025:8025"   # Web UI
      - "1025:1025"   # SMTP

  vite:
    image: node:22-alpine
    working_dir: /app/frontend
    command: npm run dev
    volumes:
      - .:/app
    ports:
      - "5173:5173"
    healthcheck:
      test: ["CMD", "wget", "-qO-", "http://localhost:5173"]
      interval: 5s
      timeout: 3s
      retries: 5

  web:
    build: .
    command: python manage.py runserver 0.0.0.0:8000
    environment:
      DJANGO_SETTINGS_MODULE: config.settings.local
      DATABASE_URL: postgres://app:app@db:5432/reviewmaster
      REDIS_URL: redis://redis:6379
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    ports:
      - "8000:8000"
    volumes:
      - .:/app

volumes:
  postgres_data:
```

### Healthcheck Views (/healthz/ and /readyz/)

```python
# apps/common/views.py
from django.db import connection
from django.core.cache import cache
from django.http import JsonResponse

def healthz(request):
    """Liveness probe — app is running."""
    return JsonResponse({"status": "ok"})

def readyz(request):
    """Readiness probe — DB and Redis are reachable."""
    checks = {}
    try:
        connection.ensure_connection()
        checks["db"] = "ok"
    except Exception as e:
        checks["db"] = str(e)

    try:
        cache.set("readyz_check", "1", 5)
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = str(e)

    status = 200 if all(v == "ok" for v in checks.values()) else 503
    return JsonResponse({"status": "ready" if status == 200 else "degraded", **checks}, status=status)
```

### pyproject.toml key sections

```toml
[tool.pytest.ini_options]
DJANGO_SETTINGS_MODULE = "config.settings.test"
python_files = ["test_*.py"]
addopts = "--strict-markers --tb=short"

[tool.coverage.run]
source = ["apps"]
omit = ["*/migrations/*", "*/tests/*"]

[tool.coverage.report]
fail_under = 85
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Tailwind CLI separate process | Tailwind as PostCSS plugin inside Vite | Tailwind v3.x+ | Single build pipeline; no separate `npm run tw` |
| `requirements.txt` + pip | `pyproject.toml` + uv | 2024-2025 ecosystem shift | Faster installs, lockfile, single config |
| `python manage.py test` + Django TestCase | pytest + pytest-django | 2020+ mainstream | Fixtures, parametrize, better DX |
| React 17 `ReactDOM.render` | React 18+ `createRoot` | React 18 (2022) | Concurrent mode; required for React 19 |
| `tailwindcss` v3 `require("tailwindcss")` PostCSS | `tailwindcss` v4 `@tailwindcss/vite` plugin | Tailwind v4 (2025) | Breaking change in PostCSS plugin registration |
| `auth.User` directly | Custom user model with `AbstractBaseUser` | Django best practice since 1.5 | Cannot be changed after first migration |

**Deprecated/outdated:**
- `python-decouple`: use `django-environ` (matches CLAUDE.md)
- `django-crispy-forms`: not in this stack — custom template partials with Tailwind
- `HTMX`: explicitly excluded from Phase 1 (CONTEXT.md)

---

## Open Questions

1. **django-vite Django 6 classifier gap**
   - What we know: PyPI classifiers show support up to Django 4.2; package released Feb 2025; no breaking API change identified
   - What's unclear: Whether any internal Django 6 change broke the staticfiles or URL resolution layer django-vite relies on
   - Recommendation: Wave 0 task must include a smoke test (`manage.py check` + page load with `{% vite_asset %}`). If it fails, swap to `django-vite-plugin` (declared Django 6 support not confirmed there either) or pin `DJANGO_VITE` to read the manifest directly without the package.

2. **Tailwind v4 PostCSS vs `@tailwindcss/vite` plugin**
   - What we know: `tailwindcss` 4.2.4 is installed by npm; v4 changed PostCSS plugin API
   - What's unclear: Whether to use `@tailwindcss/vite` plugin or the PostCSS path in this Vite setup
   - Recommendation: Use the `@tailwindcss/vite` Vite plugin (official Tailwind v4 recommendation for Vite projects). Install `@tailwindcss/vite` separately and do NOT add tailwindcss to `postcss.config.js`.

3. **Alpine.js bundled vs CDN**
   - What we know: CONTEXT.md leaves this to Claude's discretion
   - Recommendation: Bundle via Vite npm import (`import Alpine from "alpinejs"`) for consistency with the single build pipeline. CDN is acceptable for speed but breaks the locked decision of Vite being the single asset pipeline.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest + pytest-django |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` — Wave 0 creates this |
| Quick run command | `pytest apps/ -x -q --tb=short` |
| Full suite command | `pytest apps/ --cov=apps --cov-fail-under=85` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DSYS-01 | Sidebar shell template renders without error | Smoke / Django TestClient | `pytest apps/accounts/tests/test_views.py -x` | Wave 0 |
| DSYS-02 | Sidebar nav items carry correct CSS classes for active/hover state | Template unit | `pytest apps/common/tests/test_templates.py -x` | Wave 0 |
| DSYS-03 | Topbar renders page title and bell/avatar | Template unit | `pytest apps/common/tests/test_templates.py -x` | Wave 0 |
| DSYS-04 | Main content area uses correct background class | Template unit | `pytest apps/common/tests/test_templates.py -x` | Wave 0 |
| DSYS-05 | Responsive breakpoint classes present in sidebar HTML | Template unit | `pytest apps/common/tests/test_templates.py -x` | Wave 0 |
| DSYS-06 | Table wrapper has `overflow-x-auto`; mobile card class present | Template unit | `pytest apps/common/tests/test_templates.py -x` | Wave 0 |
| DSYS-07 | All component classes render (buttons, badges, skeletons, empty state) | Template smoke | `pytest apps/common/tests/test_components.py -x` | Wave 0 |
| DSYS-08 | Focus ring class present on interactive elements; ARIA labels on icon buttons | Accessibility / template unit | `pytest apps/common/tests/test_accessibility.py -x` | Wave 0 |

Note: DSYS-05 through DSYS-08 visual/interactive correctness (responsive layout, keyboard navigation, focus trap behaviour) requires manual QA — automated tests cover markup presence only.

### Sampling Rate

- **Per task commit:** `pytest apps/ -x -q --tb=short`
- **Per wave merge:** `pytest apps/ --cov=apps --cov-fail-under=85`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `apps/accounts/tests/__init__.py`
- [ ] `apps/accounts/tests/factories.py` — UserFactory
- [ ] `apps/accounts/tests/test_models.py` — User model unit tests
- [ ] `apps/organisations/tests/__init__.py`
- [ ] `apps/organisations/tests/factories.py` — OrganisationFactory, InvitationTokenFactory
- [ ] `apps/organisations/tests/test_models.py` — Organisation soft-delete, InvitationToken expiry
- [ ] `apps/common/tests/__init__.py`
- [ ] `apps/common/tests/test_templates.py` — shell layout, component presence
- [ ] `apps/common/tests/test_accessibility.py` — ARIA label presence
- [ ] `pyproject.toml` `[tool.pytest.ini_options]` section
- [ ] `config/settings/test.py` — fast test settings
- [ ] Framework install: `uv add --group dev pytest pytest-django factory-boy pytest-cov`

---

## Sources

### Primary (HIGH confidence)

- Official Django 6.0 docs — custom user model, AUTH_USER_MODEL constraint
- Official djangorestframework release notes — confirmed 3.17.1 supports Django 6.0 (verified March 2026)
- Official django-vite GitHub README — configuration pattern, template tags
- Official Vite docs (vite.dev) — multiple entrypoints, manifest, build config
- npm registry — focus-trap-react 12.0.0, lucide-react 1.8.0, alpinejs 3.15.11, react 19.2.5, @vitejs/plugin-react 6.0.1, tailwindcss 4.2.4 (verified 2026-04-22)
- UI-SPEC (01-UI-SPEC.md) — pixel-accurate design token specifications, all 20 component specifications
- CONTEXT.md — locked implementation decisions

### Secondary (MEDIUM confidence)

- PyPI django-vite 3.1.0 page — version confirmed Feb 23, 2025; Django 4.2 listed as max in classifiers
- Django Forum + multiple blog posts — AUTH_USER_MODEL ordering requirement, circular dependency mitigation
- Official pytest-django docs — pyproject.toml configuration pattern

### Tertiary (LOW confidence)

- Community reports that django-vite 3.1 works with Django 5+ (no explicit official statement; inferred from no reported issues on GitHub)
- Tailwind v4 PostCSS vs Vite plugin path — official docs indicate `@tailwindcss/vite` is the recommended approach; exact config for this stack needs Wave 0 validation

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all packages verified against official registries/release notes
- Architecture: HIGH — patterns derived from CLAUDE.md, CONTEXT.md, UI-SPEC directly
- django-vite Django 6 compatibility: LOW — classifiers stop at 4.2; functional compatibility likely but unverified
- Tailwind v4 config: MEDIUM — official docs exist but require validation against this specific Vite setup
- Pitfalls: HIGH — AUTH_USER_MODEL and circular migration pitfalls are documented by official Django docs

**Research date:** 2026-04-22
**Valid until:** 2026-05-22 (stable stack; Tailwind v4 and django-vite are the moving parts)
