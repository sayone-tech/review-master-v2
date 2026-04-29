# Phase 9: Team - Research

**Researched:** 2026-04-29
**Domain:** Django team invitation, session management, DRF viewset guards, React multi-select, prefetch patterns
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Staff scope selectors (TEAM-06, TEAM-08)**
- Independent selection: Region multi-select and Store multi-select are fully independent. User can pick any combination of 0+ regions AND 0+ stores.
- Store list never narrows: always shows all active stores regardless of which regions are selected. XMOD-03 requires deactivated shops excluded; no additional narrowing logic.
- Validation: at least 1 region or 1 store must be selected for Staff role. Manager role requires no scope selections.

**Invitation acceptance UX (TEAM-17)**
- Manager → redirects to `/admin/org/dashboard/` after activation.
- Staff → redirects to a simple welcome page `/admin/org/welcome/` (placeholder): heading "Welcome to {OrgName}" + body "Your account is ready. Your administrator will let you know when your access is set up."
- Acceptance form: Name pre-filled from invited user's `full_name` (editable), Email locked (read-only), Password + confirm identical to existing ORG_ADMIN activation form.
- `invite_accept_view` must branch on `invitation.purpose`: `ORG_ADMIN` → existing `activate_account()` → `org_admin_dashboard`; `TEAM_MEMBER` → new `activate_team_member()` → role-based redirect.

**Row actions layout (TEAM-01, TEAM-13, TEAM-16)**
- Accepted members (Active/Disabled): Edit (pencil) + Remove (trash) inline icon buttons, always visible. Enabled toggle is a separate column.
- Pending members: Resend (envelope) + Remove (trash) inline. Edit hidden/disabled for Pending rows.
- Self-protection: Edit and Remove buttons disabled (with tooltip) on own row. Enabled toggle disabled on own row.
- No three-dot dropdown — inline buttons only.

**Solo-user banner (TEAM-05)**
- Position: above the table (table always renders).
- Copy: "You're the only team member. Invite others to collaborate." + inline "+ Add Team Member" link/button.
- Trigger: shows when `team_member_count == 0` (Org Admin is only member).
- Style: yellow info banner — `bg-yellow/10` with yellow left border or `bg-yellow-tint border border-yellow/40 rounded-md`.

