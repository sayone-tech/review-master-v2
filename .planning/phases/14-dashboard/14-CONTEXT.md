# Phase 14: Dashboard — Context

**Gathered:** 2026-05-07
**Status:** Ready for planning

<domain>
## Phase Boundary

Replace the dashboard placeholder at `/admin/org/dashboard/` with a functional analytics page.
Org Admins, Managers, and Staff see: a filter bar (Region, Store, Date Range), a Top Performing
Outlets section (bar chart + highlights card, or "Your Store" single-shop variant), three KPI
cards (Total Reviews, Average Rating, Negative Reviews), and a Sentiment Distribution donut.

All read-only. No live-updating widgets. No action items widgets. No Superadmin dashboard.
Error pages (branded 404/500) are also in scope as self-contained templates.

</domain>

<decisions>
## Implementation Decisions

### Date Picker — Custom Range
- Custom range shows an **inline panel** that drops below the Date Range dropdown
- Panel contains two HTML `<input type="date">` inputs (From, To) styled with Tailwind — no date picker library
- An **Apply button** inside the panel triggers the fetch; prevents partial-state API calls (e.g. From filled but To empty)
- Panel closes on Apply, on clicking away, or on switching to a preset (7d/30d/90d)
- Validation (from > to, range > 365 days) fires on Apply, shown as an inline error below the inputs — not a toast

### 404 / 500 Error Pages
- **Standalone full-page layout** — no sidebar, no topbar, no shell template dependency
- Branded: platform logo (`logo/main_logo.png`), yellow/black palette, centered content on a white/light background
- **Same template structure** for both pages; only the code, title, and message differ:
  - 404: "404 — Page Not Found" + brief explanation + navigation button
  - 500: "500 — Something went wrong" + brief explanation + navigation button
- Navigation button logic (from requirements): authenticated user → Dashboard (`/admin/org/dashboard/`), unauthenticated → Login (`/accounts/login/`)
- Wired via Django's `handler404` and `handler500` in `config/urls.py`; templates at `templates/404.html` and `templates/500.html`

### Widget Island Structure
- **Single React island**: one `#dashboard-root` div in the Django template
- The island owns the React Query `QueryClientProvider`, filter state, and renders all 5 widgets
- Filter state flows down as props to each widget — no cross-island communication
- Widget directory: `frontend/src/widgets/dashboard/` following the established `api.ts` + `types.ts` + `useXxx.ts` + component files pattern
- Entrypoint: `frontend/src/entrypoints/dashboard.tsx` (consistent with existing entrypoint naming)

### Bootstrap Data
- Django injects **regions list + accessible shops list** via `<script type="application/json">` in the template
- This allows the filter bar (dropdowns) to render immediately without a loading state
- All 5 widget datasets are fetched via React Query on mount — they are NOT pre-rendered server-side
- Pattern: consistent with the Reviews page bootstrap approach

### Bar Chart Click Navigation
- Clicking a bar navigates in the **same tab** via `window.location.href`
- **Always resolve to absolute ISO dates**, even for presets:
  - "Last 30 days" → compute `from=YYYY-MM-DD` and `to=YYYY-MM-DD` at click time
  - Custom range → pass the already-absolute from/to values
- URL format: `/admin/org/reviews/?store={shop_id}&from={YYYY-MM-DD}&to={YYYY-MM-DD}`
- The Reviews page filter bar already accepts `?store` and date params; no Reviews page changes needed

### Claude's Discretion
- Loading skeleton design for KPI cards and chart areas
- Exact Tailwind spacing and typography within the established design system tokens
- Transition/animation timing for filter panel open/close
- How to handle the `accessible_shop_ids` empty-list edge case for Org Admins in the bootstrap payload
- Whether `sessionStorage` or a React ref holds the persisted filter state across route changes

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements
- `docs/Requirements_Phase4_Dashboard.docx` — Primary requirements doc. All acceptance criteria, filter scope rules, widget data definitions, API endpoint shapes, performance targets, and out-of-scope list. This is the binding spec.
- `.planning/REQUIREMENTS.md` — REQ-ID index of all 38 Phase 14 requirements (FILT-01–10, TOP-01–07, STORE-01–03, KPI-01–05, SENT-01–06, TECH-01–06, ERR-01–02)

### Architecture and Research
- `.planning/research/SUMMARY.md` — Stack additions (recharts + @tanstack/react-query), critical pitfalls, build order, conflict resolution (React Query chosen despite STACK.md note)
- `.planning/research/ARCHITECTURE.md` — Backend pattern: APIView + IsOrgScoped (NOT TenantScopedViewSet); DashboardFilterParams frozen dataclass; cache key design; ORM aggregation patterns; React island wiring

