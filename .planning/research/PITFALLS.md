# Domain Pitfalls

**Domain:** Multi-tenant SaaS — Django 6, three-role RBAC, Google Business Profile reviews
**Researched:** 2026-04-22 (v1.0) | Updated: 2026-04-27 (v0.2-org-admin milestone)
**Confidence:** HIGH (Django-specific C1–C7, M3–M6) | MEDIUM (OAuth popup M1–M2, encrypted-field migration M7)

---

## v0.2-org-admin Pitfalls (New — Added for Milestone Research)

These pitfalls are specific to the Organisation Admin module being added to the live v1.0 system. They address the eight features: OAuth popup flow, encrypted field storage, tenant-scoped permissions, StaffAccessScope junction model, InvitationToken rename, Region ID race condition, soft-delete with audit trail, and cross-tenant data leakage from new viewsets.

---

### NEW-C1: COOP Header Breaks the OAuth Popup's postMessage Channel

**What goes wrong:** The Django app ships `Cross-Origin-Opener-Policy: same-origin` (a HSTS/security-hardening default). The Google OAuth consent page at `accounts.google.com` opens in a popup. When the user approves, Google tries to call `window.opener.postMessage(...)` back to the parent tab — but COOP `same-origin` severs the `window.opener` reference entirely. The popup completes OAuth but the parent tab never receives the authorization code. The store connect flow silently fails with no error visible to the user.

**Why it happens:** The project already sets aggressive security headers (HSTS, CSP, X-Frame-Options — see CLAUDE.md §19). COOP `same-origin` is commonly added alongside those. Chrome 124+ and Firefox enforce COOP strictly for cross-origin popup communication. Google's own sign-in library began emitting "Cross-Origin-Opener-Policy policy would block the window.closed call" warnings in mid-2024.

**Consequences:** Store Google connection flow breaks silently in all COOP-hardened deployments. The popup appears to open and close normally; no JS error is surfaced unless devtools are open.

**Prevention:**
1. Set `Cross-Origin-Opener-Policy: same-origin-allow-popups` (not `same-origin`) on the shop OAuth initiation view's response. This preserves security benefits while allowing `postMessage` from cross-origin popups.
2. Do NOT set `COOP: same-origin-allow-popups` globally — apply it only to the `/shops/connect/google/` view via a targeted middleware or view-level response header.
3. On the Django callback view (`/shops/oauth/callback/`), after saving the token, render a minimal HTML page that calls `window.opener.postMessage({status: 'success', shop_id: ...}, window.location.origin)` and then `window.close()`. Do not redirect.
4. In the parent JS listener, verify `event.origin === window.location.origin` and `event.source === popupRef.current` before trusting the payload.
5. Provide a redirect fallback: if `window.opener` is null (popup blocked or Safari iOS PWA), fall back to a full-page redirect flow that stores OAuth state in session and redirects back to the shop detail page.

**Detection:** Console warning: "Cross-Origin-Opener-Policy policy would block the window.closed call" during Google auth. Popup closes; no `message` event fires in parent.

**Phase:** v0.2-org-admin, Shops module OAuth connection phase. Must be solved before any popup implementation begins.

---

### NEW-C2: postMessage Origin Not Verified — XSS → Token Theft

**What goes wrong:** The parent window listens for `window.addEventListener('message', handler)` without checking `event.origin`. Any cross-origin page (including attacker-controlled iframes or windows) can `postMessage` arbitrary data to the parent. The handler reads `event.data.shop_id` and calls an API endpoint to finalize the connection — without verifying that the message actually came from the OAuth callback URL.

**Why it happens:** Popup/postMessage flows are rarely covered in Django tutorials. Developers copy the `message` event listener pattern from docs without the origin guard.

**Consequences:** An attacker who can induce a user to visit a malicious page while the shop connect flow is in progress can inject a fake success message, causing the backend to attempt finalization with attacker-controlled parameters.

