---
paths:
  - "apps/**/views.py"
  - "apps/**/serializers.py"
  - "apps/**/api_urls.py"
  - "apps/**/urls.py"
---

# DRF View / Serializer Rules

Concise reminder — full detail in CLAUDE.md §5 (thin views), §8 (DRF), §9 + §22 (auth/tenant).

- **Thin views.** Delegate writes to `services/`, reads to `selectors/`. Do **not** call `.objects.filter()` in a view for anything beyond a trivial read. No multi-step workflows in views.
- **Explicit permissions on EVERY viewset** — no global/implicit `AllowAny`. Compose `IsAuthenticated & <role perm>` (`IsSuperadmin` / `IsOrgAdmin` / `IsStaffAdmin`).
- **Tenant scoping is mandatory.** Org/Staff-admin querysets MUST filter by the caller's `organisation_id` (enforce in a base permission/mixin, not per-view). Staff also enforce brand-vs-shop scope (action items) and `StaffAccessScope`.
- **Pagination on every list endpoint** (`PageNumberPagination` / `CursorPagination` for big tables). **Throttling** on every endpoint (scoped rates).
- **Serializers validate + shape only** — no business logic, no side effects. Use two serializers (read vs create) when input ≠ output. Never trust `request.data` directly.
- Filtering via explicit `django-filter` `FilterSet` — never expose arbitrary `__` lookups. URL path versioning (`/api/v1/...`).
- Add a query-count test for each new list endpoint (§6.9).