### Claude's Discretion
- Exact session termination: `is_active=False` is sufficient (Django's `ModelBackend.authenticate()` checks `is_active` on every request). Session records can optionally be cleared from `django_session` table — implement if needed for instant termination.
- `activate_team_member()` service signature and placement (`apps/accounts/services/team.py`)
- Staff welcome page URL slug and template structure
- `StaffAccessScope` bulk create/replace strategy on edit (delete all + recreate vs diff)
- Exact `+N more` truncation threshold (suggest: show 2, overflow rest)
- Query-count ceiling value for team list (suggest: ≤5 queries for 20 members with 3 scopes)

### Deferred Ideas (OUT OF SCOPE)
- Staff Admin views (scoped review dashboard, review list/response filtered by assigned regions/stores) — future phase
- Audit log for team changes — future phase
- Bulk invite via CSV — not in Phase 9 scope
- Staff access scope based on role type (dynamic scope) — future enhancement
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| TEAM-01 | Team list columns: Member Name+Email, Role badge, Access chips, Status badge, Invited Date, Enabled toggle, Edit+Remove buttons | UI-SPEC surface 1 locked; ShopTable.tsx is the canonical inline-button pattern |
| TEAM-02 | Team list: search (Name+Email) + Region filter + Store filter (Store narrows when Region selected) | Confirmed: `list_shops(active_only=True)` already supports this; new `list_team_members()` selector needed |
| TEAM-03 | Team list pagination (10/25/50/100, default 10) | ShopsPagination pattern direct copy |
| TEAM-04 | Three stats cards: Total Members, Managers, Active Members | Django annotation via `Count()` with `filter=` on TeamViewSet list action |
| TEAM-05 | Solo-user info banner above table when team_member_count == 0 | Count from stats; frontend conditional render |
| TEAM-06 | Add Team Member modal: Name, Email, Role; Staff shows Region+Store multi-select; at least 1 required for Staff | No existing multi-select widget — new checkbox-list pattern as per UI-SPEC |
| TEAM-07 | Invite refreshes list, toast "Invitation sent to {email}.", sends 48h token email | `invite_member()` service + `send_team_invitation_email()` service |
| TEAM-08 | Edit modal: Name/Role/Scopes editable, Email locked; role change shows/hides scope section | Same pattern as TEAM-06 but pre-filled; scope replace strategy: delete-all + recreate |
| TEAM-09 | Edit success toast "Team member updated." + list refresh | Standard pattern |
| TEAM-10 | Disable: amber confirm, terminate sessions immediately, toast "{Name} disabled." | `disable_member()` service sets `is_active=False`; optional session flush from `django_session` table |
| TEAM-11 | Enable: one-click no confirm, toast "{Name} enabled." | `enable_member()` service sets `is_active=True` |
| TEAM-12 | Disabled user login sees "Your account has been disabled. Contact your administrator." | `CustomAuthenticationForm.error_messages["inactive"]` already exists — update copy string |
| TEAM-13 | Remove: red confirm, revoke access, terminate sessions, invalidate tokens, toast | `remove_member()` service; session flush; token invalidation |
| TEAM-14 | Self-protection: UI (disabled buttons+tooltips) AND API (403) | Custom guard in `perform_destroy`/action methods; UI from `data-current-user-id` |
| TEAM-15 | Last-Manager guard at API layer: cannot remove last Manager | Service-level check: `count(role=ORG_ADMIN, is_active=True) == 1` before remove |
| TEAM-16 | Resend invitation: blue confirm, invalidate old token, send new email | `resend_team_invitation()` service; invalidate via `filter(is_used=False).update(is_used=True)` |
| TEAM-17 | Acceptance page: pre-fill Name+locked Email; activate with role; auto-login; role-based redirect | `invite_accept_view` branching on `invitation.purpose`; new `activate_team_member()` service |
| TEML-01 | Team Invitation email: inviter name, org, role; Staff: region/store names; 48h CTA; plain-text fallback | `send_transactional_email()` with `template_base="emails/team_invitation"` |
| TEML-02 | Team Invitation Resent email: same + "replaces previous invitation" notice | Same service, `is_resend=True` context key, different subject |
| XMOD-03 | Deactivated shops excluded from Store multi-select in Add/Edit modals | `list_shops(active_only=True)` — `active_only` param already exists in `apps/shops/selectors/shops.py` |
</phase_requirements>

---

## Summary

Phase 9 is a feature-complete team management module. The codebase is well-prepared: all required Django models (`User`, `InvitationToken`, `StaffAccessScope`) are fully defined and migrated. The `InvitationToken.purpose` column is nullable (Phase 6 step 1 complete) and requires a data migration backfill + NOT NULL constraint (step 2) before TEAM_MEMBER tokens can be issued safely. The services/selectors/viewset pattern from Phases 7–8 applies directly. Three areas need careful planning-level understanding: the session termination approach, the `StaffAccessScope` prefetch pattern flowing through DRF serializers, and the `invite_accept_view` branching.

**Session engine:** No `SESSION_ENGINE` is set in `base.py` or `production.py`, so Django's default `django.contrib.sessions.backends.db` (database sessions) is in use. Sessions are stored in the `django_session` table. The CONTEXT.md decision confirms that setting `is_active=False` is sufficient — Django's `ModelBackend` checks `is_active` on every authenticated request, so the user is blocked on their next request even without flushing session rows. For "instant termination" semantics, the `django_session` table can be queried and matched rows deleted, but this is an optional enhancement. TEAM-10 and TEAM-13 requirements can be satisfied by `is_active=False` alone.

**Prefetch pattern:** `Prefetch('access_scopes', queryset=StaffAccessScope.objects.select_related('region', 'shop'), to_attr='prefetched_scopes')` means the serializer MUST read `instance.prefetched_scopes` (a plain Python list from `to_attr`) rather than `instance.access_scopes.all()` (which would issue a new query per member, bypassing the prefetch).

**Primary recommendation:** Implement `apps/accounts/services/team.py` as the single service module, `apps/accounts/selectors/team.py` as the read module, `TeamViewSet` in `apps/accounts/views.py`, React widget at `frontend/src/widgets/team-management/`, and two email template pairs at `templates/emails/team_invitation.{html,txt}` and `templates/emails/team_invitation_resent.{html,txt}`.

---

## Standard Stack

### Core (all already installed — no new dependencies required)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Django | 6.0.x | ORM, migrations, sessions, views | Project baseline |
| Django REST Framework | latest | TeamViewSet, serializers, pagination | Project baseline |
| django.contrib.sessions.backends.db | built-in | Session storage (default — no SESSION_ENGINE set) | Confirmed by settings inspection |
| factory-boy | installed | `TeamMemberFactory`, `InvitationTokenFactory` | Existing factories.py pattern |
| pytest-django | installed | Test suite | Project baseline |

### No New Dependencies

The entire phase is implementable with the existing dependency set. No new packages are needed.

**Confirmed by `base.py` inspection:** No `SESSION_ENGINE` key is set → Django defaults to `django.contrib.sessions.backends.db` (database sessions, `django_session` table).

---

## Architecture Patterns

### Recommended Project Structure

New files for Phase 9:

```
apps/accounts/
├── services/
│   ├── team.py           # NEW: invite_member, activate_team_member, update_member,
│   │                     #      enable_member, disable_member, remove_member,
│   │                     #      resend_team_invitation
│   └── profile.py        # existing
├── selectors/            # CREATE THIS DIRECTORY
│   └── team.py           # NEW: list_team_members, get_team_stats
├── exceptions.py         # NEW: SelfProtectionError, LastManagerError
├── migrations/
│   └── 0005_invitationtoken_purpose_backfill.py  # NEW: data migration + NOT NULL

frontend/src/widgets/team-management/
├── types.ts              # TeamMemberRow, TeamFilterParams, TeamListResponse
├── api.ts                # CSRF + fetch — copy shop-management/api.ts pattern exactly
├── useTeam.ts            # React hook — copy useShops.ts pattern
├── TeamTable.tsx         # inline icon buttons per UI-SPEC Surface 1
├── TeamModals.tsx        # CustomEvent subscriptions + modal orchestration
├── AddTeamMemberModal.tsx
├── EditTeamMemberModal.tsx
├── DisableMemberModal.tsx
├── RemoveMemberModal.tsx
├── ResendMemberInviteModal.tsx
├── RoleBadge.tsx
├── AccessChips.tsx
├── TeamStatsCards.tsx
├── EnabledToggle.tsx
└── TeamEmptyState.tsx

frontend/src/entrypoints/
└── team-management.tsx   # Mount TeamTable + TeamModals into separate roots

templates/
├── team/
│   └── team_list.html    # Django template — mounts team-management entrypoint
├── accounts/
│   └── team_invite_accept.html   # extends auth_base.html
└── emails/
    ├── team_invitation.html + .txt
    └── team_invitation_resent.html + .txt
```

### Pattern 1: InvitationToken Purpose Backfill — Expand-Contract Step 2

**What:** Two-operation migration: data migration (RunPython backfill) followed by schema migration (AlterField to remove null=True).

**When to use:** The `purpose` column is currently `null=True, blank=True` (Phase 6 step 1). All existing rows were created by `create_organisation()` which never set `purpose` — they are all `ORG_ADMIN` invites. Step 2 backfills them and adds the NOT NULL constraint.

**Safe order of operations:**
1. Single migration file with two operations: `RunPython(backfill)` first, then `AlterField(null=False)`.
2. Backfill sets `purpose='ORG_ADMIN'` and `invited_for_role='ORG_ADMIN'` on ALL rows where `purpose IS NULL`.
3. After migration, `InvitationToken.objects.filter(purpose__isnull=True).count()` must be 0 before AlterField runs (RunPython is transactional — Django wraps it in an atomic block by default).
4. No in-flight token risk: existing tokens already have `is_used=True` (consumed at org activation) or were created by resend flows. Any token with `is_used=False` is still valid — backfilling `purpose='ORG_ADMIN'` on it does not affect its token_hash or expires_at.

**Example:**
```python
# apps/accounts/migrations/0005_invitationtoken_purpose_backfill.py
from django.db import migrations, models


def backfill_purpose(apps, schema_editor):
    InvitationToken = apps.get_model("accounts", "InvitationToken")
    InvitationToken.objects.filter(purpose__isnull=True).update(
        purpose="ORG_ADMIN",
        invited_for_role="ORG_ADMIN",
    )


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0004_staffaccessscope"),
    ]

    operations = [
        migrations.RunPython(backfill_purpose, reverse_code=migrations.RunPython.noop),
        migrations.AlterField(
            model_name="invitationtoken",
            name="purpose",
            field=models.CharField(
                max_length=20,
                choices=[
                    ("ORG_ADMIN", "Org Admin Setup"),
                    ("TEAM_MEMBER", "Team Member Invitation"),
                ],
                db_index=True,
            ),
        ),
        migrations.AlterField(
            model_name="invitationtoken",
            name="invited_for_role",
            field=models.CharField(
                max_length=20,
                choices=[
                    ("SUPERADMIN", "Superadmin"),
                    ("ORG_ADMIN", "Org Admin"),
                    ("STAFF_ADMIN", "Staff Admin"),
                ],
            ),
        ),
    ]
```

**Note on noqa comment:** After `AlterField`, remove the `# noqa: DJ001` comment from `models.py` `purpose` and `invited_for_role` fields — null=True is gone.

### Pattern 2: StaffAccessScope Prefetch through DRF Serializer

**What:** Use `to_attr='prefetched_scopes'` in `Prefetch()`. The serializer reads `getattr(instance, 'prefetched_scopes', None)` — NOT `instance.access_scopes.all()`.

**Why critical:** Calling `instance.access_scopes.all()` in a serializer bypasses the prefetch and issues 1 query per team member (N+1). With `to_attr`, Django stores the prefetched result as a plain Python list attribute on each User instance.

**Example (selector):**
```python
# apps/accounts/selectors/team.py
from django.db.models import Prefetch, Q, QuerySet

from apps.accounts.models import StaffAccessScope, User


def list_team_members(
    *,
    organisation_id: int,
    search: str = "",
    region_id: int | None = None,
    shop_id: int | None = None,
) -> QuerySet[User]:
    qs = (
        User.objects
        .filter(
            organisation_id=organisation_id,
            role__in=[User.Role.ORG_ADMIN, User.Role.STAFF_ADMIN],
        )
        .select_related("invited_by")
        .prefetch_related(
            Prefetch(
                "access_scopes",
                queryset=StaffAccessScope.objects.select_related("region", "shop"),
                to_attr="prefetched_scopes",
            )
        )
    )
    if search:
        qs = qs.filter(
            Q(full_name__icontains=search) | Q(email__icontains=search)
        )
    if region_id is not None:
        qs = qs.filter(access_scopes__region_id=region_id)
    if shop_id is not None:
        qs = qs.filter(access_scopes__shop_id=shop_id)
    return qs.order_by("-invited_at", "-created_at")
```

**Example (serializer reading from to_attr):**
```python
class StaffAccessScopeSerializer(serializers.ModelSerializer):
    region_name = serializers.CharField(source="region.name", allow_null=True)
    region_region_id = serializers.CharField(source="region.region_id", allow_null=True)
    shop_name = serializers.CharField(source="shop.name", allow_null=True)

    class Meta:
        model = StaffAccessScope
        fields = ["id", "scope_type", "region", "region_name", "region_region_id",
                  "shop", "shop_name"]


class TeamMemberReadSerializer(serializers.ModelSerializer):
    access_scopes = serializers.SerializerMethodField()

    def get_access_scopes(self, instance):
        # CRITICAL: read from prefetched_scopes (to_attr result), not .all()
        scopes = getattr(instance, "prefetched_scopes", None)
        if scopes is None:
            scopes = list(
                instance.access_scopes.select_related("region", "shop").all()
            )
        return StaffAccessScopeSerializer(scopes, many=True).data
```

### Pattern 3: Session Termination for Disable/Remove

**What:** Setting `user.is_active = False` immediately prevents future authentication via Django's `ModelBackend`. The user is blocked on their NEXT request. For "instant termination" semantics, additionally flush `django_session` rows for that user.

**Confirmed SESSION_ENGINE:** `base.py` has no `SESSION_ENGINE` key → default is `django.contrib.sessions.backends.db`. Sessions live in the `django_session` table.

**Session flush approach (database sessions):**

Django's `Session` model stores encoded session data in the `session_data` column. Django's `Session.get_decoded()` method decodes it and returns the session dict. The key `_auth_user_id` holds the authenticated user's pk as a string (set by Django's `login()` call).

