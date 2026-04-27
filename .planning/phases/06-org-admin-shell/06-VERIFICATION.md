---
phase: 06-org-admin-shell
verified: 2026-04-27T00:00:00Z
status: passed
score: 5/5 must-haves verified
re_verification: null
gaps: []
human_verification:
  - test: "Log in as an Org Admin with a blank full_name — verify email prefix appears in welcome heading"
    expected: "Welcome, {email_prefix} visible in browser without whitespace artifacts"
    why_human: "The template rendering of whitespace-only full_name fallback cannot be confirmed programmatically without running the server"
  - test: "Visit /admin/org/dashboard/ with zero regions — confirm yellow banner renders with correct colours in browser"
    expected: "bg-yellow text-black banner with lightbulb icon and 'Create Region' CTA button visible"
    why_human: "CSS class rendering and visual appearance of yellow colour requires browser confirmation"
  - test: "Log in as an ORG_ADMIN via login form — verify redirect lands on /admin/org/dashboard/"
    expected: "Browser URL changes to /admin/org/dashboard/ after login; sidebar is visible"
    why_human: "Full login redirect flow requires session middleware behaviour confirmed in real browser or test client"
---

# Phase 6: Org Admin Shell Verification Report

**Phase Goal:** Org Admins have a working shell to navigate and a secure foundation that prevents all future viewsets from leaking data across tenant boundaries.
**Verified:** 2026-04-27
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | ORG_ADMIN lands on /admin/org/dashboard/ and sees personalised "Welcome, {Name}" with setup banner when no Regions exist; other roles redirected/403 | VERIFIED | `org_admin_dashboard` in `apps/organisations/views.py` extracts `first_name` via `user.full_name.split()[0]` or email prefix; `show_setup_banner` via `Region.objects.filter(organisation=user.organisation).exists()`; SUPERADMIN redirects, STAFF_ADMIN gets `HttpResponseForbidden` |
| 2 | Org Admin sidebar renders six items in correct order with yellow active state | VERIFIED | `templates/partials/sidebar_org.html` has 5 `_nav_item.html` includes (Dashboard, Shops, Regions, Team, Profile) plus logout form — all six items; icons verified: layout-dashboard, store, map-pin, users, user, log-out |
| 3 | Org Admin profile page at /admin/org/profile/ has edit-in-place name update and password change identical to Superadmin profile | VERIFIED | `org_profile`, `org_update_name_view`, `org_change_password_view` all gated by `@org_admin_required`, use `update_profile_name` and `svc_change_password` services; `org_profile.html` differs from `profile.html` in exactly 3 lines (extends + 2 url names) |
| 4 | TenantScopedViewSet and IsOrgScoped exist in apps/common/; cross-tenant isolation tests prove Org A admin cannot see Org B resources | VERIFIED | `apps/common/viewsets.py` has `TenantScopedViewSet.get_queryset()` with `filter(organisation_id=org_id)` and `qs.none()` fallback; `apps/common/permissions.py` has `IsOrgScoped` with `has_object_permission` checking `obj_org_id == user.organisation_id`; `test_isolation.py` verifies scoped dashboard context |
| 5 | All Phase 2–9 data migrations present and reversible; django-fernet-encrypted-fields installed; SALT_KEY loaded | VERIFIED | All 5 migrations exist: `regions/0001_initial`, `shops/0001_initial`, `accounts/0003_user_invitationtoken_v02`, `accounts/0004_staffaccessscope`, `common/0001_sequencecounter`; SALT_KEY in base/local/test/production settings; `django-fernet-encrypted-fields==0.4.0` and `django-sequences==3.0` pinned in `pyproject.toml`; `EncryptedTextField` from `encrypted_fields.fields` in `apps/shops/models.py` |