**Prevention:**
1. Always check `event.origin === window.location.origin` as the first statement in the message handler — reject anything else.
2. Also check `event.source === popupWindowRef` to confirm the message came from the specific popup window you opened, not another window.
3. On the backend OAuth callback view, do NOT trust any `shop_id` or org context from query parameters submitted via the popup. Use the `state` parameter (a signed nonce stored in the user's session at flow initiation) to reconstruct the shop context server-side.
4. The `state` parameter must be a `TimestampSigner`-signed value — same pattern already used for invitation tokens. Max age: 10 minutes for OAuth state.

**Detection:** `addEventListener('message', ...)` handler lacking `event.origin` check; `shop_id` passed as an OAuth state parameter directly (unsigned).

**Phase:** v0.2-org-admin, Shops OAuth. Wave 0 security scaffold must include signed state parameter before any OAuth URL generation code is written.

---

### NEW-C3: OAuth Refresh Token Race Condition — Concurrent Sync Jobs Both Hit `invalid_grant`

**What goes wrong:** Two concurrent review-sync jobs for the same shop both detect an expired access token and attempt to refresh simultaneously. Both call `google.refresh_access_token(refresh_token)`. The first call succeeds and Google rotates the refresh token (Google Business Profile API rotates refresh tokens on use if token rotation is enabled). The second call uses the now-invalid old refresh token and receives `invalid_grant`. The second job marks the shop connection as expired, sends a reconnect notification to the Org Admin, and discards the valid new tokens from the first call.

**Why it happens:** The project already uses Redis locks for sync jobs (CLAUDE.md §7.6), but that pattern guards `_do_sync()` not `_do_token_refresh()`. A separate token-refresh helper called outside the lock scope is vulnerable.

**Consequences:** Shops get incorrectly marked as disconnected after every token rotation. Org Admins receive false reconnect-required emails. High operational noise erodes trust.

**Prevention:**
1. Use a dedicated Redis lock keyed `lock:google_token_refresh:shop:{shop_id}` that covers the entire read-refresh-write cycle, not just the sync loop.
2. In the token refresh service: acquire the lock → re-fetch the shop's `access_token_expires_at` from the DB inside the lock → if another worker already refreshed (token now valid), skip the refresh call and use the updated token from DB.
3. Wrap the token write in `select_for_update()` inside `transaction.atomic()` to prevent concurrent writes from clobbering each other's results.
4. On `invalid_grant`, do NOT immediately mark the shop as disconnected. First check if a valid token pair was written to the DB in the last 60 seconds (another worker may have just refreshed). Only escalate to "reconnect required" after confirming no valid token exists.

**Detection:** Two sync jobs for the same shop running within seconds of each other during token expiry; `invalid_grant` errors correlating with successful refreshes in logs.

**Phase:** v0.2-org-admin, Shops module. Token refresh service and Redis lock scope must be reviewed in the same phase as the sync management command.

---

### NEW-C4: Cross-Tenant Data Leakage via New DRF Viewsets Missing get_queryset Scoping

**What goes wrong:** New viewsets for Shops, Regions, and Team members are added for the Org Admin module. Each viewset's `get_queryset()` calls a selector that was written without a hard `organisation=` filter — or the filter is optional (`org_id=None` returns all records). An Org Admin who discovers the API URL can enumerate another organisation's shops by guessing integer IDs, or retrieve them via list endpoints.

**This is the most common multi-tenant Django mistake.** The existing `OrganisationViewSet` is correctly scoped for Superadmin (returns all orgs, which is correct for that role). Developers copy the pattern to the new Org Admin viewsets without adding the `organisation=request.user.organisation` filter.

**Why it happens:** The existing selectors (e.g., `list_organisations_for_superadmin`) are intentionally unscoped. New selectors are written by referencing the existing ones as templates. The `has_permission` check (IsOrgAdmin) passes, but object-level scoping is silently missing.

**Consequences:** IDOR (Insecure Direct Object Reference) — an Org Admin can read, update, or soft-delete another org's shops/regions/users. Critical GDPR and SOC 2 violation. Undetectable without explicit cross-tenant tests.

**Important DRF nuance:** `has_object_permission` is never called for list endpoints and never called when `has_permission` returns False. The only reliable protection is queryset-level filtering, not object permissions.

**Prevention:**
1. Create `IsOrgScoped` permission class and `OrgScopedQuerysetMixin` in the same wave-0 scaffold commit before any Org Admin viewset exists.
   ```python
   class OrgScopedQuerysetMixin:
       def get_queryset(self):
           user = self.request.user
           if not user.organisation_id:
               return super().get_queryset().none()
           return super().get_queryset().filter(
               organisation_id=user.organisation_id
           )
   ```
2. Write separate selectors for Org Admin — never pass `organisation_id=None` to make filtering optional. A selector that can return all organisations is never used in an Org Admin context.
3. Add a mandatory CI test class: `TenantIsolationTest` — create Org A and Org B, log in as Org A's admin, assert zero results on all Org B resources via every list and detail endpoint.
4. `perform_create` in every Org Admin viewset must inject `organisation=request.user.organisation` — never accept `organisation_id` from `request.data`.

**Detection:** Selector functions with `organisation_id` as an optional parameter with `None` default; `Organisation.objects.all()` or unfiltered Shop/Region querysets in non-Superadmin code paths.

**Phase:** v0.2-org-admin, wave 0 scaffold. The mixin and isolation tests must exist before the first Org Admin viewset is written.

---

### NEW-C5: InvitationToken → UserInvitation Rename Breaks Live Token Lookups

**What goes wrong:** The migration renames the `accounts_invitation_token` table (or the Django model class) to `accounts_user_invitation`. Between the migration running and the new code deploying (Cloud Run rolling deploy with two container versions alive simultaneously), the old app instances still query `accounts_invitation_token`. If the table has been renamed, old instances throw `ProgrammingError: relation "accounts_invitation_token" does not exist`. Active invitation links in Org Admins' inboxes that click during the deploy window 404 or 500.

**Why it happens:** Cloud Run / GKE rolling deploys run old and new code simultaneously. Any migration that renames a table is incompatible with the old code, which still references the old name. This is not a hypothetical — the v1.0 app has live `accounts_invitation_token` rows with the existing `organisation_id` FK and `OneToOneField(invited_user)`. Changing either the table name or the FK structure without a backward-compatible intermediate step is destructive.

**Consequences:** Production downtime during deploy. Activation links sent before the migration become invalid. Resend creates tokens in the new table that the old code cannot find.

**Prevention — Three-step expand-contract pattern:**
1. **Step 1 (additive migration, deploy first):** Add the `purpose` column with `null=True`, default `'ORG_ADMIN_INVITE'`. Keep `db_table = 'accounts_invitation_token'`. Add `invited_by` and `accepted_at` fields as nullable. Do NOT rename the table yet. New code reads `purpose`, old code ignores the new column.
2. **Step 2 (data migration):** Backfill `purpose = 'ORG_ADMIN_INVITE'` for all existing rows. Make `purpose` non-null with a default. Still no table rename.
3. **Step 3 (rename, separate deploy):** Rename the Django model to `UserInvitation`. Use `SeparateDatabaseAndState` with `db_table = 'accounts_user_invitation'` in the database operations and `AlterModelTable` in state operations. Include `reverse_sql` for rollback. Only deploy this migration after all old code pods are retired.

**FK constraint note:** The existing `invited_user` `OneToOneField` will need to become a plain `ForeignKey` if multiple invitation types per user are needed (e.g., staff invitations). Changing a `OneToOneField` to a `ForeignKey` in PostgreSQL can leave a ghost unique constraint — verify with `EXPLAIN` and drop explicitly if present.

**Detection:** `ProgrammingError: relation "accounts_invitation_token" does not exist` in Sentry during a rolling deploy.

**Phase:** v0.2-org-admin. Must use three-step expansion. Do NOT combine steps into one migration.

---

### NEW-C6: Encrypted Field Migration — Plaintext Data Survives in Old Rows

**What goes wrong:** The existing `Store` model (or the new `Shop` model) stores Google refresh tokens and API keys as plaintext `CharField`s. Adding `encrypt=True` (via `django-cryptography`) via a Django migration changes the column type to `BinaryField` (or keeps it as a `CharField` but wraps with Fernet). The migration runs `ALTER TABLE`, but existing rows still contain plaintext data. The migration does not automatically re-encrypt old values. Every row written before the migration is silently readable as plaintext in the DB dump.

**Why it happens:** Developers assume that adding an encrypted field type in the model migrates the data. `django-cryptography`'s `ALTER TABLE` only changes the column type/constraint — it does not transform existing data. A separate data migration using `RunPython` is required to read-decrypt-re-encrypt every row.

**Consequences:** Partial encryption: new rows are encrypted, old rows are plaintext. A DB dump taken after the migration but before the backfill leaks all pre-migration tokens in plaintext. Worse, the encrypted field's `from_db_value` will attempt to decrypt plaintext ciphertext and raise a `cryptography.fernet.InvalidToken` exception, crashing every read of an old row.

**Prevention:**
1. Migration sequence:
   - Step 1: Add a new `BinaryField` (e.g., `refresh_token_encrypted`) as nullable alongside the existing `CharField` (`refresh_token`).
   - Step 2: Data migration — read `refresh_token` plaintext, encrypt with Fernet key from `SECRET_KEY`/GCP, write to `refresh_token_encrypted`.
   - Step 3: Make `refresh_token` nullable (no data loss). Deploy. Verify old `refresh_token` column empty.
   - Step 4: Drop `refresh_token` column.
2. Encryption key must come from GCP Secret Manager, not from `SECRET_KEY`. Tying encryption to `SECRET_KEY` means a key rotation wipes all encrypted tokens permanently — documented issue in `django-fernet-fields` (see Sources).
3. Use `MultiFernet` with two keys: `[new_key, old_key]`. Encrypt with `new_key`, decrypt accepts both. This enables key rotation without data loss.
4. The data migration must be batched: `Shop.objects.iterator(chunk_size=200)` — a single transaction on thousands of rows holds table locks and causes replication lag.

**Detection:** `InvalidToken` exceptions on reads after migration; `type(field.value)` is `str` not `bytes` for rows written before the encrypted migration.

**Phase:** v0.2-org-admin, Shops module encryption setup. Encryption key infrastructure must exist before any Shop model is created with OAuth tokens — add the key to GCP Secret Manager in wave 0.

---

### NEW-C7: Region ID Auto-Generation Race Condition — Duplicate IDs Under Concurrent Creates

**What goes wrong:** The Region `region_id` (e.g., `REG-001`, `REG-002`) is generated by counting existing regions for the organisation and incrementing: `count = Region.objects.filter(organisation=org).count(); region_id = f"REG-{count + 1:03d}"`. Two concurrent region-create requests for the same org both read `count = 3` and both generate `REG-004`. One INSERT succeeds; the other violates the `UNIQUE` constraint on `region_id` and raises `IntegrityError`.

**Why it happens:** `SELECT COUNT(*)` is not atomic with the subsequent `INSERT`. At the default PostgreSQL isolation level (`READ COMMITTED`), two transactions can both see the same count before either inserts.

**Consequences:** `IntegrityError` surfaces as a 500 to one of the two concurrent users. Even with retry logic, the experience is broken. Without the UNIQUE constraint, both get `REG-004`, which violates data integrity silently.

**Prevention:**
1. Use `select_for_update()` with an advisory lock or lock on a sentinel row. The simplest safe pattern:
   ```python
   @transaction.atomic
   def generate_region_id(org: Organisation) -> str:
       # Lock the organisation row to serialize concurrent region creates
       org_locked = Organisation.objects.select_for_update().get(pk=org.pk)
       count = Region.objects.filter(organisation=org_locked).count()
       return f"REG-{count + 1:03d}"
   ```
2. Add `UniqueConstraint(fields=["organisation", "region_id"])` to the `Region` model `Meta.constraints`. This is the safety net — the service-layer lock is the prevention, the DB constraint is the backstop.
3. Always wrap the entire `generate_region_id + Region.objects.create()` call inside the same `transaction.atomic()` block. The `select_for_update()` lock is only held for the duration of the transaction.
4. Do NOT use `max(region_id)` string parsing as an alternative — it breaks if a region ID is manually edited or deleted.

**Detection:** `IntegrityError: duplicate key value violates unique constraint "region_region_id_org_uniq"` under load tests with concurrent creates.

**Phase:** v0.2-org-admin, Regions module. Lock strategy and DB constraint must be in the Region model migration.

---

### NEW-C8: StaffAccessScope N+1 on Team List — Access Chips Trigger Per-User Queries

**What goes wrong:** The Team list shows each Staff Admin's access scope chips (e.g., "North Region", "Shop A", "Shop B"). The `StaffAccessScope` model has a `scope_type` field (`REGION | SHOP`) and nullable `region_id` / `shop_id` FKs. The Team list serializer has a `SerializerMethodField` that calls `user.access_scopes.all()` per user, then for each scope calls `scope.region` or `scope.shop` to get the name. This is N+1 + N+1: one query per user for scopes, then one query per scope for the name.

**Why it happens:** The nullable multi-type FK pattern on `StaffAccessScope` resists standard `prefetch_related` because the FK target is polymorphic. Developers default to `SerializerMethodField` with inline queries. Unlike `GenericForeignKey`, the two-nullable-FK pattern does not have built-in `prefetch_related` support for resolving both FK branches in batch.

**Consequences:** Team list with 50 staff members and 3 scopes each = 50 + 150 queries minimum. Violates the ≤5 query CI ceiling. P95 latency exceeds 400ms SLA on the first realistic dataset.

**Prevention:**
1. Use two separate `Prefetch` objects — one for scopes with `region_id__isnull=False` (prefetch with `select_related('region')`), one for scopes with `shop_id__isnull=False` (prefetch with `select_related('shop')`):
   ```python
   from django.db.models import Prefetch

   qs = User.objects.filter(
       organisation=org, role=User.Role.STAFF_ADMIN
   ).prefetch_related(
       Prefetch(
           'access_scopes',
           queryset=StaffAccessScope.objects.select_related('region', 'shop'),
           to_attr='prefetched_scopes',
       )
   )
   ```
2. In the serializer, access `instance.prefetched_scopes` (the `to_attr` list) — do not call `instance.access_scopes.all()`.
3. Add a query-count CI test: create 20 Staff Admins, each with 3 scopes, hit the Team list endpoint, assert `<= 4` queries.
4. The `StaffAccessScope` model must add `select_related('region', 'shop')` at the manager level as the default for any queryset that includes scope name display.

**Detection:** `access_scopes.all()` in a `SerializerMethodField`; no `prefetch_related('access_scopes')` in the Team list selector; query count test absent from `test_selectors.py`.

**Phase:** v0.2-org-admin, Team module. The `StaffAccessScope` selector must include the prefetch chain from day one — retrofitting it after the serializer is written is the most common failure mode.

---

### NEW-C9: Soft-Delete Cascade Breaks Audit Trail — Hard Deletes on Child Records

**What goes wrong:** `Shop` has `on_delete=models.CASCADE` pointing to `Region`. When a Region is soft-deleted (status set to `DELETED`), the cascade does not fire — CASCADE only fires on `DELETE` SQL. This is expected and correct. However, if an admin performs a direct hard delete on a Region (e.g., via the Django admin), the CASCADE hard-deletes all child `Shop` rows, destroying the audit trail of those shops and their Google OAuth tokens. Additionally, `StaffAccessScope` rows referencing the shop are silently hard-deleted.

**Why it happens:** The current `Organisation.soft_delete()` pattern (setting `status=DELETED`) is not enforced at the database or model layer. Any `region.delete()` call from Django admin or a misplaced service call bypasses the soft-delete logic entirely.

**Consequences:** Irreversible data loss. Shop history, review data, and OAuth token references destroyed. No recovery path without a DB backup.

**Prevention:**
1. Override `delete()` on the `Region` and `Shop` model to raise `PermissionError` or redirect to `soft_delete()`. This prevents accidental hard deletes at the ORM level.
2. For the Django admin, override `ModelAdmin.delete_queryset()` and `ModelAdmin.delete_model()` to call `soft_delete()` instead of `queryset.delete()`.
3. When a Region is soft-deleted: do NOT cascade-soft-delete its Shops automatically. Instead, block Region deletion if any active Shops are assigned (per requirements: "delete blocked when shops assigned"). Return a validation error listing the blocking shops.
4. `StaffAccessScope` rows referencing a soft-deleted Shop or Region should be retained (not deleted) — they serve as audit evidence of past access grants. Use `is_active` status instead.

**Detection:** `region.delete()` call without going through `soft_delete()`; Django admin with default `delete_model` on Region; `StaffAccessScope` with `on_delete=CASCADE` pointing to `Shop`.

**Phase:** v0.2-org-admin, Regions and Shops modules. Override `delete()` in the model and admin in the same PR as the model definition.

---

### NEW-C10: Popup Blocked on First Click — Safari and Mobile Browsers

**What goes wrong:** `window.open()` called inside an `async` function or inside a `Promise.then()` chain is treated as a programmatic popup (not user-initiated) by Safari, iOS browsers, and some Chrome popup-blocker configurations. The Google OAuth popup is blocked. The user sees nothing — no error, no popup, no fallback. The shop connect flow appears to do nothing on button click.

**Why it happens:** Browser popup-blocker heuristics require `window.open()` to be called in the synchronous call stack of a user gesture (a click handler). Any `await` or `.then()` before the `window.open()` call breaks this chain. The typical anti-pattern: button click → `await fetch('/shops/initiate-oauth/')` → `window.open(response.oauth_url)`. The `await` breaks the synchronous gesture chain.

**Consequences:** The Google Connect button is broken on Safari (desktop and iOS) and any browser with strict popup blocking. Affects a significant portion of users. No visible error.

**Prevention:**
1. Open the popup synchronously on button click before any async operations:
   ```javascript
   button.addEventListener('click', () => {
     // Open popup synchronously in gesture handler — no await before this
     const popup = window.open('about:blank', 'google_oauth', 'width=600,height=700');
     fetch('/shops/initiate-oauth/').then(res => res.json()).then(data => {
       popup.location.href = data.oauth_url;  // Assign URL after fetch resolves
     }).catch(() => popup.close());
   });
   ```
2. Implement a redirect fallback: if `popup === null` (popup was blocked), set `window.location.href` to the OAuth URL with `?flow=redirect` to trigger a full-page redirect flow.
3. On mobile (detect via `navigator.maxTouchPoints > 0` or user-agent), default to redirect flow — popup flows are unreliable on mobile browsers.

**Detection:** Safari console: "A popup window could not be opened" or popup `null` on the first click. No error surfaced in the application.

**Phase:** v0.2-org-admin, Shops OAuth frontend. The frontend popup implementation must handle this as a first-class requirement.

---

## v1.0 Pitfalls (Original — Preserved)

---

### C1: Custom User Model Defined After First Migration

**What goes wrong:** `AUTH_USER_MODEL` is added to settings after running the initial `migrate`. Django bakes `auth.User` references into contenttypes and early migration files. This is unrecoverable without wiping the database.

**Why it happens:** Developers scaffold the project, run `migrate` to test the DB connection, then add the custom User model in a second commit.

**Prevention:**
1. Define `apps/accounts/models.py` with `AbstractBaseUser`/`AbstractUser` subclass on day 0, before any `migrate` command
2. Set `AUTH_USER_MODEL = "accounts.User"` in `config/settings/base.py` in the same commit as the model
3. Document in Makefile: first-time setup creates the User model before any migrate

**Detection:** `OperationalError: no such table: accounts_user` when `auth.User` references appear in early migrations.

**Phase:** Must be resolved Phase 1, day 0. (RESOLVED in v1.0)

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

**Phase:** Establish `TenantScopedMixin` in Phase 1. All selectors must be role-segregated before Phase 2. (See also NEW-C4 for v0.2-specific expansion)

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

**Phase:** Phase 1. Treat as security-critical from day one. (RESOLVED in v1.0)

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

**Phase:** Phase 1 establishes the pattern with the organisations list. (See also NEW-C8 for StaffAccessScope specifics)

---

### C5: Superadmin Role Checking in UI Only, Not in DRF Viewset

**What goes wrong:** Template views use `{% if user.role == 'SUPERADMIN' %}` as access control. The underlying DRF API endpoint has `permission_classes = []` as a placeholder. An Org Admin queries the API URL directly.

**Consequences:** Privilege escalation. RBAC becomes theatre.

**Prevention:**
1. Every DRF viewset must have an explicit non-empty `permission_classes` list
2. Test each endpoint with each role: `200` for allowed, `403` for forbidden
3. Permission classes are the source of truth. Template conditionals are UX only

**Detection:** `permission_classes = []` or `[AllowAny]` on non-public endpoints; role checks inside view body logic.

**Phase:** Phase 1. Permission class architecture must be established before any endpoint ships. (RESOLVED in v1.0)

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

**Phase:** Phase 1 (React data table is a Phase 1 deliverable). (RESOLVED in v1.0)

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

**Phase:** Phase 1. SES production access request is a day-1 infrastructure task. (RESOLVED in v1.0)

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

**Phase:** Phase 1. Manager override must be in the same PR as the `deleted_at` field. (See NEW-C9 for cascade pitfalls in v0.2)

---

### M4: Store Allocation Counter Race Condition

**What goes wrong:** Two concurrent requests both read `org.allocated_stores`, compute the new value, and write back. One update is silently lost.

**Prevention:**
1. Use `F()` expressions: `Organisation.objects.filter(pk=org.pk).update(allocated_stores=F("allocated_stores") + delta)`
2. For conditional updates (cannot decrement below active store count): `select_for_update()` inside `transaction.atomic()`

**Detection:** `org.allocated_stores += 1` in any service function; no `transaction.atomic()` around count-based writes.

**Phase:** Phase 1. (RESOLVED in v1.0)

---

### M5: Staff Invitation Reuses Org Admin Token Flow Without Purpose Discrimination

**What goes wrong:** The new Staff Admin invitation flow is wired to the same `InvitationToken` (or `UserInvitation` after rename) model without a `purpose` field. An Org Admin invitation token URL and a Staff Admin invitation token URL are structurally identical. An attacker who intercepts a Staff Admin invitation URL attempts it against the Org Admin activation endpoint — the backend has no way to reject the mismatch. Worse: after adding the `purpose` enum, old Org Admin invitation tokens in the DB have `purpose=NULL`, causing `NullPointerError` at the activation view when checking `if token.purpose == Purpose.STAFF_INVITE`.

**Prevention:**
1. Add `purpose` field as a non-null `TextChoices` field with a default (`ORG_ADMIN_INVITE`) using the three-step expand-contract migration described in NEW-C5.
2. The activation view must verify: `if token.purpose != expected_purpose: raise ValidationError("Token type mismatch")`.
3. Tokens of the wrong purpose return the same opaque 400 as expired or used tokens — do not reveal the mismatch reason.
4. Backfill all existing rows to `purpose='ORG_ADMIN_INVITE'` in the data migration before making the field non-null.

**Detection:** `InvitationToken` activation view without `purpose` check; `purpose=NULL` rows in production after migration.

**Phase:** v0.2-org-admin, Team module. Must be addressed before any Staff invitation email is sent.

---

### M6: IsOrgAdmin Permission Missing `has_object_permission` — Allows Cross-Org PATCH/DELETE

**What goes wrong:** `IsOrgAdmin` is created as a view-level permission (`has_permission` returns True for any ORG_ADMIN role user). A `ShopViewSet` with `permission_classes = [IsOrgAdmin]` allows any Org Admin to `PATCH /api/v1/shops/42/` even if Shop 42 belongs to a different org. The permission class approves the role; object-level ownership is never checked.

**Why it happens:** `has_object_permission` in DRF's `BasePermission` returns `True` by default. Developers implement `has_permission` for role checks and assume object-level isolation is handled. It is not — unless `get_queryset()` is scoped (NEW-C4 prevention) AND object permissions are explicitly verified.

**Prevention:**
1. `IsOrgScoped` permission class must implement BOTH `has_permission` (role check) AND `has_object_permission` (verifies `obj.organisation_id == request.user.organisation_id`).
2. Never rely on `get_queryset()` scoping alone for mutation safety — a `PATCH /shops/{id}/` with a valid token bypasses `get_queryset()` and calls `get_object()` which triggers `has_object_permission`. The mixin and the permission class are both required.
3. The cross-tenant isolation test (NEW-C4) must include `PATCH` and `DELETE` verb tests with cross-org object IDs.

**Detection:** `IsOrgAdmin` or `IsOrgScoped` permission class without a `has_object_permission` override; `ShopViewSet` relying solely on queryset filtering for mutation safety.

**Phase:** v0.2-org-admin, wave 0 permission scaffold.

---

## Minor Pitfalls

| # | Pitfall | Prevention | Phase |
|---|---------|-----------|-------|
| m1 | Django settings module not set in CI (uses local.py, masks PostgreSQL-specific issues) | `DJANGO_SETTINGS_MODULE = config.settings.test` in CI env vars and `pyproject.toml` | Phase 1 CI setup (RESOLVED) |
| m2 | Tailwind CSS purge removing classes added by React components | Add `frontend/src/**/*.{ts,tsx}` to Tailwind content paths; run production build in CI | Phase 1 Tailwind + React setup |
| m3 | Forgot password leaks email existence via response timing | Always return identical 200 response body; add dummy `check_password` for non-existent users | Phase 1 auth (RESOLVED) |
| m4 | JSON fixtures breaking on migration squash | Use `factory-boy` factories exclusively — no JSON fixtures | Phase 1 day one (RESOLVED) |
| m5 | GCP Secret Manager key not available at migration time (encrypted field migration fails) | Run encrypted-field data migration as a management command separate from `manage.py migrate`; load key explicitly | v0.2 Shops encryption |
| m6 | Google refresh token has a 6-month inactivity expiry — shops unused for 6 months silently disconnect | Run a monthly `refresh_google_tokens` management command even if no reviews need fetching; log the `invalid_grant` and notify Org Admin | v0.2 Shops sync |
| m7 | `select_for_update()` raises `TransactionManagementError` when called outside `transaction.atomic()` | Always wrap service functions that use `select_for_update()` with `@transaction.atomic` decorator — never call them from non-transactional contexts | v0.2 Region ID generation, token refresh |
| m8 | Google OAuth consent scope change voids existing refresh tokens | If the app requests additional scopes in a new version, all existing refresh tokens are immediately invalid; must re-prompt all connected stores | v0.2+ scope changes |

---

## Phase-Specific Warning Table

| Topic | Pitfall | Mitigation |
|-------|---------|-----------|
| Custom User model (Phase 1, day 0) | Defined after first migration — unrecoverable | `AUTH_USER_MODEL` set before any `migrate`; enforce in onboarding checklist (RESOLVED) |
| Organisations list API (Phase 1) | N+1 on `stores` count + `created_by` name | `select_related("created_by")` + `annotate(store_count=Count("stores"))`; query-count CI test (RESOLVED) |
| Invitation flow (Phase 1) | Token replay race condition | `select_for_update()` + `transaction.atomic()` in activation view (RESOLVED) |
| Invitation flow (Phase 1) | SES sandbox blocks staging emails | Request SES production access at kickoff (RESOLVED) |
| Soft-delete (Phase 1) | Deleted orgs visible in active querysets | Override default manager in same PR as `deleted_at` field (RESOLVED) |
| Store allocation (Phase 1) | Counter race condition | `F()` expression or `select_for_update()` (RESOLVED) |
| React data table (Phase 1) | CSRF failures or JWT creep | Session auth + `X-CSRFToken` header; no JWT for embedded widgets (RESOLVED) |
| All API endpoints (Phase 1) | Role check in UI only | `permission_classes = [IsSuperadmin]` mandatory; test each role explicitly (RESOLVED) |
| v0.2 wave 0 scaffold | No tenant scoping mixin before first Org Admin viewset written | Create `OrgScopedQuerysetMixin` + `IsOrgScoped` + `TenantIsolationTest` in wave 0, before any feature code |
| v0.2 Shops OAuth (COOP) | `Cross-Origin-Opener-Policy: same-origin` breaks postMessage from Google popup | Set `same-origin-allow-popups` only on the OAuth initiation view; redirect fallback for Safari/mobile |
| v0.2 Shops OAuth (popup blocked) | Popup blocked on Safari and mobile when opened after `await` | Open `window.open()` synchronously before any async call; redirect fallback |
| v0.2 Shops OAuth (token refresh) | Concurrent refresh jobs invalidate each other's tokens | Redis lock covers read-refresh-write; re-check DB token freshness before escalating to "reconnect required" |
| v0.2 Shops encryption | Existing plaintext rows not re-encrypted after migration | Three-step migration: add column → data migration backfill → drop old column; use management command for backfill |
| v0.2 Shops encryption | Fernet key tied to SECRET_KEY — key rotation wipes all tokens | Use dedicated key from GCP Secret Manager; `MultiFernet([new, old])` for rotation |
| v0.2 InvitationToken rename | Table rename during rolling deploy breaks live old-code pods | Three-step expand-contract: add columns → backfill → rename in separate deploy |
| v0.2 InvitationToken rename | Old tokens with `purpose=NULL` crash activation view after migration | Backfill `purpose='ORG_ADMIN_INVITE'` before making field non-null |
| v0.2 Region ID generation | `SELECT COUNT` + INSERT race condition produces duplicate IDs | `select_for_update()` on org row + `UniqueConstraint` on (organisation, region_id) |
| v0.2 Team list | StaffAccessScope N+1 on access chips | `prefetch_related(Prefetch('access_scopes', queryset=..., to_attr='prefetched_scopes'))`; CI query-count test ≤4 |
| v0.2 Soft-delete | `region.delete()` hard-deletes child Shop rows via CASCADE | Override `delete()` on Region/Shop; block Region deletion if active Shops assigned |
| v0.2 Staff invitation | Staff token accepted by Org Admin activation endpoint (no purpose check) | `purpose` field on token; activation view verifies purpose before accepting |
| v0.2 All Org Admin viewsets | `IsOrgAdmin` checks role but not object ownership on mutations | `IsOrgScoped.has_object_permission` verifies `obj.organisation_id == user.organisation_id` |

---

## Sources

- [Django Multi-Tenant — raphaelm/django-scopes](https://github.com/raphaelm/django-scopes)
- [DRF Permissions — Object Level](https://www.django-rest-framework.org/api-guide/permissions/)
- [COOP: restrict-properties — Chrome for Developers](https://developer.chrome.com/blog/coop-restrict-properties)
- [COOP & Google OAuth Popup — Next.js Discussion](https://github.com/vercel/next.js/discussions/51135)
- [Google OAuth invalid_grant — Nango Blog](https://nango.dev/blog/google-oauth-invalid-grant-token-has-been-expired-or-revoked/)
- [Django Zero-Downtime Migrations — Loopwerk](https://www.loopwerk.io/articles/2025/safe-django-db-migrations/)
- [Django SeparateDatabaseAndState](https://typevar.dev/en/docs/django/ref/migration-operations/django.db.migrations.operations.SeparateDatabaseAndState)
- [Django Migrations Without Downtime — GitHub Gist](https://gist.github.com/majackson/493c3d6d4476914ca9da63f84247407b)
- [django-cryptography Migration Guide](https://django-cryptography.readthedocs.io/en/latest/migrating.html)
- [Fernet Key Loss → Inaccessible Data — django-fernet-fields Issue #13](https://github.com/jazzband/django-fernet-encrypted-fields/issues/13)
- [Avoid Django's GenericForeignKey — Luke Plant](https://lukeplant.me.uk/blog/posts/avoid-django-genericforeignkey/)
- [PostgreSQL Race Conditions with SELECT FOR UPDATE](https://on-systems.tech/blog/128-preventing-read-committed-sql-concurrency-errors/)
- [Cascading Soft Deletion in Django — usebutton.com](https://www.usebutton.com/post/cascading-soft-deletion-in-django)
- [Popup Blocker — Safari iOS postMessage](https://github.com/pocketbase/pocketbase/discussions/2429)
- [MDN: Cross-Origin-Opener-Policy](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Cross-Origin-Opener-Policy)
- [Sentry Database Migrations Guide](https://develop.sentry.dev/backend/application-domains/database-migrations/)
