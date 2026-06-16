---
name: security-checklist
description: >-
  Project security review of the current diff/branch for this multi-tenant Django + DRF + Celery + Channels SaaS. Enforces THIS repo's conventions — multi-tenant isolation, RBAC, Channels/Celery auth, OpenAI PII logging, and the CLAUDE.md §22 deploy checklist — and invokes the tenant-security-auditor / orm-performance-auditor subagents for the high-risk surfaces. Use BEFORE opening a PR, before merging any auth/scoping/query/OpenAI/Channels change, or when the user asks to "security review", "check tenant isolation", "audit permissions/RBAC", "review for vulnerabilities", or "is this secure". Complements the built-in /security-review (generic vuln scan) by checking project-specific rules.
---

# Security Checklist (project)

Run a security review of the changes on the current branch against this repo's conventions. Tenant isolation is the **highest-risk surface**; treat a cross-tenant leak or a missing permission as a **blocker**.

## Workflow

1. **Scope the change.** `git diff --name-only origin/main...HEAD` (fall back to `git diff --staged` / working tree). Note which surfaces are touched: models/queries, views/serializers/urls, permissions, Celery `tasks.py`, Channels `consumers.py`/`routing.py`, `apps/integrations/openai/**`, settings/deploy.
2. **Run the checklist below** against the diff. For each item, cite file:line evidence (pass) or a finding (severity HIGH/MED/LOW).
3. **Delegate the deep surfaces to subagents** (Agent tool, read-only):
   - Any auth/permission/scoping/Channels/Celery-handling-user-data change → **`tenant-security-auditor`**.
   - Any model/query/serializer/list-endpoint/migration change → **`orm-performance-auditor`** (an N+1 or unbounded query is also a DoS surface).
4. **Tooling:** run `bandit` on changed Python (pre-commit config in `pyproject.toml`); run `pip-audit`/`safety` if available; confirm `gitleaks`/detect-private-key found nothing.
5. **Report:** a severity-grouped findings list + a one-line verdict. **Block on any HIGH** (or `security_block_on` config). Apply fixes yourself only after surfacing them.

## Security Review Checklist

### Multi-tenant isolation (CLAUDE.md §9, §22) — highest risk
- [ ] Every new/changed queryset on org-scoped data filters by the caller's `organisation_id` (enforced in a base permission/mixin, not ad-hoc per view).
- [ ] Staff (`STAFF_ADMIN`) cannot see other orgs' data **or** brand-scoped action items; `StaffAccessScope` (shop/region) is honored. The selector layer is the authoritative defence.
- [ ] A **cross-tenant test** exists for the changed surface (org A cannot read/write org B; Staff 403 on brand scope).
- [ ] No object is fetched by raw PK without an org filter where tenancy applies.

### AuthN / AuthZ (RBAC) (§8, §9)
- [ ] Every viewset/endpoint has explicit `permission_classes` — **no global or implicit `AllowAny`**. Roles composed (`IsSuperadmin` / `IsOrgAdmin` / `IsStaffAdmin`).
- [ ] Detail/edit/status endpoints re-check object-level scope (return 403, not 404-leak vs 403 consistently).
- [ ] Invitation/token flows: `TimestampSigner`, ≤48h max age, single-use, hash stored — not raw tokens.

### Channels consumers (§13.4)
- [ ] On connect: authenticated (else `close(4401)`), `organisation_id` matches resource (else `close(4403)`), Staff shop-in-scope (else `close(4403)`). Failures **close**, never leak.
- [ ] No NEW consumer added without a §13 update + sign-off.

### Celery (§22 Phase 3+)
- [ ] Every task handling user-scoped data verifies `organisation_id` against the entity it operates on.
- [ ] No business logic / secrets in task args logs; args sanitized.

### OpenAI / enrichment PII (§14, §22, §29)
- [ ] Review text and prompts containing review content are **never logged at INFO+** (treat as PII).
- [ ] No bypass of the `AiUsageLog` write; no second OpenAI call / vector DB; `review_count` not mutated inline.

### Input handling & injection (§8, §22)
- [ ] All input goes through DRF serializer validation — never trust `request.data` directly.
- [ ] No `mark_safe` / `|safe` on untrusted/user input (templates, emails). User values auto-escaped.
- [ ] No raw SQL with string interpolation; ORM or parameterized.

### Settings / deployment (§22)
- [ ] `DEBUG=False`, `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, HSTS (`SECURE_HSTS_SECONDS`), explicit `ALLOWED_HOSTS`, CSP enabled (prod settings).
- [ ] Secrets from GCP Secret Manager / env — **never** committed `.env`, never hardcoded keys (gitleaks/detect-private-key clean).
- [ ] Flower never deployed to production; no debug toolbar in prod.

### Dependencies / tooling
- [ ] `bandit` — no medium/high findings on changed code.
- [ ] `pip-audit` / `safety` — no known CVEs introduced; new deps pinned (no `>=`).

## Notes
- This is advisory and project-specific; the generic `/security-review` built-in is a complementary line of defence.
- For a full-phase security pass during GSD, `/gsd-secure-phase` produces a `SECURITY.md`; this skill is the lighter pre-PR gate.