```python
# apps/accounts/services/team.py
from django.contrib.sessions.models import Session
from django.utils import timezone


def _flush_user_sessions(user_pk: int) -> None:
    """Delete all active django_session rows for this user (database session backend).

    Scans active sessions and matches those belonging to user_pk via get_decoded().
    Non-fatal: if session flush fails, is_active=False still blocks future logins.
    """
    active_sessions = Session.objects.filter(expire_date__gte=timezone.now())
    to_delete = []
    for session in active_sessions:
        try:
            data = session.get_decoded()
            if data.get("_auth_user_id") == str(user_pk):
                to_delete.append(session.pk)
        except Exception:
            pass  # corrupted session data — skip
    if to_delete:
        Session.objects.filter(pk__in=to_delete).delete()
```

**Performance note:** The active session scan is acceptable for admin operations (infrequent, initiated by Org Admin). This product will never have more than a few hundred concurrent sessions per organisation tier. The CONTEXT.md decision already authorises skipping the flush if not needed (`is_active=False` is sufficient).

### Pattern 4: invite_accept_view Purpose Branching

**Current implementation (apps/accounts/views.py):** The view calls `activate_account()` unconditionally and redirects to `org_admin_dashboard`. After Phase 9:

```python
# apps/accounts/views.py — extended invite_accept_view POST handler

if request.method == "POST":
    form = ActivationForm(request.POST)
    if form.is_valid():
        if invitation.purpose == InvitationToken.Purpose.TEAM_MEMBER:
            from apps.accounts.services.team import activate_team_member
            try:
                user = activate_team_member(
                    invitation=invitation,
                    full_name=form.cleaned_data["full_name"],
                    password=form.cleaned_data["password1"],
                )
            except ValidationError:
                return render(request, "accounts/invite_error.html", {"message": ACTV05_COPY})
            login(request, user)
            if user.role == User.Role.STAFF_ADMIN:
                return redirect(reverse("org_welcome"))   # new stub URL
            return redirect(reverse("org_admin_dashboard"))
        else:
            # ORG_ADMIN path — existing unchanged
            from apps.organisations.services.organisations import activate_account
            try:
                user = activate_account(
                    invitation=invitation,
                    full_name=form.cleaned_data["full_name"],
                    password=form.cleaned_data["password1"],
                )
            except ValidationError:
                return render(request, "accounts/invite_error.html", {"message": ACTV05_COPY})
            login(request, user)
            return redirect(reverse("org_admin_dashboard"))
```

