# Off-Roadmap Features — Retro Registry

**Status:** Shipped / in production code
**Created:** 2026-06-16
**Purpose:** Record features that are **built and live in the codebase but were never captured in the formal GSD requirements registry** (`.planning/REQUIREMENTS.md` / milestone `*REQUIREMENTS*.md` / `ROADMAP.md`). Found via a code-vs-requirements audit (2026-06-16).

> **Root cause:** most of these were built through a parallel **Superpowers** spec/plan track (`docs/superpowers/specs|plans/`, May 2026) that GSD does not read, so they never got REQ-IDs. One (Reply Templates) has **no spec at all**. This file makes them discoverable; it does **not** retro-assign authoritative REQ-IDs (the `Suggested REQ prefix` column is a hint if/when they're folded into the registry).
>
> **Going forward:** features must be added to `.planning/REQUIREMENTS.md` **before** they are built — see CLAUDE.md §24 ("Requirements first"). Do not extend this file with new work; fold new features into the registry instead.

---

## Summary

| # | Feature | Code surface | Source | Suggested REQ prefix |
|---|---------|--------------|--------|----------------------|
| 1 | **Reply Templates** | `apps/reply_templates/` (model, viewset, widget) | 🔴 **Undocumented** — no GSD requirement, no Superpowers spec | `REPL-` |
| 2 | **Reports (Store Performance)** | `apps/reports/` (API view, page, widget) | 🟡 Superpowers — `docs/superpowers/specs/2026-05-12-reports-design.md` (+ plan) | `RPT-` |
| 3 | **Recurring Review Targets** | `ReviewTarget` model + viewset + `shop-targets` widget | 🟡 Superpowers — `2026-05-10-review-target-design.md`, `2026-05-11-recurring-review-targets-design.md` | `RTGT-` |
| 4 | **Mobile API / JWT auth** | `MobileTokenObtainPairView`, `TokenRefreshView` | 🟡 Superpowers — `2026-05-09-mobile-api-jwt-docs-design.md` (corpus treats JWT as future/conditional) | `MJWT-` |
| 5 | **Action Item Categories** | `ActionItem.Category` enum + `category` field/index/filter | 🟡 Superpowers — `2026-05-15-action-item-categories-design.md` | `AIC-` |

Legend: 🔴 no spec anywhere · 🟡 specced only in the Superpowers side-track (not in the GSD registry).

---

## 1. Reply Templates — 🔴 Undocumented

Org-scoped, reusable reply snippets used when responding to reviews.

- **Code:** `apps/reply_templates/` — `ReplyTemplate(TimeStampedModel)` (`models.py:10`, org-scoped `name` + `content`); `ReplyTemplateViewSet` (`views.py:74`) at `/api/v1/reply-templates/`; `selectors/`, `services/templates.py`, `serializers.py`, `tests/`; React widget `frontend/src/widgets/reply-templates/` (entrypoint `reply-templates.tsx`); nav at `/admin/org/reply-templates/`.
- **Spec status:** No REQ-ID and no design doc anywhere. The only corpus hit for "reply template" is an SES email template (`reviewbee_reply`) and a coverage-table row in the mobile-API doc — neither specifies this feature.
- **Note:** Distinct from v0.2 *Team Email Templates* (TEML-01/02, which are invitation emails). This is the one genuinely undocumented feature — it warrants a real spec.

## 2. Reports — Store Performance — 🟡 Superpowers

- **Code:** `apps/reports/` — `StoreReportApiView` at `GET /api/v1/reports/stores/`; `reports_page_view` at `/admin/org/reports/`; `selectors/`; React widget `frontend/src/widgets/reports/` (entrypoint `reports.tsx`).
- **Spec status:** `docs/superpowers/specs/2026-05-12-reports-design.md` + `plans/2026-05-12-reports.md`. No REQ-ID, no ROADMAP phase (the phase table jumps 6 → 26 with no Reports phase).

## 3. Recurring Review Targets — 🟡 Superpowers

- **Code:** `ReviewTarget` model (`apps/shops/models.py:129` — WEEK/MONTH period, `target_count` per shop); `ReviewTargetViewSet` at `/api/v1/shops/{pk}/targets/`; `shop_targets_view` at `/admin/org/shops/<id>/targets/`; `apps/shops/services/targets.py`, `selectors/targets.py`; React widget `shop-targets/` (entrypoint `shop-targets.tsx`).
- **Spec status:** Superpowers `2026-05-10-review-target-*` and `2026-05-11-recurring-review-targets-*`. No REQ-ID.

## 4. Mobile API / JWT authentication — 🟡 Superpowers (+ built ahead of approval)

- **Code:** `apps/accounts/api_urls.py` — `MobileTokenObtainPairView` at `/api/v1/auth/token/`, `TokenRefreshView` at `/api/v1/auth/token/refresh/` (SimpleJWT).
- **Spec status:** Superpowers `2026-05-09-mobile-api-jwt-docs-*`. The formal corpus explicitly treats JWT as **future/conditional** — `Requirements_Superadmin.md`: *"Token-based authentication (SimpleJWT) will be added only if a separate client is introduced,"* and `ROADMAP.md`: *"📱 Mobile app — scope … to be defined"* (a milestone after v0.8). So these endpoints exist ahead of an approved requirement. CLAUDE.md §9 still says session auth is primary and "token auth (SimpleJWT) only if a separate client is added later."

## 5. Action Item Categories — 🟡 Superpowers

- **Code:** `ActionItem.Category` choices (QUALITY / SERVICE / EXPERIENCE / OPERATIONS / OTHER) + `category` field and `ai_org_category_idx` index (`apps/action_items/models.py:43`); category filtering in the action-items viewset/widget. Also baked into the v0.8 enrichment prompt (`category` is a required field on each GPT action item — see §14.2 / `apps/integrations/openai/parser.py`).
- **Spec status:** Superpowers `2026-05-15-action-item-categories-*`. No REQ-ID in v0.6 (Action Item Quality) or v0.7. Partially load-bearing for v0.8 since the enrichment parser depends on the `category` enum.

---

## Appendix — Infrastructure built via Superpowers (operational, lower concern)

Deployment/infra work also went through the Superpowers track and is not in the feature requirements registry, but it is operational scaffolding rather than end-user features:

- AWS deployment — `docs/superpowers/specs/2026-05-05-aws-deployment-design.md`
- Infra hardening — `2026-05-06-infra-hardening-design.md`
- ECR lifecycle + budget alert — `plans/2026-05-07-ecr-lifecycle-and-budget-alert.md`

(Infrastructure-as-code lives in the sibling `../review-master-terraform/` workspace per CLAUDE.md §25.)

---

## Not findings (verified covered or pure scaffolding)

- **Audit Log Viewer** (`AuditLog`/`ShopAuditLog`, `/api/v1/audit-logs/`, `audit-log` widget) — covered by v0.7 `REQ-01..09`.
- CloudWatch metrics + `publish_celery_queue_depths_task`, `enrich_existing_reviews` backfill command, `smoke_test_task`, the `__ui__/` component showcase, OAuth-result polling — operational/test scaffolding implied by existing requirements.
