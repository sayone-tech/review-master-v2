---
phase: 21-audit-log-viewer
reviewed: 2026-05-24T00:00:00Z
depth: standard
files_reviewed: 22
files_reviewed_list:
  - apps/common/selectors/audit_logs.py
  - apps/common/serializers.py
  - apps/common/filters.py
  - apps/common/pagination.py
  - apps/common/views.py
  - apps/common/urls.py
  - apps/common/tests/test_audit_log_selectors.py
  - apps/common/tests/test_audit_log_api.py
  - config/urls.py
  - config/settings/base.py
  - templates/org-admin/audit-log.html
  - templates/partials/sidebar_org.html
  - frontend/src/entrypoints/audit-log.tsx
  - frontend/src/widgets/audit-log/types.ts
  - frontend/src/widgets/audit-log/utils.ts
  - frontend/src/widgets/audit-log/api.ts
  - frontend/src/widgets/audit-log/useAuditLog.ts
  - frontend/src/widgets/audit-log/TypePill.tsx
  - frontend/src/widgets/audit-log/AuditLogFilters.tsx
  - frontend/src/widgets/audit-log/AuditLogTable.tsx
  - frontend/src/widgets/audit-log/AuditLogWidget.tsx
  - frontend/vite.config.ts
findings:
  critical: 1
  warning: 6
  info: 5
  total: 12
status: issues_found
---

# Phase 21: Code Review Report

**Reviewed:** 2026-05-24
**Depth:** standard
**Files Reviewed:** 22
**Status:** issues_found

## Summary

The Phase 21 audit-log viewer is well-structured: cursor pagination has a tie-breaker, the
selector applies `select_related("actor")`, the serializer correctly omits `before_data`,
the template uses `{% json_script %}` for bootstrap data (XSS-safe), and a `CaptureQueriesContext`
test asserts a query ceiling. CSRF is handled by Django; the API is GET-only.

However, one **BLOCKER** was found in the Staff-scoping selector: the entity_id filter joins
two integer-PK spaces (review PKs and action_item PKs) into a single `entity_id__in=[...]`
list. Because the entity-type predicate is OR'd separately (`AUDIT_ENTITY_FILTER` allows
review-reply OR any action_item), a Staff user can see audit-log entries for a review in
an **inaccessible shop** whenever the inaccessible review's PK happens to match the PK of any
accessible action item — and the inverse for action items. Integer PKs from separate sequences
collide routinely (id=1 exists in both tables), so this is not a theoretical edge case.

Several warnings cover filter validation gaps, an actor-dropdown leak for Staff, and a UTC
timezone issue in the date defaults. Info items cover dead code, a test with no real
assertions on the first response, and minor inconsistencies.

## Critical Issues

### CR-01: Staff scope leak via entity_id collision across review/action_item PK spaces

**File:** `apps/common/selectors/audit_logs.py:48-87`
**Issue:**
`list_audit_logs_for_staff` builds `accessible_entity_ids = review_ids + action_item_ids`
(concatenated) and applies `.filter(entity_id__in=accessible_entity_ids)`. The entity-type
predicate `AUDIT_ENTITY_FILTER` is OR'd separately:

```
(entity_type='action_item' OR (entity_type='review' AND action IN [...reply...]))
  AND entity_id IN (review_ids + action_item_ids)
```

Because `Review` and `ActionItem` both extend `TimeStampedModel` (NOT `UUIDModel`), they use
**integer auto-PKs from separate sequences**. PK=1 exists in both tables. This means an
audit-log row of `entity_type="review", entity_id="1"` for a review in an
**inaccessible shop** will pass the filter whenever an accessible `ActionItem` with `pk=1`
exists (because `"1"` is in the combined list). The inverse also leaks brand-scope action
items: an `AuditLog` with `entity_type="action_item", entity_id="42"` for a brand-scope
item leaks if any accessible Review has `pk=42`.

This is the **layer-1 authoritative defence** per CLAUDE.md §9 — and it is broken.

`AuditLogFactory.entity_id` defaults to `factory.Sequence(lambda n: str(n))`, so the
existing tests `test_list_audit_logs_for_staff_excludes_brand_scope_items` and
`test_list_audit_logs_for_staff_excludes_inaccessible_shop_reviews` may pass coincidentally
because the sequence values never collide across runs of the same test, but they do **not**
cover the collision case.

**Fix:**
Split the entity-id filter by entity type, so review entity_ids only ever match review
audit rows and action-item entity_ids only match action_item audit rows:

```python
return (
    AuditLog.objects.filter(organisation_id=organisation_id)
    .filter(AUDIT_ENTITY_FILTER)
    .filter(
        Q(entity_type="review", entity_id__in=review_ids)
        | Q(entity_type="action_item", entity_id__in=action_item_ids)
    )
    .select_related("actor")
)
```

Also add an explicit regression test:

