# Project Research Summary

**Project:** v0.2-org-admin — Organisation Admin Module (Shops, Regions, Team)
**Domain:** Multi-tenant SaaS — Django 6, three-role RBAC, Google Business Profile integration
**Researched:** 2026-04-27
**Confidence:** HIGH

## Executive Summary

The v0.2-org-admin milestone adds the Organisation Admin control plane on top of the live v1.0 Superadmin system. The module introduces four bounded contexts — a shell/layout layer, a Regions module, a Shops module with Google Business Profile OAuth, and a Team management module — each with a strict dependency order driven by the data model graph. Experts building this class of multi-tenant, location-management SaaS establish tenant isolation infrastructure (scoped querysets, permission base classes, cross-tenant isolation tests) before writing any feature code, then build features in dependency order: shell → regions → shops (manual) → shops (OAuth) → team → team invitations. The Google OAuth popup flow is the highest-complexity and highest-risk unit; it must be treated as its own scoped work item with explicit fallbacks for COOP header breakage, popup blocking on Safari and mobile, and concurrent token-refresh races.

The recommended approach is to make the wave-0 scaffold commit (tenant scoping mixin, IsOrgScoped permission class, TenantIsolationTest CI gate, Fernet key in GCP Secret Manager, and the three-step InvitationToken expand-contract migration plan) the hard gate that blocks all feature work. From that foundation, regions and the Google integrations layer can be built in parallel since they have no mutual dependency. The Shops module consumes both, and the Team module consumes Shops and Regions for its scope-selection UI. Field-level encryption for OAuth refresh tokens must be wired into the Shop model from its first migration — retrofitting encryption is a multi-step downtime-risk migration per the expand-contract pitfall pattern.

The key risks fall into two categories: security architecture (cross-tenant data leakage via unscoped viewsets, postMessage origin spoofing, unsigned OAuth state parameters, missing object-level permission checks on mutations) and operational correctness (COOP header silently breaking the popup channel, concurrent token-refresh race producing false "reconnect required" notifications, Region ID generation race yielding duplicate IDs, and the InvitationToken table rename breaking live pods during rolling deploy). All ten new-pitfall entries have concrete prevention steps that must be implemented in the same work unit as the feature they protect — not deferred as hardening tasks.

---

## Key Findings

### Recommended Stack

The v1.0 stack requires seven new production packages and four new dev packages for this milestone. The single most important package decision is the replacement of `django-cryptography` (abandoned since 2022, no Django 6 support) with `django-fernet-encrypted-fields==0.3.1` from jazzband, which is verified against Django 6.0 and Python 3.12. For Google OAuth, the recommended approach is `google-auth-oauthlib` (server-side code exchange) combined with Google Identity Services in the frontend for the popup code flow — not django-allauth, which replaces the user authentication system and is wrong for per-shop API authorization. Google Places validation uses direct `httpx` calls rather than `google-maps-services-python`, which has a hard `requests` dependency and is heavier than needed.

The one unresolved compatibility question is `django-sequences==3.0`, which lists Django 3.2–5.0 in its tested matrix and has not yet confirmed Django 6 support. It is pure Python with no Django internals coupling, so the risk is low, but a smoke test in the Phase 6 setup is mandatory. A 30-line `select_for_update()` fallback on a `Sequence` model is ready if it fails.

**Core new technologies:**
- `django-fernet-encrypted-fields==0.3.1`: field-level Fernet encryption for OAuth refresh tokens and API keys — jazzband-maintained, Django 6.0 verified
- `google-auth==2.49.2` + `google-auth-oauthlib==1.3.1`: Google OAuth 2.0 server-side code exchange, popup flow
- `google-api-python-client==2.194.0`: Google Business Profile API calls with discovery caching
- `httpx==0.28.1`: HTTP client for Places API validation, testable via `pytest-httpx`
- `tenacity==9.1.4`: retry with exponential backoff for all Google API calls
- `django-sequences==3.0`: gapless per-org Region ID sequences (Django 6 compatibility needs smoke test)

**Settings additions required:**
- `FERNET_KEYS` loaded from GCP Secret Manager (dedicated key, never `SECRET_KEY`)
- `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET` from Secret Manager
- `GOOGLE_PLACES_API_KEY` backend-only, never exposed to frontend