### Critical conventions from CLAUDE.md
- `CLAUDE.md` §3 — File/folder structure (apps/dashboard/ layout)
- `CLAUDE.md` §5 — Services/selectors pattern (selectors/aggregations.py, services/cache.py)
- `CLAUDE.md` §6 — No-N+1 policy; CaptureQueriesContext tests required on all list/aggregate endpoints
- `CLAUDE.md` §7.3 — Redis cache key convention: `{app}:{entity}:{id}:{variant}`
- `CLAUDE.md` §9 — Tenant scoping; Staff filtered by StaffAccessScope; org_id at base layer
- `CLAUDE.md` §13.2 — Channels scope discipline: NO live-updating widgets in Phase 14

### Prior phase patterns
- `templates/reviews/review_list.html` — Reference for how Django template mounts a React island with `<script type="application/json">` bootstrap data and a `#widget-root` div
- `templates/base_org.html` — Base template the dashboard page extends (sidebar, topbar, block structure)
- `frontend/src/widgets/action-items/api.ts` — Reference api.ts pattern (getCsrfToken, headers, ApiError, handle, buildQs)
- `frontend/src/widgets/action-items/useActionItems.ts` — Reference vanilla fetch hook pattern (pre-React Query baseline)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `frontend/src/lib/toast.ts` — Toast API: `{kind: 'success'|'error'|'info', title: string}`. Use for bar click error states if Reviews page navigation fails.
- `frontend/src/widgets/modal/Modal.tsx` — If filter panel needs a popover shell, this is the reference. More likely a custom inline Tailwind div.
- `frontend/src/widgets/data-table/DataTable.tsx` — NOT used in dashboard (no tabular data), but its error/empty/loading state pattern is the template to follow.
- `frontend/src/widgets/action-items/api.ts` — The `getCsrfToken()`, `headers()`, `ApiError`, `handle()` utilities are the canonical pattern for `apps/dashboard/api.ts`.

### Established Patterns
- **Widget directory layout**: `frontend/src/widgets/{name}/` with `api.ts`, `types.ts`, `use{Name}.ts`, individual component `.tsx` files, and an `index.ts` barrel. Dashboard follows the same layout under `frontend/src/widgets/dashboard/`.
- **Entrypoints**: `frontend/src/entrypoints/{name}.tsx` — single file that mounts the React root. Registered in `vite.config.ts` `build.rollupOptions.input`.
- **Bootstrap data**: Django view passes JSON context; template renders `<script type="application/json" id="dashboard-bootstrap">{{ bootstrap_json }}</script>`; React reads `document.getElementById('dashboard-bootstrap').textContent` on mount.
- **Vanilla fetch hooks (pre-React Query)**: existing widgets use `useState`/`useEffect`/`useCallback` pattern. Dashboard introduces React Query v5 — the `useQuery` API (`{ queryKey, queryFn, staleTime }` object form) is the v5 convention.
- **CSRF**: extracted from `document.cookie` matching `/csrftoken=([^;]+)/`. Dashboard API calls that are GET-only do not need CSRF headers — all dashboard endpoints are read-only.

### Integration Points
- `config/urls.py` — Add `path('api/v1/dashboard/', include('apps.dashboard.urls'))` and wire `handler404`/`handler500`
- `config/settings/base.py` — Add `'apps.dashboard'` to `INSTALLED_APPS`
- `templates/organisations/org_dashboard.html` — The existing placeholder to replace; extend `base_org.html`, add `#dashboard-root` div and bootstrap JSON script
- `frontend/vite.config.ts` — Add `dashboard: 'src/entrypoints/dashboard.tsx'` to `build.rollupOptions.input`
- Login redirect (`apps/accounts/views.py`, `CustomLoginView`) — Already redirects Org Admin/Manager/Staff to `/admin/org/dashboard/` from Phase 6; no change needed
- `apps/reviews/models.py` — The `Review` model; 3 new composite indexes go in a migration in `apps/reviews/migrations/`

</code_context>

<specifics>
## Specific Ideas

- Date picker inline panel: should feel like the existing filter bar on the Reviews page — compact, not a full modal. The two date inputs sit side-by-side in a small Tailwind card that appears below the Date Range select.
- Error pages should show the platform logo at the top (same `main_logo.png` used in emails and the login page), a large muted code number (404 or 500), a short human-readable message, and a single CTA button. No decorative illustrations needed.
- Bar chart threshold colors are hardcoded per spec: green `#22C55E` (≥4.0), amber `#F59E0B` (3.0–3.99), red `#EF4444` (<3.0) — these are the same color tokens used in the Sentiment Distribution donut.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within Phase 14 scope.

</deferred>

---

*Phase: 14-dashboard*
*Context gathered: 2026-05-07*