```python
def test_list_audit_logs_for_staff_no_cross_type_pk_collision():
    org = OrganisationFactory()
    shop_in = ShopFactory(organisation=org)
    shop_out = ShopFactory(organisation=org)
    staff = UserFactory(role=User.Role.STAFF_ADMIN, organisation=org)
    StaffAccessScopeFactory(user=staff, scope_type=StaffAccessScope.ScopeType.SHOP,
                             shop=shop_in)
    # Accessible action item whose PK collides with an inaccessible review PK.
    review_out = ReviewFactory(organisation=org, shop=shop_out)
    ai_in = ActionItemFactory(organisation=org, shop=shop_in,
                              scope=ActionItem.Scope.SHOP, pk=review_out.pk)
    AuditLogFactory(organisation=org, entity_type="review",
                    entity_id=str(review_out.pk), action="reply_posted")
    rows = list(list_audit_logs_for_staff(organisation_id=org.id, user=staff))
    assert all(r.entity_id != str(review_out.pk) or r.entity_type != "review"
               for r in rows)
```

## Warnings

### WR-01: `entity_type` filter accepts arbitrary strings (no whitelist)

**File:** `apps/common/filters.py:16`
**Issue:**
`entity_type = django_filters.CharFilter(field_name="entity_type")` accepts any string. A
caller can pass `?entity_type=shop_sync` (or anything). The selector's
`AUDIT_ENTITY_FILTER` AND-intersects to empty, so this does not leak data — but bypassing
input validation is unsafe defence-in-depth and the API contract (D-07) restricts the param
to `"review" | "action_item"`.
**Fix:**
Use `ChoiceFilter` with an explicit whitelist:

```python
entity_type = django_filters.ChoiceFilter(
    field_name="entity_type",
    choices=[("review", "review"), ("action_item", "action_item")],
)
```

### WR-02: `date_from > date_to` is silently accepted

**File:** `apps/common/filters.py:18-19`
**Issue:**
No cross-field validation — a request with `date_from=2026-12-31&date_to=2026-01-01`
returns an empty result set with HTTP 200, masking a client bug. CLAUDE.md §8 expects
explicit filterset validation.
**Fix:**
Override `FilterSet.clean` or add a `def clean(self)` to raise
`forms.ValidationError("date_from must be on or before date_to")` so DRF returns 400.

### WR-03: Actor dropdown bootstrap leaks org-wide actor names to Staff users

**File:** `apps/common/views.py:184-212`
**Issue:**
`audit_log_view` builds `actors_list` from `AuditLog.objects.filter(organisation_id=org_id)`
for both ORG_ADMIN and STAFF_ADMIN. A Staff user only sees their accessible-shop subset of
log entries, but the dropdown surfaces **every actor in the org** — including actors who
only acted on brand-scope items or inaccessible shops. This is a low-severity PII leak
(internal staff names), but it bypasses the Staff scoping pattern CLAUDE.md §9 requires
at every layer.
**Fix:**
Build a role-aware actor list. For Staff, derive distinct `actor_id` values from
`list_audit_logs_for_staff(...)` rather than the raw `AuditLog` table:

```python
if getattr(request.user, "role", None) == User.Role.STAFF_ADMIN:
    base_qs = list_audit_logs_for_staff(organisation_id=org_id, user=request.user)
else:
    base_qs = list_audit_logs_for_org(organisation_id=org_id)
actors_qs = (
    base_qs.filter(actor__isnull=False)
    .values("actor_id", "actor__full_name").distinct()
    .order_by("actor__full_name")
)
```

### WR-04: `filter_shop` accepts arbitrary shop IDs without verifying caller access

**File:** `apps/common/filters.py:34-46`
**Issue:**
`filter_shop` accepts any `shop_id` and resolves it to review PKs without checking that
the requesting Staff user can access the shop. The selector's `entity_id__in=...` ANDs
to an empty intersection if the shop is inaccessible, so no data leaks. But the filter
silently swallows the inaccessible-shop request rather than returning 400/403, and the
review PK list is materialised in memory regardless. Defence-in-depth + observability
both want this to fail loudly.
**Fix:**
Pass `request` into the filterset (already available via `self.request`) and reject
`shop_id` not in the caller's accessible-shop set:

```python
def filter_shop(self, qs, name, value):
    from apps.reviews.selectors.reviews import get_accessible_shop_ids
    user = self.request.user
    accessible = set(get_accessible_shop_ids(user_id=user.pk))
    if value not in accessible:
        raise django_filters.exceptions.ValidationError({"shop": "Not accessible."})
    ...
```

### WR-05: `isoDate` uses UTC; default date window is wrong for non-UTC clients near midnight

**File:** `frontend/src/widgets/audit-log/useAuditLog.ts:11-20` and `AuditLogFilters.tsx:24-33` and `AuditLogWidget.tsx:17-25`
**Issue:**
`new Date().toISOString().split("T")[0]` always produces the **UTC** date. For users in
+05:30 (IST) or similar after 18:30 local time, the "today" date is tomorrow UTC, so the
default `date_to` is set one day past the local today, and matching against `date_from`
becomes inconsistent with what the user thinks they selected. Also leads to filter "30d"
sometimes producing 29 or 31 displayed days depending on clock skew.

