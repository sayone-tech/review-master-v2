# Domain Pitfalls

**Domain:** Multi-tenant SaaS — Django 6, three-role RBAC, Google Business Profile reviews
**Researched:** 2026-04-22
**Confidence:** HIGH (Django-specific C1–C5, M3–M4) | MEDIUM (React/SES M1–M2)

---

## Critical Pitfalls

### C1: Custom User Model Defined After First Migration

**What goes wrong:** `AUTH_USER_MODEL` is added to settings after running the initial `migrate`. Django bakes `auth.User` references into contenttypes and early migration files. This is unrecoverable without wiping the database.

**Why it happens:** Developers scaffold the project, run `migrate` to test the DB connection, then add the custom User model in a second commit.

**Prevention:**
1. Define `apps/accounts/models.py` with `AbstractBaseUser`/`AbstractUser` subclass on day 0, before any `migrate` command
2. Set `AUTH_USER_MODEL = "accounts.User"` in `config/settings/base.py` in the same commit as the model
3. Document in Makefile: first-time setup creates the User model before any migrate

**Detection:** `OperationalError: no such table: accounts_user` when `auth.User` references appear in early migrations.

**Phase:** Must be resolved Phase 1, day 0.

---

### C2: Tenant Scoping Not Enforced at the Queryset Layer

**What goes wrong:** Org Admin and Staff Admin views filter by `organisation_id` in some viewsets but not all. One tenant reads another tenant's data.

**Why it happens:** Scoping is "remembered" per-developer rather than enforced structurally. Selectors written for Superadmin use are accidentally reused in Org Admin views.

**Consequences:** Cross-tenant data leakage — critical security vulnerability. GDPR/SOC 2 violation.

**Prevention:**
1. Create a `TenantScopedMixin` that overrides `get_queryset()` and injects `organisation_id=self.request.user.organisation_id` automatically
2. Write **separate** selector functions for Superadmin vs Org Admin — never share a selector with `organisation_id=None` as an optional parameter
3. Add a `TestTenantIsolation` test class: create two organisations, assert Org A's admin gets 0 results when requesting Org B's resources. Run on every list endpoint in CI

**Detection:** Selector functions with `organisation_id=None` as default; `Organisation.objects.all()` in non-Superadmin code paths.

**Phase:** Establish `TenantScopedMixin` in Phase 1. All selectors must be role-segregated before Phase 2.

---

### C3: Invitation Token Replay After Single-Use

**What goes wrong:** Three independent attack surfaces: (1) activation view omits DB lookup after `unsign()` succeeds, (2) race condition where two near-simultaneous requests both pass the "not used" check, (3) raw token stored in DB instead of a hash.

**Consequences:** Token replay allows attacker to activate an account twice. Raw token storage lets anyone with DB read access mint valid invitations.

**Prevention:**
1. Store `token_hash = sha256(raw_token)` in `InvitationToken` — never the raw token
2. In activation view: `InvitationToken.objects.select_for_update().get(token_hash=..., used_at__isnull=True)` inside `transaction.atomic()` — prevents race condition
3. `TimestampSigner.unsign(token, max_age=172800)` catches expired tokens before DB lookup
4. Return the same 400 error for `BadSignature`, `SignatureExpired`, and `DoesNotExist` — do not reveal which triggered

**Detection:** Activation view not wrapped in `transaction.atomic()`; missing `select_for_update()`; `InvitationToken.token` field (raw string) instead of `token_hash`.

**Phase:** Phase 1. Treat as security-critical from day one.

---

### C4: N+1 Queries Discovered Late

**What goes wrong:** List views pass unit tests but hammer the DB in staging. Common: a serializer accesses `instance.organisation.name` or `instance.stores.count()` inside a loop.

**Consequences:** P95 list endpoint latency exceeds 400ms SLA. DB CPU spikes proportional to page size.

**Prevention:**
1. Every list selector explicitly declares `select_related` and `prefetch_related` chains
2. Add `django-debug-toolbar` to `docker-compose.override.yml`; SQL panel enabled by default
3. Install `nplusone` in local and test settings with `NPLUSONE_RAISE = True`
4. Every list endpoint must have a `CaptureQueriesContext` test asserting a **fixed** query ceiling (e.g., `<= 5`) that does NOT scale with result count — this is the hard CI gate
5. `SerializerMethodField` that touches the DB is banned. Use `source=` on nested serializers backed by prefetched data
6. Use `annotate()` + `Count()` for counts — never `len()` or `.count()` inside a serializer

**Detection:** `SerializerMethodField` methods calling `instance.<relation>.all()` or `.count()`; selectors with `.all()` and no joins; CI missing query-count tests.

**Phase:** Phase 1 establishes the pattern with the organisations list.

---

### C5: Superadmin Role Checking in UI Only, Not in DRF Viewset

**What goes wrong:** Template views use `{% if user.role == 'SUPERADMIN' %}` as access control. The underlying DRF API endpoint has `permission_classes = []` as a placeholder. An Org Admin queries the API URL directly.

**Consequences:** Privilege escalation. RBAC becomes theatre.

**Prevention:**
1. Every DRF viewset must have an explicit non-empty `permission_classes` list
2. Test each endpoint with each role: `200` for allowed, `403` for forbidden
3. Permission classes are the source of truth. Template conditionals are UX only

**Detection:** `permission_classes = []` or `[AllowAny]` on non-public endpoints; role checks inside view body logic.

**Phase:** Phase 1. Permission class architecture must be established before any endpoint ships.

---

## Moderate Pitfalls