**`activate_team_member()` service:** Differs from `activate_account()` in that it:
1. Creates the user with `role=invitation.invited_for_role` (not hardcoded ORG_ADMIN)
2. Updates the pre-existing User row (created at invite time) instead of creating a new one
3. Sets `accepted_at=timezone.now()` and flips `is_active=True`

**Key architectural note:** The `invite_member()` service creates the User row at invitation time (with `is_active=False` and no usable password), so the Pending row appears in the team list immediately. The activation step then updates the existing User row rather than creating a new one. This is the opposite of the ORG_ADMIN flow where `activate_account()` creates the User at activation time.

**Form pre-fill for TEAM_MEMBER:** The view passes `initial={'full_name': invitation.invited_user.full_name}` to the form. The template renders the email from `invitation.invited_user.email` (not `invitation.organisation.email` as in the ORG_ADMIN flow).

### Pattern 5: Self-Protection and Last-Manager Guard

**Where:** Both in the ViewSet action methods (API layer) and in the React UI (disabled state via `data-current-user-id`).

**API pattern — self-protection (403):**
```python
# In TeamViewSet custom actions (destroy, disable, etc.)
def destroy(self, request, pk=None):
    member = self.get_object()
    if member.pk == request.user.pk:
        return Response(
            {"detail": "You cannot remove yourself."},
            status=status.HTTP_403_FORBIDDEN,
        )
    remove_member(member=member, removed_by=request.user)
    return Response(status=status.HTTP_204_NO_CONTENT)
```

**API pattern — last-manager guard (403):**
```python
# In remove_member() service
manager_count = User.objects.filter(
    organisation_id=member.organisation_id,
    role=User.Role.ORG_ADMIN,
    is_active=True,
).count()
if manager_count <= 1 and member.role == User.Role.ORG_ADMIN:
    raise LastManagerError("Cannot remove the last Manager.")
```

**HTTP codes:** Use `HTTP_403_FORBIDDEN` for both self-protection and last-manager violations (matches CONTEXT.md spec "API layer 403"; simpler frontend error handling than mixing 403 and 409).

**Exception classes** in `apps/accounts/exceptions.py`:
```python
class SelfProtectionError(Exception): ...
class LastManagerError(Exception): ...
```

**UI self-protection:** The `data-current-user-id` attribute on the React mount element seeds the current user's pk. The `TeamTable` component compares `member.id === currentUserId` to disable Edit, Remove, and Enabled toggle on the own row.

**UI last-manager guard:** `managerCount` is derived from the stats card API response. When `member.role === "MANAGER"` AND `managerCount === 1`, Remove button is disabled with `title="Cannot remove the last Manager."`.

### Pattern 6: StaffAccessScope Bulk Replace on Edit