`defaultDateRange` is also **duplicated** across three files
(`useAuditLog.ts`, `AuditLogFilters.tsx`, `AuditLogWidget.tsx`) — if one is changed the
others drift.
**Fix:**
Compute via local-time components:

```ts
function isoDate(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}
```

Move `defaultDateRange`/`isoDate` to `utils.ts` and import from one place.

### WR-06: Cursor-page-size mismatch — page_size cap on backend (`max_page_size=100`) but client offers 10/25/50; default 50 forces all pages to 50 regardless of UI selection

**File:** `frontend/src/widgets/audit-log/useAuditLog.ts:8`, `AuditLogWidget.tsx:99-103`, `apps/common/pagination.py:18`
**Issue:**
The hook initialises `pageSize = DEFAULT_PAGE_SIZE = 50`. UI offers `{10, 25, 50}`. On
first load, the user has no way to land on a page size other than 50 unless they
explicitly change the select — which then re-fetches. The bigger problem: changing the
page-size select correctly resets the cursor stack and triggers refetch, but the **previously
saved next/prev cursors in `prevCursorsRef`** were generated against the old page size.
If the user clicks Next, changes page size, then clicks Prev, the popped cursor is
inconsistent with the new page size and the server cursor encodes `(timestamp, id)` that
was emitted from a different page boundary. Behaviour is undefined.
**Fix:**
`changePageSize` already clears `prevCursorsRef`, but make sure the URL also drops any
cursor (currently no cursor in URL — OK). Add a test that exercises Next → change page
size → Prev returns the first page.

## Info

### IN-01: `test_filter_date_range` issues two requests but only asserts on the second; the first response is dead code

**File:** `apps/common/tests/test_audit_log_api.py:165-184`
**Issue:**
Lines 174-177 issue a request and assign to `resp`, then immediately overwrite `resp` on
line 179 without any assertion. The 2099 boundary check is unintentionally a no-op.
**Fix:**
Either add `assert resp.status_code == 200 and len(resp.data["results"]) == 0` for the
2099 window, or remove the first request.

### IN-02: `userRole` prop and `data-user-role` attribute are dead pass-through

**File:** `frontend/src/widgets/audit-log/AuditLogWidget.tsx:39-43`, `templates/org-admin/audit-log.html:5`, `frontend/src/entrypoints/audit-log.tsx:23`
**Issue:**
The widget receives `userRole` and immediately `void _userRole`s it. Three layers of
plumbing (template attr → entrypoint → widget prop) for an unused value. Either use it
(e.g., to hide the actor-name column for Staff) or remove the entire prop chain.
**Fix:**
Drop the prop, the `data-user-role` attribute, and `user_role` from the Django context
unless a near-term use case is documented.

### IN-03: `actors_json` empty-list for Superadmin path is unreachable (Superadmin can't load this page)

**File:** `apps/common/views.py:192-206`
**Issue:**
The `if org_id is not None` guard exists but `audit_log_view` is wrapped with
`@login_required` and the URL is intended for ORG/STAFF admins only. There is no
permission check in the Django view itself — a Superadmin who knows the URL can render
the page shell. The API returns 403 so no data leaks, but the page renders with the wrong
sidebar (`base_org.html`). Add a role guard or rely on a middleware redirect.
**Fix:**
Add an early role check:

```python
role = getattr(request.user, "role", None)
if role not in ("ORG_ADMIN", "STAFF_ADMIN"):
    return redirect("home")
```

### IN-04: `getattr(actor, "full_name", "") or ""` then `if full_name else None` — two paths for the same empty case

**File:** `apps/common/serializers.py:37-42`
**Issue:**
The `or ""` already converts `None` to `""`; the subsequent `if full_name` then returns
`None`. The intermediate cast `str(full_name)` is unnecessary because `full_name` is
already a string. Slight overcomplication; collapse to:

```python
def get_actor_name(self, obj):
    return getattr(obj.actor, "full_name", None) or None if obj.actor else None
```

### IN-05: Sidebar nav lacks active-state container for "Activity Log" alongside Staff-only Reports/Templates conditionals

**File:** `templates/partials/sidebar_org.html:41`
**Issue:**
The Activity Log nav item is rendered for both ORG_ADMIN and STAFF_ADMIN (correct per
D-12), but it is placed **outside** the role conditional, after the Org-Admin-only block
ends. This is intentional and correct. The minor issue: Staff users get a visual gap
between "Action Items" and "Activity Log" because the Org-Admin-only `{% if %}` block
collapses to nothing. The `<ul>` rendering is fine, but if a CSS rule on `<li>` last-of-type
is ever added it will misbehave for Staff. Document with a comment or move the conditional
boundary so Activity Log is always the last item regardless of role.
**Fix:**
Add a short comment above line 41 noting the placement is intentional.

---

_Reviewed: 2026-05-24_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