### Expected Features

The features break cleanly by the dependency graph. The Org Admin shell is the universal prerequisite. Regions must exist before shops (region FK on Shop) and before team (scope multi-select at invite time). Manual shop creation must precede Google OAuth shop creation (OAuth adds to a record, not replaces it). Team must follow both regions and shops to populate scope selectors.

**Must have (table stakes — all P1):**
- Org Admin sidebar shell with role-aware navigation
- Dashboard landing with setup-state orientation and empty-state CTAs
- Regions: searchable list, create with auto-ID (REG-001 format), edit name, delete blocked when shops assigned
- Shops: searchable/filtered list with allocation counter, create via manual Place ID, activate/deactivate, edit
- Shop allocation counter enforcement — hard block at backend with `select_for_update()`, disabled button + explanatory banner in UI
- Google Business Profile OAuth popup flow — connect and reconnect, with COOP fallback polling and Safari/mobile redirect fallback
- Connection status badge per shop (NOT_CONNECTED / CONNECTED / EXPIRED)
- Team: invite Manager (full org) and Staff (region/shop scope), list with status badges, edit scope, enable/disable, remove
- Self-protection (cannot disable/remove yourself) and last-manager guard
- Team invitation email + context-aware acceptance page
- Profile page (reuse Superadmin services, swap shell context)

**Should have (differentiators — low-complexity, high value):**
- Popup-blocked polling fallback via Redis status key (HIGH operational value, required for OAuth reliability)
- Last-seen sync timestamp per shop (pairs naturally with connection status badge)
- Invitation context-aware acceptance copy ("You've been invited by X to join Y as Manager")

**Defer to future milestones:**
- Staff Admin dashboard — needs reviews module to be meaningful (Phase 3+)
- Google Business Profile name preview before shop save — secondary API call; ship after initial OAuth is stable
- Region detail page showing assigned shops — quality-of-life, not blocking
- Bulk shop CSV import — post-PMF
- Shop API key management — low immediate value

### Architecture Approach

The architecture follows the existing services/selectors pattern from CLAUDE.md with four additions: `IsOrgScoped` and `IsOrgAdmin` permission classes in `apps/accounts/permissions.py`, a `TenantScopedViewSet` base in `apps/common/views.py`, and two new bounded-context apps (`apps/regions/`, `apps/shops/`) alongside expansion of `apps/integrations/google/`. Import direction is strictly acyclic: `common <- accounts <- organisations <- regions <- shops <- integrations` (integrations receives data as parameters and returns plain values, importing no domain models). `StaffAccessScope` lives in `apps/accounts/` using string FK labels to `regions.Region` and `shops.Shop` to avoid circular imports. The OAuth callback is a Django `TemplateView` (not a DRF view) because it must render HTML to drive `window.opener.postMessage()`. The `/org/*` URL prefix cleanly separates new Org Admin views from the existing `/admin/*` Superadmin routes.

**Major components:**
1. `apps/accounts/permissions.py` — `IsOrgScoped`, `IsOrgAdmin`, `StaffAccessScope` model; all permission and access-scope logic owned here
2. `apps/common/views.py` — `TenantScopedViewSet`; cross-cutting base that injects `organisation_id` filter into every Org Admin queryset
3. `apps/regions/` — Region CRUD with gapless auto-ID generation via `select_for_update()` on the Organisation row
4. `apps/integrations/google/` — `OAuthFlow`, `BusinessProfileClient`, `PlacesAPI`, `exceptions`; pure integration layer with no domain model imports
5. `apps/shops/` — Shop CRUD, allocation enforcement, OAuth connection/reconnect, API key management; consumes integrations layer
6. `apps/accounts/services/team.py` — team invite, scope management, enable/disable/remove; extends existing invitation token infrastructure with `purpose` enum

### Critical Pitfalls

1. **Cross-tenant data leakage via unscoped viewsets (NEW-C4)** — The most common multi-tenant Django mistake. Create `TenantScopedViewSet` and `TenantIsolationTest` (covering list + PATCH + DELETE for both org contexts) in wave 0 before any Org Admin viewset is written. Never accept `organisation_id` from `request.data` in `perform_create`.