**Strategy chosen (Claude's Discretion):** Delete-all + `bulk_create`. Simple and correct for the small set sizes (at most a few dozen regions/shops per org).

```python
@transaction.atomic
def update_member(*, member: User, full_name: str, role: str,
                  region_ids: list[int], shop_ids: list[int]) -> User:
    member.full_name = full_name
    member.role = role
    member.save(update_fields=["full_name", "role", "updated_at"])
    # Replace scopes atomically
    member.access_scopes.all().delete()
    new_scopes = []
    for rid in region_ids:
        new_scopes.append(StaffAccessScope(
            user=member, scope_type=StaffAccessScope.ScopeType.REGION, region_id=rid
        ))
    for sid in shop_ids:
        new_scopes.append(StaffAccessScope(
            user=member, scope_type=StaffAccessScope.ScopeType.SHOP, shop_id=sid
        ))
    if new_scopes:
        StaffAccessScope.objects.bulk_create(new_scopes)
    return member
```

### Pattern 7: Multi-Select for Scope Section (React)

**No existing multi-select widget in the codebase.** `CreateShopModal.tsx` uses a single-select `<select>` for Region. The scope section requires a new checkbox-list pattern as specified in UI-SPEC Surface 2:

```tsx
// Scrollable checkbox list — Region multi-select
<div className="max-h-[180px] overflow-y-auto border border-line rounded-md">
  {regions.map((r) => (
    <label
      key={r.id}
      className="flex items-center gap-2 px-3 py-2 hover:bg-line-soft cursor-pointer"
    >
      <input
        type="checkbox"
        className="w-4 h-4 accent-yellow"
        checked={selectedRegionIds.has(r.id)}
        onChange={() => toggleRegion(r.id)}
      />
      <span className="text-[14px] text-ink">{r.name}</span>
    </label>
  ))}
</div>
```

**Note on Store list narrowing:** Per CONTEXT.md locked decision, the Store multi-select in the Add/Edit modal always shows all active stores regardless of which regions are selected. The list page's Store filter dropdown does narrow when a Region is selected, but the modal scope selectors do not narrow.

### Pattern 8: Email Context for Team Invitation

**`send_transactional_email()` is ready to use** (`apps/common/services/email.py`). Context dict for team invitation templates:

```python
send_transactional_email(
    to=[invitee_email],
    subject=f"You're invited to join {organisation.name}",
    template_base="emails/team_invitation",
    context={
        "invitee_name": invitee_name,
        "inviter_name": invited_by.full_name,
        "organisation": organisation,
        "role_display": "Manager" if invited_for_role == "ORG_ADMIN" else "Staff",
        "accept_url": _build_accept_url(raw_token),
        "expires_in_hours": 48,
        "site_url": settings.SITE_URL.rstrip("/"),
        # For Staff role only — empty lists if Manager
        "assigned_region_names": [s.region.name for s in scopes if s.scope_type == "REGION"],
        "assigned_shop_names": [s.shop.name for s in scopes if s.scope_type == "SHOP"],
        "is_staff_role": invited_for_role == "STAFF_ADMIN",
        "is_resend": False,
    },
    tags=["team-invitation"],
)
```

**Template pattern (TEML-01 requirement):** The template checks `is_staff_role` and renders the comma-separated region/store list only for Staff:
```html
{% if is_staff_role and assigned_region_names %}
  <p>Regions: {{ assigned_region_names|join:", " }}</p>
{% endif %}
{% if is_staff_role and assigned_shop_names %}
  <p>Stores: {{ assigned_shop_names|join:", " }}</p>
{% endif %}
```

### Anti-Patterns to Avoid

- **Calling `instance.access_scopes.all()` in a serializer:** Always use `getattr(instance, 'prefetched_scopes', None)` with a fallback. Without the prefetch guard, every team list request with 20 Staff members issues 20 extra queries.
- **Creating User in `activate_team_member()` with `User.objects.create_user()`:** For TEAM_MEMBER flow, the User was created at invite time. Activation should `user.set_password(password)` + `user.is_active = True` + `user.accepted_at = timezone.now()` + `user.save()`.
- **Hardcoding `purpose='ORG_ADMIN'` only in backfill — not updating `create_organisation()`:** After migration 0005, `create_organisation()` should explicitly set `purpose=InvitationToken.Purpose.ORG_ADMIN` on the token it creates, preventing future NULL rows.
- **Using `to_attr='access_scopes'` (same name as the relation):** Use `to_attr='prefetched_scopes'` (distinct name) to avoid shadowing the manager attribute with a plain list.
- **Checking `manager_count` without `is_active=True`:** Disabled managers should not count as "last Manager" protectors — a disabled ORG_ADMIN cannot log in, so removing an active one while one disabled one remains leaves no accessible manager.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Session flush | Custom session scanning loop per request | `Session.objects.filter(expire_date__gte=now)` + `get_decoded()` | Django's `Session` model has `get_decoded()` built-in |
| CSRF in fetch | Custom token extraction | Copy `getCsrfToken()` from `shop-management/api.ts` verbatim | Already battle-tested in this codebase |
| Pagination | Custom page logic | Copy `ShopsPagination` (PageNumberPagination) | Identical requirements |
| Multi-select | React Select / headless UI | Native checkbox list per UI-SPEC (no new dependencies) | Project uses hand-rolled components; no external component libs |
| Token generation | Custom random string | `secrets.token_urlsafe(32)` (already used in organisations service) | Standard library, cryptographically secure |
| Query-count assertion | Custom assert | `assert_query_ceiling` fixture from `apps.common.tests.fixtures` | Already available, conftest.py pattern established |

**Key insight:** The entire Phase 9 backend is implementable by composing existing patterns. The only genuinely new code is the team-specific business logic in `services/team.py` and `selectors/team.py`.

---

## Common Pitfalls

### Pitfall 1: `to_attr` Name Collision with Relation Manager
**What goes wrong:** Using `to_attr='access_scopes'` in Prefetch shadows the relation manager, causing unexpected behavior when serializers or tests access the attribute.
**Why it happens:** Django stores the `to_attr` result as a plain list attribute on the instance; using the same name as the relation replaces the manager.
**How to avoid:** Always use `to_attr='prefetched_scopes'` (distinct name). Read with `getattr(instance, 'prefetched_scopes', None)`.
**Warning signs:** `AttributeError` on `prefetched_scopes` or unexpectedly empty access chip list.

### Pitfall 2: Purpose NOT NULL Migration Order
**What goes wrong:** Running `AlterField(null=False)` before `RunPython(backfill)` causes `IntegrityError` if any NULL rows exist.
**Why it happens:** Django migration operations run in declaration order within a single `operations` list.
**How to avoid:** Always declare `RunPython` before `AlterField` in the same migration. Both are wrapped in a single transaction by default.
**Warning signs:** Migration fails with `NOT NULL constraint failed: accounts_invitation_token.purpose`.

### Pitfall 3: User Created at Activation vs at Invite Time
**What goes wrong:** Calling `User.objects.create_user(email=..., ...)` in `activate_team_member()` creates a second User row, causing `email` UniqueConstraint violation.
**Why it happens:** The `invite_member()` service creates the User at invite time (so a Pending row appears in the team list). If `activate_team_member()` also calls `create_user`, it duplicates.
**How to avoid:** `invite_member()` creates `User(is_active=False, ...)` and saves it. `activate_team_member()` fetches the existing user via `invitation.invited_user` and updates it.
**Warning signs:** `UNIQUE constraint failed: accounts_user.email` on team member activation.

### Pitfall 4: `invited_user` is OneToOneField — Resend Conflict
**What goes wrong:** `InvitationToken.invited_user` is `OneToOneField(null=True)`. Creating a new token for the same user (on resend) fails because OneToOneField enforces uniqueness — only one token can reference a given user at a time.
**Why it happens:** `resend_team_invitation()` marks old tokens `is_used=True` but the `invited_user` FK on the old token still points to the user.
**How to avoid:** Before creating the new token, null out `invited_user` on the old token: `old_token.invited_user = None; old_token.save(update_fields=["invited_user"])`. Then create the new token with `invited_user=user`.
**Warning signs:** `UNIQUE constraint failed: accounts_invitation_token.invited_user_id` on resend.

### Pitfall 5: CustomLoginView Inactive Message
**What goes wrong:** TEAM-12 requires "Your account has been disabled. Contact your administrator." but `CustomAuthenticationForm.error_messages["inactive"]` currently says "This account is inactive."
**Why it happens:** The existing form error message was written for generic use.
**How to avoid:** Update `error_messages["inactive"]` in `CustomAuthenticationForm` to the required copy. This affects ALL roles — verify no tests assert the old copy.
**Warning signs:** Login form shows old "This account is inactive." in tests for TEAM-12.

### Pitfall 6: Conftest Import for `assert_query_ceiling`
**What goes wrong:** `assert_query_ceiling` fixture is defined in `apps/common/tests/fixtures.py` but won't auto-discover in `apps/accounts/tests/` without a conftest that re-exports it.
**Why it happens:** pytest conftest auto-discovery only searches ancestor directories of the test file, not sibling apps.
**How to avoid:** Check if `apps/accounts/tests/conftest.py` exists. If not, create it following `apps/shops/tests/conftest.py` pattern (re-export `assert_query_ceiling` and `two_orgs_two_admins`).
**Warning signs:** `fixture 'assert_query_ceiling' not found` in pytest output.

---

## Code Examples

### invite_member() Service — Core Pattern

```python
# apps/accounts/services/team.py
import secrets
from django.db import transaction
from django.utils import timezone


@transaction.atomic
def invite_member(
    *,
    organisation: "Organisation",
    full_name: str,
    email: str,
    invited_for_role: str,
    region_ids: list[int],
    shop_ids: list[int],
    invited_by: "User",
) -> tuple["User", str]:
    """Creates User (is_active=False) + InvitationToken + StaffAccessScope rows.
    Returns (user, raw_token). Email send happens after this returns — caller is responsible."""
    from apps.accounts.models import InvitationToken, StaffAccessScope, User

    role = (
        User.Role.STAFF_ADMIN
        if invited_for_role == InvitationToken.InvitedForRole.STAFF_ADMIN
        else User.Role.ORG_ADMIN
    )
    user = User(
        email=email,
        full_name=full_name,
        role=role,
        organisation=organisation,
        invited_by=invited_by,
        invited_at=timezone.now(),
        is_active=False,
    )
    user.set_unusable_password()
    user.save()

    raw_token = secrets.token_urlsafe(32)
    InvitationToken.objects.create(
        organisation=organisation,
        invited_user=user,
        token_hash=InvitationToken.hash_token(raw_token),
        purpose=InvitationToken.Purpose.TEAM_MEMBER,
        invited_for_role=invited_for_role,
    )

    scopes = [
        StaffAccessScope(user=user, scope_type=StaffAccessScope.ScopeType.REGION, region_id=rid)
        for rid in region_ids
    ] + [
        StaffAccessScope(user=user, scope_type=StaffAccessScope.ScopeType.SHOP, shop_id=sid)
        for sid in shop_ids
    ]
    if scopes:
        StaffAccessScope.objects.bulk_create(scopes)

    return user, raw_token
```

### activate_team_member() Service

```python
@transaction.atomic
def activate_team_member(
    *,
    invitation: "InvitationToken",
    full_name: str,
    password: str,
) -> "User":
    """Activate an existing (is_active=False) team member User.
    Uses select_for_update() against InvitationToken to prevent double-submit race."""
    from apps.accounts.models import InvitationToken

    locked = InvitationToken.objects.select_for_update().get(pk=invitation.pk)
    if locked.is_used:
        raise ValidationError("Invitation already used.")

    user = locked.invited_user
    if user is None:
        raise ValidationError("Invitation is invalid.")

    user.full_name = full_name
    user.set_password(password)
    user.is_active = True
    user.accepted_at = timezone.now()
    user.save(update_fields=["full_name", "password", "is_active", "accepted_at", "updated_at"])

    locked.is_used = True
    locked.save(update_fields=["is_used", "updated_at"])

    return user
```

### TeamViewSet — disable action pattern

```python
@action(detail=True, methods=["post"], url_path="disable")
def disable(self, request: Request, pk: int | None = None) -> Response:
    member = self.get_object()
    if member.pk == request.user.pk:
        return Response(
            {"detail": "You cannot disable yourself."},
            status=status.HTTP_403_FORBIDDEN,
        )
    from apps.accounts.services.team import disable_member
    disable_member(member=member)
    return Response(TeamMemberReadSerializer(member).data)
```

### Query-count test template

```python
def test_team_list_query_count(api_client, assert_query_ceiling, db):
    org = OrganisationFactory()
    admin = UserFactory(role=User.Role.ORG_ADMIN, organisation=org)
    for _ in range(20):
        staff = UserFactory(role=User.Role.STAFF_ADMIN, organisation=org, is_active=True)
        StaffAccessScopeFactory(user=staff, scope_type="REGION")
        StaffAccessScopeFactory(user=staff, scope_type="REGION")
        StaffAccessScopeFactory(user=staff, scope_type="SHOP")

    api_client.force_authenticate(user=admin)
    with CaptureQueriesContext(connection) as ctx:
        response = api_client.get("/api/v1/team/")
    assert response.status_code == 200
    assert_query_ceiling(ctx, max_queries=4)  # ROADMAP.md mandated ceiling
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `InvitationToken.purpose = NULL` | Backfill to `ORG_ADMIN`, then `NOT NULL` | Phase 9 migration 0005 | Enables safe TEAM_MEMBER token creation |
| `invite_accept_view` always calls `activate_account()` | Branches on `invitation.purpose` | Phase 9 | Enables team member activation flow |
| `django_session` never flushed on disable | Optional flush via `Session.objects.filter(...)` | Phase 9 | Near-instant session termination |

**Deprecated/outdated:**
- `create_organisation()` not setting `purpose` on InvitationToken: after migration 0005, this service should be updated to set `purpose=InvitationToken.Purpose.ORG_ADMIN` explicitly (not a correctness issue after backfill, but prevents future nullable rows in case the NOT NULL constraint is ever relaxed).

---

## Open Questions

1. **`activate_team_member()` handles both ORG_ADMIN and STAFF_ADMIN invited_for_role**
   - What we know: Manager team members get `role=ORG_ADMIN`. Staff team members get `role=STAFF_ADMIN`. Both come through the TEAM_MEMBER purpose path.
   - Recommendation: `activate_team_member()` handles both — the `invited_for_role` on the token determines the User.role. Manager team members redirect to `/admin/org/dashboard/`. Staff members redirect to `/admin/org/welcome/`.

2. **`InvitationToken.invited_user` is OneToOneField — resend requires null-out of old token**
   - What we know: `resend_team_invitation()` must create a new token referencing the same User. OneToOneField uniqueness means only one token can reference a User at a time.
   - Recommendation: `resend_team_invitation()` must null out `invited_user` on old tokens before creating the new token. Planners should add this step explicitly to the resend service task.

3. **Stats card counts include the Org Admin themselves?**
   - Recommendation: Include the Org Admin in all counts (they are a member of the org). "Total Members" = all ORG_ADMIN + STAFF_ADMIN users in the org. The Org Admin sees themselves in the list and the count includes them.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest + pytest-django (existing) |
| Config file | `pyproject.toml` (existing `[tool.pytest.ini_options]`) |
| Quick run command | `pytest apps/accounts/tests/ -x -q` |
| Full suite command | `pytest --cov=apps --cov-fail-under=85` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| TEAM-01 | Team list columns render correctly via serializer | unit (serializer) | `pytest apps/accounts/tests/test_serializers.py -x` | ❌ Wave 0 |
| TEAM-06 | `invite_member` creates user+token+scopes | unit (service) | `pytest apps/accounts/tests/test_services_team.py::test_invite_member -x` | ❌ Wave 0 |
| TEAM-07 | `invite_member` sends team invitation email | unit (service) | `pytest apps/accounts/tests/test_services_team.py::test_invite_member_sends_email -x` | ❌ Wave 0 |
| TEAM-10 | `disable_member` sets is_active=False | unit (service) | `pytest apps/accounts/tests/test_services_team.py::test_disable_member -x` | ❌ Wave 0 |
| TEAM-13 | `remove_member` revokes access + invalidates tokens | unit (service) | `pytest apps/accounts/tests/test_services_team.py::test_remove_member -x` | ❌ Wave 0 |
| TEAM-14 | self-protection returns 403 at API layer | integration (viewset) | `pytest apps/accounts/tests/test_views_team.py::test_cannot_remove_self -x` | ❌ Wave 0 |
| TEAM-15 | last-manager guard returns 403 at API layer | integration (viewset) | `pytest apps/accounts/tests/test_views_team.py::test_last_manager_guard -x` | ❌ Wave 0 |
| TEAM-17 | `activate_team_member` sets password + is_active | unit (service) | `pytest apps/accounts/tests/test_services_team.py::test_activate_team_member -x` | ❌ Wave 0 |
| TEML-01 | team invitation email contains inviter, org, role, scopes | unit (service) | `pytest apps/accounts/tests/test_services_team.py::test_team_invitation_email -x` | ❌ Wave 0 |
| XMOD-03 | `list_shops(active_only=True)` excludes inactive shops | unit (selector) | `pytest apps/shops/tests/test_selectors.py -x` | ✅ (active_only param exists) |
| XMOD-05 | team list endpoint: ≤4 queries for 20 Staff with 3 scopes each | integration (viewset) | `pytest apps/accounts/tests/test_views_team.py::test_team_list_query_count -x` | ❌ Wave 0 |
| Migration 0005 | backfill sets purpose=ORG_ADMIN then NOT NULL constraint applies | migration test | `pytest apps/accounts/tests/test_migrations.py -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest apps/accounts/tests/ -x -q`
- **Per wave merge:** `pytest --cov=apps --cov-fail-under=85`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `apps/accounts/selectors/` directory — create with `__init__.py` + `team.py`
- [ ] `apps/accounts/tests/test_services_team.py` — covers TEAM-06, TEAM-07, TEAM-10, TEAM-13, TEAM-17, TEML-01, TEML-02
- [ ] `apps/accounts/tests/test_views_team.py` — covers TEAM-14, TEAM-15, XMOD-05
- [ ] `apps/accounts/tests/test_serializers.py` — covers TEAM-01 (access_scopes prefetch read path)
- [ ] `apps/accounts/tests/conftest.py` — verify exists; if not, create following `apps/shops/tests/conftest.py` re-export pattern for `assert_query_ceiling` and `two_orgs_two_admins`

---

## Sources

### Primary (HIGH confidence)

- Direct codebase inspection: `apps/accounts/models.py` — User, InvitationToken, StaffAccessScope models confirmed verbatim
- Direct codebase inspection: `apps/accounts/views.py` — `invite_accept_view` implementation confirmed verbatim
- Direct codebase inspection: `apps/accounts/migrations/0003_user_invitationtoken_v02.py` — purpose column is nullable (step 1 complete)
- Direct codebase inspection: `apps/accounts/migrations/0004_staffaccessscope.py` — latest migration; step 2 goes into 0005
- Direct codebase inspection: `config/settings/base.py` — no `SESSION_ENGINE` key → Django default db sessions
- Direct codebase inspection: `config/settings/production.py` — no `SESSION_ENGINE` override
- Direct codebase inspection: `apps/common/services/email.py` — `send_transactional_email()` signature confirmed
- Direct codebase inspection: `apps/shops/selectors/shops.py` — `active_only` param confirmed present (XMOD-03 satisfied)
- Direct codebase inspection: `apps/organisations/services/organisations.py` — `activate_account()` confirmed; user created at activation for ORG_ADMIN flow
- Direct codebase inspection: `apps/common/viewsets.py` — `TenantScopedViewSet` confirmed
- Direct codebase inspection: `apps/common/permissions.py` — `IsOrgScoped` confirmed
- Direct codebase inspection: `apps/accounts/tests/factories.py` — `StaffAccessScopeFactory` confirmed ready
- Direct codebase inspection: `apps/common/tests/fixtures.py` — `assert_query_ceiling`, `two_orgs_two_admins` confirmed
- Direct codebase inspection: `apps/shops/tests/conftest.py` — conftest re-export pattern confirmed
- Direct codebase inspection: `apps/accounts/forms.py` — `CustomAuthenticationForm.error_messages["inactive"]` currently "This account is inactive." (needs update for TEAM-12)
- Direct codebase inspection: `apps/organisations/urls.py` — `org_team` stub confirmed; Phase 9 replaces `org_stub_view`
- Direct codebase inspection: `frontend/src/widgets/shop-management/api.ts` — CSRF + fetch pattern for copying
- Direct codebase inspection: `templates/emails/invitation.html` — existing email template structure for reference
- Direct codebase inspection: `apps/accounts/services/` — `selectors/` directory does NOT exist; must be created in Wave 0

### Secondary (MEDIUM confidence)

- Django `Session.get_decoded()` for database backend — standard Django documented API. Confirmed backend is `django.contrib.sessions.backends.db` by settings inspection; `get_decoded()` behavior is well-documented in Django source.
- `InvitationToken.invited_user` OneToOneField resend conflict — identified from model inspection; the null-out resolution is recommended but not confirmed by existing service code.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries confirmed via settings and codebase inspection; no new dependencies needed
- Architecture: HIGH — all patterns are direct extensions of Phase 7/8 implementations confirmed in codebase
- Pitfalls: HIGH — all pitfalls identified from actual code inspection (not speculation)
- Session termination: MEDIUM — `is_active=False` is confirmed sufficient by CONTEXT.md; Session table flush approach is standard Django but not yet exercised in this codebase

**Research date:** 2026-04-29
**Valid until:** 2026-05-29 (30 days — stable framework stack)