**Score:** 5/5 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `apps/regions/models.py` | Region model with org+region_id unique constraint | VERIFIED | `class Region(TimeStampedModel)` with `UniqueConstraint(fields=["organisation","region_id"], name="region_org_id_unique")` |
| `apps/shops/models.py` | Shop model with EncryptedTextField for google_refresh_token and api_key | VERIFIED | `from encrypted_fields.fields import EncryptedTextField`; both fields declared as `EncryptedTextField(null=True, blank=True)` |
| `apps/accounts/models.py` | StaffAccessScope + User extensions + InvitationToken.purpose/invited_for_role | VERIFIED | `class StaffAccessScope` with CheckConstraint `staff_scope_xor_region_shop`; `invited_by`, `invited_at`, `accepted_at` on User; `purpose` and `invited_for_role` nullable on InvitationToken |
| `apps/common/models.py` | SequenceCounter fallback model | VERIFIED | `class SequenceCounter(TimeStampedModel)` at line 21 with `db_table = "common_sequence_counter"` |
| `config/settings/base.py` | SALT_KEY + ENCRYPTED_FIELD_MODE + regions/shops/sequences in INSTALLED_APPS | VERIFIED | All present; no FERNET_KEYS references anywhere in config/ |
| `apps/accounts/permissions.py` | IsOrgAdmin DRF permission + org_admin_required decorator | VERIFIED | `class IsOrgAdmin` at line 27; `def org_admin_required` at line 42; returns `HttpResponseForbidden` (not redirect) for wrong-role users |
| `apps/common/permissions.py` | IsOrgScoped with has_object_permission override | VERIFIED | `class IsOrgScoped(BasePermission)` with `def has_object_permission` checking `obj_org_id == getattr(user, "organisation_id", None)` |
| `apps/common/viewsets.py` | TenantScopedViewSet base class | VERIFIED | `class TenantScopedViewSet(GenericViewSet)` with `filter(organisation_id=org_id)` and `qs.none()` when org_id is None |
| `apps/common/tests/fixtures.py` | two_orgs_two_admins + assert_query_ceiling fixtures | VERIFIED | Both fixtures defined; `two_orgs_two_admins` returns dict with org_a/org_b/admin_a/admin_b; `assert_query_ceiling` raises AssertionError with diagnostic query list |
| `apps/common/tests/test_isolation.py` | Cross-tenant isolation test scaffold | VERIFIED | Contains `test_org_admin_dashboard_scoped_to_own_organisation` and `test_two_admins_cannot_see_each_others_organisation`; verifies `response.context["organisation"].pk` scoped to correct org |
| `apps/common/tests/test_sequences_smoke.py` | django-sequences smoke test | VERIFIED | `from sequences import get_next_value` smoke test and `SequenceCounter` fallback test both present |
| `templates/partials/sidebar_org.html` | Six-item Org Admin sidebar | VERIFIED | Five `_nav_item.html` includes with correct hrefs (/admin/org/{dashboard,shops,regions,team,profile}/) plus logout form with `data-lucide="log-out"` |
| `apps/organisations/urls.py` | Dashboard alias + 3 stub page URLs | VERIFIED | `org_admin_dashboard` name preserved on legacy URL; `org_admin_dashboard_v02` alias; `org_regions`, `org_shops`, `org_team` names registered |
| `apps/organisations/views.py` | org_stub_view + personalised org_admin_dashboard | VERIFIED | `def org_stub_view` with `@org_admin_required`; `org_admin_dashboard` with `first_name` extraction and `show_setup_banner = not Region.objects.filter(organisation=user.organisation).exists()` |
| `templates/organisations/org_stub.html` | Stub template extending base_org.html | VERIFIED | Extends `base_org.html`; includes `components/empty_state.html` with section variables |
| `templates/organisations/org_dashboard.html` | Welcome card + conditional setup banner | VERIFIED | `Welcome, {{ first_name }}` heading; `Manage your shops, regions and team from here.` subtitle; `{% if show_setup_banner %}` yellow banner with `bg-yellow text-black` and CTA href `/admin/org/regions/`; `max-w-[560px]` container |
| `apps/accounts/views.py` (CustomLoginView) | Role-based post-login redirect | VERIFIED | `super().form_valid(form)` called first; SUPERADMIN redirects to `/admin/organisations/`; ORG_ADMIN+org redirects to `/admin/org/dashboard/`; STAFF_ADMIN falls back to `settings.LOGIN_REDIRECT_URL` |
| `apps/accounts/views.py` (org_profile views) | Three new ORG_ADMIN-only profile views | VERIFIED | `org_profile`, `org_update_name_view`, `org_change_password_view` all with `@org_admin_required`; use `update_profile_name` and `svc_change_password` services |
| `apps/accounts/urls.py` | Three new org profile URLs | VERIFIED | `org_profile`, `org_profile_update_name`, `org_profile_change_password` registered |
| `templates/accounts/org_profile.html` | Profile template extending base_org.html | VERIFIED | Extends `base_org.html`; both cards ("Your profile", "Change password") present; form actions use `org_profile_update_name` and `org_profile_change_password`; diff shows exactly 3 lines different from `profile.html` |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `StaffAccessScope.region/shop` in accounts/models.py | `regions.Region / shops.Shop` | String FK labels | WIRED | `"regions.Region"` at line 138, `"shops.Shop"` at line 145 — no module-level circular import |
| `apps/shops/models.py` | `encrypted_fields.fields.EncryptedTextField` | Import | WIRED | `from encrypted_fields.fields import EncryptedTextField` at line 6 |
| `accounts/migrations/0004_staffaccessscope.py` | `regions/0001_initial + shops/0001_initial` | dependencies list | WIRED | Both `("regions", "0001_initial")` and `("shops", "0001_initial")` at lines 12-13 |
| `apps/common/permissions.py IsOrgScoped.has_object_permission` | `obj.organisation_id == request.user.organisation_id` | Object-level check | WIRED | `obj_org_id == getattr(user, "organisation_id", None)` at line 36 |
| `apps/common/viewsets.py TenantScopedViewSet.get_queryset` | `request.user.organisation_id filter` | super().get_queryset().filter | WIRED | `qs.filter(organisation_id=org_id)` at line 26 |
| `apps/common/tests/conftest.py` | `apps/common/tests/fixtures.py` | star-import | WIRED | `from apps.common.tests.fixtures import (assert_query_ceiling, two_orgs_two_admins)` |
| `templates/partials/sidebar_org.html` | `/admin/org/{dashboard,shops,regions,team,profile}/` | _nav_item.html href | WIRED | All five hrefs confirmed in sidebar; old `/admin/org-dashboard/` absent from sidebar (new alias used) |
| `apps/organisations/urls.py path('admin/org/dashboard/')` | `org_admin_dashboard` view | URL alias | WIRED | Same view function as legacy URL; legacy name `org_admin_dashboard` preserved for `invite_accept_view` |
| `apps/accounts/views.py CustomLoginView.form_valid` | `redirect('/admin/org/dashboard/')` | Post-super() role check | WIRED | `user.role == User.Role.ORG_ADMIN` check at line 74 |
| `org_admin_dashboard view` | `apps/regions/models.Region` | `Region.objects.filter(...).exists()` | WIRED | `from apps.regions.models import Region` at line 33; `.exists()` used (not `.count()`) |
| `templates/organisations/org_dashboard.html setup banner CTA` | `/admin/org/regions/` | anchor href | WIRED | `href="/admin/org/regions/"` at line 21 of template |
| `apps/accounts/views.py org_profile views` | `update_profile_name + change_password` services | service function calls | WIRED | `update_profile_name(user=user, full_name=...)` and `svc_change_password(user=user, ...)` in both new views |
| `templates/accounts/org_profile.html` | `{% url 'org_profile_update_name' %}` | form action | WIRED | Confirmed at template line 33 and 77 |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| SHEL-01 | 06-03-PLAN | Org Admin sidebar: six items in order (Dashboard, Shops, Regions, Team, Profile top; Logout bottom-pinned) with icons and yellow active state | SATISFIED | `sidebar_org.html` has exact five `_nav_item.html` entries in specified order + logout form; `data-lucide` icons verified: layout-dashboard, store, map-pin, users, user, log-out; `_nav_item.html` applies `border-yellow text-yellow` via `is_active_route` |
| SHEL-02 | 06-04-PLAN | ORG_ADMIN lands on /admin/org/dashboard/ with "Welcome, {Name}" card | SATISFIED | `org_admin_dashboard` view extracts first name; template renders `Welcome, {{ first_name }}` with org name subtitle and "Manage your shops, regions and team from here." |
| SHEL-03 | 06-04-PLAN | Yellow info banner "Get started by creating your first region" with "Create Region" CTA when org has zero Regions | SATISFIED | `show_setup_banner = not Region.objects.filter(...).exists()` in view; template renders `bg-yellow text-black` banner with CTA linking to `/admin/org/regions/` |
| SHEL-04 | 06-05-PLAN | Profile page at /admin/org/profile/ reuses two-card layout (name edit-in-place, password change) | SATISFIED | Three views gated by `@org_admin_required`; `org_profile.html` extends `base_org.html`; diff shows exactly 3 lines different from `profile.html`; same service functions used |
| XMOD-05 | 06-01-PLAN, 06-02-PLAN | Query-count ceilings enforced via `assert_query_ceiling` fixture; TenantScopedViewSet + IsOrgScoped prevent cross-tenant data leakage | SATISFIED | `assert_query_ceiling` fixture in `apps/common/tests/fixtures.py`; used in dashboard test (ceiling 10); isolation tests verify org-scoped context; `TenantScopedViewSet` auto-filters by `organisation_id` |

