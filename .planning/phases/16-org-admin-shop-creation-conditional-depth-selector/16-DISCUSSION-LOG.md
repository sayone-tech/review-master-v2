# Phase 16: Org Admin Shop Creation — Conditional Depth Selector - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-15
**Phase:** 16-org-admin-shop-creation-conditional-depth-selector
**Areas discussed:** Org flag delivery, Backend validation gate, Dropdown form placement

---

## Org flag delivery

**Q1: How should CreateShopModal receive the org's allow_custom_sync_depth value?**

| Option | Description | Selected |
|--------|-------------|----------|
| New bootstrap tag | Django template adds `<script type="application/json" id="shop-org-data">` — consistent with how shop-allocation and shop-regions-data are passed. Zero API calls, available immediately on mount. | ✓ |
| Fetch from org API on mount | Entrypoint calls GET /api/v1/organisations/{id}/ when the modal opens. Adds loading state; doesn't require Django template change. | |

**User's choice:** New bootstrap tag

**Q2: Flag-only or slim org object?**

| Option | Description | Selected |
|--------|-------------|----------|
| Flag only — `{"allow_custom_sync_depth": true}` | Minimal surface area — only what the shop creation form needs. | ✓ |
| Slim org object — `{"id": ..., "allow_custom_sync_depth": true, "name": ...}` | More flexible for future phases. Small extra payload. | |

**User's choice:** Flag only

**Notes:** None

---

## Backend validation gate

**Q1: If a client posts sync_depth when the org doesn't allow custom depth, what should the backend do?**

| Option | Description | Selected |
|--------|-------------|----------|
| Silently ignore — always use model default | Frontend never sends it unless allowed. Crafted API calls silently default to TWO_YEARS. Keeps API simple. | ✓ |
| Reject with 400 if org flag is False | Stricter. Serializer or service checks org.allow_custom_sync_depth and returns validation error. More defensive but adds complexity. | |

**User's choice:** Silently ignore

**Q2: Where should choice validation live?**

| Option | Description | Selected |
|--------|-------------|----------|
| DRF ChoiceField in serializer | `sync_depth = serializers.ChoiceField(choices=Shop.SyncDepth.choices, required=False, default=TWO_YEARS)`. DRF validates; service receives valid value or default. | ✓ |
| You decide | Planner/executor figures out validation layer. | |

**User's choice:** DRF ChoiceField in serializer

**Notes:** None

---

## Dropdown form placement

**Q1: Where should the Review History dropdown appear in Step 3?**

| Option | Description | Selected |
|--------|-------------|----------|
| After Region, before Phone | Groups depth choice near structural config (region). Org Admin sees it early, before optional fields. | ✓ |
| After Street Address (bottom of form) | Keeps identity fields together; config option last. Matches org modal toggle placement. | |

**User's choice:** After Region, before Phone

**Q2: Should the dropdown include helper text?**

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — short description | "Sets how far back this shop's initial review sync will go." — helps Org Admins who may not know what this controls. | ✓ |
| Label only | Compact. "Review History" + options may be self-explanatory. | |

**User's choice:** Yes, include helper text

**Notes:** Exact wording locked as "Sets how far back this shop's initial review sync will go."

---

## Claude's Discretion

- Exact prop threading path (direct prop vs. context) — prop-drilling fine given shallow depth
- Whether `shop-org-data` bootstrap tag lives on same template line as `shop-regions-data` or in a separate block
- State variable name for selected sync depth inside `CreateShopModal`

## Deferred Ideas

None — discussion stayed within phase scope.