### M1: React Components — CSRF and Auth Inconsistency

**What goes wrong:** Developers hit CSRF 403 errors and reach for `@csrf_exempt` or add JWT alongside session auth.

**Prevention:**
1. Session auth only for Phase 1 — React widgets share the session cookie
2. Pass CSRF token via `data-csrf-token="{{ csrf_token }}"` attribute on the mount div
3. DRF's `SessionAuthentication` enforces CSRF automatically — never add `@csrf_exempt` to DRF views used by embedded widgets
4. Never add `TokenAuthentication` or JWT in Phase 1

**Detection:** `@csrf_exempt` on any DRF view; `TokenAuthentication` in `DEFAULT_AUTHENTICATION_CLASSES`; React using `localStorage` for auth state.

**Phase:** Phase 1 (React data table is a Phase 1 deliverable).

---

### M2: Amazon SES Sandbox Blocks All Pre-Launch Emails

**What goes wrong:** Application tested with MailHog locally. Staging deployed with real SES credentials. First invitation email fails because SES account is still in sandbox mode.

**Why it happens:** SES sandbox → production access request takes 24–72 hours and is forgotten until it blocks staging testing.

**Prevention:**
1. Request SES production access at project kickoff — not the day before launch
2. Verify at minimum three email addresses in SES sandbox to unblock staging immediately
3. Set up DKIM + SPF DNS records in the same sprint as SES setup
4. Catch `Exception` in `send_transactional_email()`, log with `exc_info=True`, store `failed_at` on invitation record

**Detection:** SES send quota at 200/day; invitation records with no `sent_at`; `ClientError: MessageRejected` in Sentry.

**Phase:** Phase 1. SES production access request is a day-1 infrastructure task.

---

### M3: Soft-Delete Records Leaking Into Active Querysets

**What goes wrong:** `deleted_at` field added but the default manager is not overridden. Deleted organisations appear in list views. Worse: a deleted org's Org Admin invitation can still be activated.

**Prevention:**
1. Override the default manager in the same PR as adding `deleted_at`:
   ```python
   class ActiveOrganisationManager(models.Manager):
       def get_queryset(self):
           return super().get_queryset().filter(deleted_at__isnull=True)

   class Organisation(TimeStampedModel):
       deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)
       objects = ActiveOrganisationManager()
       all_objects = models.Manager()  # escape hatch for admin/recovery
   ```
2. Add a test: create a soft-deleted org, assert `Organisation.objects.count()` returns 0
3. Invitation activation must verify `invitation.organisation.deleted_at is None`

**Phase:** Phase 1. Manager override must be in the same PR as the `deleted_at` field.

---

### M4: Store Allocation Counter Race Condition

**What goes wrong:** Two concurrent requests both read `org.allocated_stores`, compute the new value, and write back. One update is silently lost.

**Prevention:**
1. Use `F()` expressions: `Organisation.objects.filter(pk=org.pk).update(allocated_stores=F("allocated_stores") + delta)`
2. For conditional updates (cannot decrement below active store count): `select_for_update()` inside `transaction.atomic()`

**Detection:** `org.allocated_stores += 1` in any service function; no `transaction.atomic()` around count-based writes.

**Phase:** Phase 1.

---

## Minor Pitfalls

| # | Pitfall | Prevention | Phase |
|---|---------|-----------|-------|
| m1 | Django settings module not set in CI (uses local.py, masks PostgreSQL-specific issues) | `DJANGO_SETTINGS_MODULE = config.settings.test` in CI env vars and `pyproject.toml` | Phase 1 CI setup |
| m2 | Tailwind CSS purge removing classes added by React components | Add `frontend/src/**/*.{ts,tsx}` to Tailwind content paths; run production build in CI | Phase 1 Tailwind + React setup |
| m3 | Forgot password leaks email existence via response timing | Always return identical 200 response body; add dummy `check_password` for non-existent users | Phase 1 auth |
| m4 | JSON fixtures breaking on migration squash | Use `factory-boy` factories exclusively — no JSON fixtures | Phase 1 day one |

---

## Phase-Specific Warning Table

| Topic | Pitfall | Mitigation |
|-------|---------|-----------|
| Custom User model (Phase 1, day 0) | Defined after first migration — unrecoverable | `AUTH_USER_MODEL` set before any `migrate`; enforce in onboarding checklist |
| Organisations list API (Phase 1) | N+1 on `stores` count + `created_by` name | `select_related("created_by")` + `annotate(store_count=Count("stores"))`; query-count CI test |
| Invitation flow (Phase 1) | Token replay race condition | `select_for_update()` + `transaction.atomic()` in activation view |
| Invitation flow (Phase 1) | SES sandbox blocks staging emails | Request SES production access at kickoff |
| Soft-delete (Phase 1) | Deleted orgs visible in active querysets | Override default manager in same PR as `deleted_at` field |
| Store allocation (Phase 1) | Counter race condition | `F()` expression or `select_for_update()` |
| React data table (Phase 1) | CSRF failures or JWT creep | Session auth + `X-CSRFToken` header; no JWT for embedded widgets |
| All API endpoints (Phase 1) | Role check in UI only | `permission_classes = [IsSuperadmin]` mandatory; test each role explicitly |
| Org Admin module (Phase 2) | Tenant scoping missed on new selectors | `TenantScopedMixin` from Phase 1; cross-tenant isolation test on every endpoint |
| Google OAuth per-store (Phase 2+) | Refresh token stored unencrypted | `django-cryptography`/Fernet encryption at rest; key from GCP Secret Manager |