All 5 required IDs (SHEL-01, SHEL-02, SHEL-03, SHEL-04, XMOD-05) are covered. No orphaned requirements found — all IDs declared in plan frontmatter are accounted for.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `templates/organisations/org_stub.html` | 6 | "This section is coming soon." | Info | Intentional — stub template is the Phase 6 design. Phases 7/8/9 will replace each stub URL's view. Not a code bug. |

No blockers or warnings found. The stub template is by design for Phases 7–9 to replace progressively.

### Human Verification Required

#### 1. Welcome heading with blank full_name

**Test:** Log in as an Org Admin user with `full_name=""` and email `alice@example.com`. Visit `/admin/org/dashboard/`.
**Expected:** Heading reads "Welcome, alice" (email prefix before @, no whitespace artifacts)
**Why human:** Template rendering of the fallback path (email prefix) is tested in pytest but the visual rendering in a real browser session confirms no unexpected whitespace around the heading

#### 2. Yellow setup banner visual appearance

**Test:** Visit `/admin/org/dashboard/` as an Org Admin whose organisation has zero Regions.
**Expected:** A distinctly yellow card appears above the welcome card containing "Get started by creating your first region" with a dark "Create Region" button; banner disappears after creating a Region
**Why human:** CSS class `bg-yellow` requires visual confirmation that the Tailwind colour token resolves to the expected brand yellow; also confirms the lightbulb icon loads via Lucide

#### 3. Post-login redirect in real browser

**Test:** Submit the login form at `/accounts/login/` with valid ORG_ADMIN credentials.
**Expected:** Browser URL changes to `/admin/org/dashboard/`; sidebar shows all six nav items
**Why human:** Session creation + redirect chain involves real HTTP responses that pytest confirms but browser flow confirms the full user experience

### Gaps Summary

No gaps. All observable truths verified. All artifacts exist, are substantive, and are correctly wired. All requirement IDs satisfied with evidence in the codebase.

The three human verification items above are confirmations of visual/browser behaviour — the code logic behind each has been verified programmatically.

---

_Verified: 2026-04-27_
_Verifier: Claude (gsd-verifier)_