2. **COOP header breaks OAuth popup postMessage channel (NEW-C1)** — Setting `Cross-Origin-Opener-Policy: same-origin` globally (common security hardening) severs `window.opener` and silently breaks the Google connect flow. Set `same-origin-allow-popups` only on the OAuth initiation view; implement a polling fallback via a 30-second Redis key for when postMessage is unavailable.

3. **Popup blocked silently on Safari and mobile (NEW-C10)** — Calling `window.open()` inside an `async` function or `.then()` breaks the synchronous gesture chain required by Safari's popup blocker. Open `window.open('about:blank', ...)` synchronously before any `await`, then assign `popup.location.href` after the fetch resolves. Default to redirect flow on mobile.

4. **InvitationToken rename breaks live pods during rolling deploy (NEW-C5)** — A table rename mid-deploy causes `ProgrammingError` in old pods still using the original table name. Use the three-step expand-contract pattern: add columns with nulls -> backfill data -> rename in a separate deploy only after all old pods retire.

5. **Encrypted field migration leaves plaintext in old rows (NEW-C6)** — Adding `EncryptedTextField` does not re-encrypt existing rows. Use the four-step migration: add new nullable encrypted column -> data migration backfill (batched, `chunk_size=200`) -> make old column nullable -> separate deploy to drop it. The Fernet key must come from GCP Secret Manager, never `SECRET_KEY`.

6. **Region ID race condition — duplicate IDs under concurrent creates (NEW-C7)** — `SELECT COUNT` then INSERT is non-atomic. Lock the Organisation row with `select_for_update()` inside `@transaction.atomic` for the entire generate-and-insert operation. Back it with `UniqueConstraint(fields=["organisation", "region_id"])` as the DB-level safety net.

7. **StaffAccessScope N+1 on Team list (NEW-C8)** — The two-nullable-FK scope model resists standard `prefetch_related`. Use `Prefetch('access_scopes', queryset=StaffAccessScope.objects.select_related('region', 'shop'), to_attr='prefetched_scopes')`. Add a CI query-count test asserting <= 4 queries for 20 Staff Admins with 3 scopes each.

---

## Implications for Roadmap

### Phase 6: Shell, Data Model, and Security Scaffold
**Rationale:** The dependency graph makes data models the hard blocker for everything else. The security scaffold (tenant scoping mixin, permission classes, isolation tests) must exist before any Org Admin viewset is written — retrofitting it is the single most common source of data leakage bugs in multi-tenant Django.
**Delivers:** All migrations for User extensions, InvitationToken purpose enum (step 1 of 3-step expand-contract), Region, Shop, StaffAccessScope; `IsOrgAdmin`, `IsOrgScoped`, `TenantScopedViewSet`; Org Admin shell with full sidebar nav, dashboard page, profile page; URL skeleton with stub viewsets; Fernet key infrastructure in GCP Secret Manager.
**Addresses:** Org Admin shell (table stakes), profile page reuse, all permission classes
**Avoids:** NEW-C4 (cross-tenant leakage), NEW-C5 (InvitationToken rename), NEW-C6 (encryption key infrastructure), M6 (IsOrgAdmin missing object permissions)
**Research flag:** Standard patterns — skip phase research. All architecture decisions are documented in ARCHITECTURE.md with code-level detail.

### Phase 7: Regions Module
**Rationale:** Region is the lightest bounded context and a hard prerequisite for both Shops (region FK) and Team (scope multi-select). Building it first proves the `TenantScopedViewSet` pattern on a simple resource before the complexity of OAuth.
**Delivers:** `apps/regions/` with full services/selectors/views, `generate_region_id()` with `select_for_update()` on org row, Region list React widget (search, paginate, create modal, edit modal, delete with guard), `/org/regions/` URL, full test suite including query-count CI assertion.
**Addresses:** Regions CRUD (all table-stakes features), auto-generated Region IDs
**Avoids:** NEW-C7 (Region ID race condition), M7 (select_for_update outside transaction)
**Research flag:** Standard patterns — skip phase research. Pattern is fully specified in ARCHITECTURE.md Phase 7 build steps.

