# Phase 1: Foundation - Context

**Gathered:** 2026-04-22
**Status:** Ready for planning

<domain>
## Phase Boundary

Project scaffolding (blank repo → runnable Django 6 app), all data models with migrations
(User with role enum, Organisation with soft-delete, InvitationToken), the base layout shell
(fixed left sidebar, top bar, main content area), the full reusable component set (buttons,
form inputs, modals, toasts, data tables, badges, empty states, loading skeletons), and the
Docker dev environment. Auth, org management, and invitation flows are separate phases.

Requirements: DSYS-01 through DSYS-08.

</domain>

<decisions>
## Implementation Decisions

### Vite ↔ Django wiring
- Use `django-vite` package — provides `{% vite_asset %}` template tags
- Production: reads Vite's `manifest.json` for content-hashed filenames
- Development: django-vite proxies asset requests to Vite dev server
- Vite build output lands in `static/dist/` (repo root) — added to `STATICFILES_DIRS`
- `collectstatic` picks up `static/dist/` for production; frontend/ is source-only
- Local dev: Vite dev server on :5173, Django on :8000, HMR active for React components
- Tailwind CSS runs as a PostCSS plugin inside Vite — single build pipeline, no separate Tailwind CLI or django-tailwind package

### React vs Template boundary
- **React components:** Data tables (complex state, sorting, pagination) and modal dialogs (require focus trap, portal rendering)
- **Django templates + Tailwind + Alpine.js:** All other DSYS-07 components — buttons, form inputs, badges, empty states, loading skeletons, toast notifications
- Toast system: Alpine.js driven, triggered from Django messages framework via template-rendered initial state
- Entrypoints in `frontend/src/entrypoints/` — one per embedded React widget (e.g., `data-table.tsx`)

### Non-React interactivity
- **Alpine.js** for all template-level interactions: sidebar collapse (desktop→tablet→mobile), profile dropdown, row action three-dot menus, confirmation popup triggers
- No HTMX in Phase 1 — server-rendered pages with Alpine.js for progressive enhancement
- Sidebar behaviour: desktop fixed 240px, tablet (768–1023px) collapses to icon rail, mobile (<768px) hamburger drawer — all driven by Alpine.js state

### Data models
- **User**: custom model in `apps.accounts` with `role` enum (SUPERADMIN / ORG_ADMIN / STAFF_ADMIN); `AUTH_USER_MODEL = "accounts.User"` set before first migration — no other app migrates until `accounts/0001` exists
- **Organisation**: `status` field enum (ACTIVE / DISABLED / DELETED) — soft-delete sets status to DELETED, not a boolean flag; `number_of_stores` (allocation) + derived `stores_used` (count of linked active stores); org type enum: RETAIL / RESTAURANT / PHARMACY / SUPERMARKET
- **InvitationToken**: stores hash of TimestampSigner-generated token; `is_used` boolean; `expires_at` timestamp (48h from creation); FK to Organisation and to User (null until activated)
- Organisation Admin status (used in VORG-02): derived at query time — PENDING (token exists, unused, not expired), ACTIVE (token used), INVITATION_EXPIRED (token exists, unused, expired); no denormalised field

### Design system
- Brand tokens in `tailwind.config.js`: primary yellow `#FACC15`, primary black `#0A0A0A`, background gray `#FAFAFA`
- Layout: fixed sidebar (Primary Black background), top bar, main content area (Background Gray) — server-rendered Django templates
- All WCAG AA contrast enforced via Tailwind config; focus states use yellow ring; ARIA labels on all icon-only buttons; focus trap in modals handled by React (via `focus-trap-react` or equivalent)

### Claude's Discretion
- Exact Tailwind theme extension (spacing, typography scale, shadow tokens)
- Dockerfile multi-stage build details (base image layers, non-root user setup)
- docker-compose service health check implementations
- Vite entrypoint naming convention within `frontend/src/entrypoints/`
- Alpine.js version and whether loaded via CDN in dev or bundled via Vite

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements
- `CLAUDE.md` — Full architectural constraints: app layout under `apps/`, services/selectors pattern, query rules, Redis usage, email setup, pre-commit hooks, Ruff/mypy config, Docker conventions, CI/CD pipeline. This is the single most important reference for ALL implementation decisions.
- `.planning/REQUIREMENTS.md` — 50 v1 requirements with IDs; Phase 1 covers DSYS-01 through DSYS-08

### External specs
- `docs/Requirements_Phase1_Superadmin.docx` — Original requirements document (v1.0, April 2026); contains design detail for DSYS components beyond what REQUIREMENTS.md captures

### Key constraints from CLAUDE.md
- §3 File & Folder Structure — exact directory layout to follow (config/, apps/, templates/, static/, frontend/)
- §5 Services & Selectors Pattern — business logic lives in services/, queries in selectors/; views are thin
- §6 Query Optimization — strict no-N+1; CI query-count ceiling tests required
- §14 Pre-commit Rules — Ruff, mypy, bandit, djhtml, gitleaks all required from day one
- §17 Docker — multi-stage python:3.12-slim, non-root user, healthcheck endpoints /healthz/ and /readyz/

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- None yet — blank repo. Phase 1 creates everything from scratch.

### Established Patterns
- CLAUDE.md §3 defines the exact folder structure to follow
- CLAUDE.md §5 defines the services/selectors pattern all subsequent phases use
- CLAUDE.md §6 defines the query optimization and N+1 rules
- Tailwind brand tokens will be established here and reused across all phases

### Integration Points
- `config/settings/` — split settings package; `local.py` activates MailHog, Vite dev server; `production.py` activates SES, GCP Secret Manager
- `config/urls.py` — app URL includes go here; Phase 2+ adds auth URLs
- `apps/accounts/` — User model must exist and be migrated before any other app references it
- `frontend/` — Vite source root; `entrypoints/` per React widget; TypeScript

</code_context>

<specifics>
## Specific Ideas

- Sidebar active state: Primary Yellow `#FACC15` highlight; hover also yellow (from REQUIREMENTS DSYS-02)
- Sidebar logout item: bottom-pinned (not in the main nav list)
- Tables: horizontal scroll on tablet; stacked cards on mobile (DSYS-06) — Alpine.js state or pure CSS media query
- Confirmation popup that requires typing org name (DORG-01): React or Alpine.js controlled input with delete button disabled until value matches
- Password strength indicator referenced in ACTV-02 and PROF-02 — consistent implementation needed; establish the component in Phase 1's design system

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 01-foundation*
*Context gathered: 2026-04-22*