### Phase 8: Shops Module — Manual Creation and Google Integrations Layer
**Rationale:** The Google integrations layer (`apps/integrations/google/`) has no UI dependency and can be built in parallel with Phase 7 (start 8.1 while 7.x is in progress). Manual shop creation unblocks Staff scope assignment without the OAuth complexity. OAuth is a discrete sub-phase within Phase 8 that can be sequenced after the list/create/edit/deactivate surfaces are stable.
**Delivers:** `apps/integrations/google/` (client, oauth, places, exceptions); Shop model with Fernet-encrypted `google_refresh_token` field (four-step encryption migration); shop list with allocation counter, filter by region/status; manual Place ID creation with Places API validation; activate/deactivate; connection status badge; Google OAuth popup flow with COOP polling fallback and Safari/mobile redirect fallback; reconnect flow; `/org/shops/` URL; Shop React widget.
**Addresses:** Shops list, manual create, allocation enforcement, Google OAuth popup, reconnect, connection status badge
**Avoids:** NEW-C1 (COOP header), NEW-C2 (postMessage origin), NEW-C3 (token refresh race), NEW-C6 (encrypted field migration), NEW-C9 (soft-delete cascade), NEW-C10 (popup blocked on Safari), m5 (GCP key not available at migration time), m6 (6-month refresh token inactivity expiry)
**Research flag:** Needs focused sub-phase research on the Google OAuth popup COOP fallback and Safari synchronous-open pattern before coding begins. A minimal browser prototype validating the dual postMessage+polling path is recommended before integrating into the Shop modal.

### Phase 9: Team Module
**Rationale:** Team depends on both Regions and Shops being live so the scope multi-select is populated with real data. The InvitationToken purpose enum step 2 (backfill) and step 3 (rename, if pursued) must be completed before Staff invitation tokens can be issued.
**Delivers:** `apps/accounts/services/team.py` (invite, update scope, enable/disable, remove, resend); InvitationToken purpose enum step 2 backfill and non-null constraint; `TeamViewSet` (write = IsOrgAdmin, read = IsOrgScoped); team list React widget with scope chips; invite modal with Manager/Staff role selector and region/shop multi-select; edit scope modal; enable/disable/remove confirmations with self-protection and last-manager guards; `team_invitation.html` + `team_invitation.txt` email templates; purpose-aware acceptance view routing; `/org/team/` URL.
**Addresses:** Team invite, team list, scope management, invitation email + acceptance, self-protection + last-manager guard
**Avoids:** NEW-C8 (StaffAccessScope N+1), M5 (Staff token accepted by wrong activation endpoint), NEW-C5 (InvitationToken rename — step 2/3)
**Research flag:** Standard patterns — the team invitation and StaffAccessScope prefetch patterns are fully specified in ARCHITECTURE.md Phase 9 build steps. No new external dependencies.

### Phase Ordering Rationale

- Data models block everything: all migrations must exist before any viewset can be wired. The Phase 6 migration set (User extensions, InvitationToken purpose, Region, Shop, StaffAccessScope) must be a single ordered migration sequence since each depends on the previous.
- Security scaffold precedes features: `TenantScopedViewSet`, `IsOrgScoped`, and cross-tenant isolation tests in Phase 6 ensure no Org Admin viewset in Phases 7–9 can be written without the guard rails in place.
- Regions before Shops because Shop has a FK to Region; Shops before Team because Team scope selection references both.
- Google integrations layer (Phase 8, step 8.1) can overlap with Phase 7 since it has no dependency on Regions — this is the primary parallelism opportunity.
- The InvitationToken expand-contract spans all phases: step 1 (add nullable columns) in Phase 6, step 2 (backfill, make non-null) in Phase 9, step 3 (rename table) as a separate post-v0.2 deploy only if required.

### Research Flags

Needs focused pre-implementation research or prototype:
- **Phase 8 (Google OAuth popup):** The COOP polling fallback pattern and the synchronous `window.open('about:blank')` Safari workaround should be validated in a minimal browser prototype before being integrated into the Shop modal. The postMessage + polling dual-path adds frontend complexity that benefits from an isolated proof-of-concept.
- **Phase 8 (`django-sequences` Django 6 smoke test):** Run `get_next_value("test")` in a test against the Django 6.0.2 test database in Phase 6 setup. If it fails, implement the 30-line `select_for_update()` fallback before Phase 7 begins.

Standard patterns (skip research-phase):
- **Phase 6:** Permission classes, TenantScopedViewSet, shell, and migration patterns are fully specified with code in ARCHITECTURE.md.
- **Phase 7:** Region CRUD with `select_for_update()` ID generation is fully specified in ARCHITECTURE.md and PITFALLS.md.
- **Phase 9:** Team invitation and StaffAccessScope prefetch patterns are fully specified. All external dependencies already added in Phase 6/8.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | MEDIUM-HIGH | All packages verified on PyPI with Django 6.0/Python 3.12 compatibility except `django-sequences` (pure Python, LOW confidence on Django 6 test matrix — smoke test required). `django-fernet-encrypted-fields` is the definitive replacement for the abandoned `django-cryptography`. |
| Features | HIGH | Dependency graph is unambiguous. Priority calls are well-grounded: hard allocation enforcement (not soft-block), two hardcoded roles (not attribute-based RBAC), flat region hierarchy (not nested). All anti-feature exclusions have explicit rationale. |
| Architecture | HIGH | Derived from direct codebase reading of v1.0 source files. Import rules, URL structure, and existing patterns (postMessage bus, CustomEvent refresh, CSRF from cookie) are confirmed against live code, not inferred. OAuth callback view implementation is fully specified. |
| Pitfalls | HIGH (Django-specific) / MEDIUM (OAuth popup browser edge cases) | Django pitfalls are well-sourced from official Django/DRF docs and established migration guides. OAuth popup pitfalls (COOP, Safari popup blocking) sourced from Chrome developer docs and browser-specific issue threads — the patterns are correct but browser behaviour may evolve. |

**Overall confidence:** HIGH

### Gaps to Address

- **`django-sequences` Django 6 compatibility:** Must be smoke-tested in Phase 6 setup before committing to it for Region ID generation. The fallback implementation is defined and ready.
- **GIS popup + Safari/iOS behaviour:** The synchronous `window.open('about:blank')` workaround is the documented fix, but iOS Safari has additional restrictions in PWA contexts. QA must cover Safari desktop, Safari iOS, and Chrome iOS as distinct test cases.
- **Google Business Profile API approval status:** The GBP API requires Google application review for production access. This is a process dependency, not a code dependency — must be confirmed before Phase 8 ships to production.
- **Region ID format confirmation:** Whether to embed an org short code (`REG-ACME-001`) or use a scoped sequence (`REG-001`) needs a product-owner decision before Phase 7 begins.
- **Manager can manage team:** Whether Managers (not just Org Admins) can invite/edit/remove Staff affects the permission class composition on `TeamViewSet`. Confirm before Phase 9 service layer is written.
- **Deactivated shop and allocation counter:** Whether deactivating a shop frees a slot in the limit counter needs a business rule decision before the allocation enforcement service is coded in Phase 8.

---

## Sources

### Primary (HIGH confidence)
- Direct codebase reading — `apps/accounts/models.py`, `apps/accounts/permissions.py`, `apps/organisations/models.py`, `apps/organisations/views.py`, `config/urls.py`, `frontend/src/entrypoints/org-management.tsx`, `templates/partials/sidebar_org.html`
- jazzband/django-fernet-encrypted-fields — GitHub — Django 6.0 test matrix confirmed
- Google GIS popup code model docs — canonical popup flow pattern
- Google Business Profile OAuth docs — per-store OAuth requirements
- Chrome for Developers COOP restrict-properties — COOP behaviour with popups
- DRF Permissions Object Level — has_object_permission limitations
- PostgreSQL SELECT FOR UPDATE concurrency patterns

### Secondary (MEDIUM confidence)
- google-auth PyPI v2.49.2 — version and Python 3.12 compatibility confirmed
- google-api-python-client PyPI v2.194.0 — version confirmed
- httpx PyPI v0.28.1 — sync API, Python 3.12 compatible
- tenacity PyPI v9.1.4 — retry with exponential backoff
- Nango Blog — Google OAuth invalid_grant — refresh token race patterns
- EnterpriseReady RBAC Guide — two-role scope model validation
- Django Zero-Downtime Migrations — Loopwerk — expand-contract pattern

### Tertiary (LOW confidence)
- django-sequences PyPI v3.0 — Django 6 not yet in test matrix; pure Python; smoke test required
- Browser popup-blocking behaviour on Safari iOS — sourced from GitHub issue threads; may be version-dependent

---
*Research completed: 2026-04-27*
*Ready for roadmap: yes*
