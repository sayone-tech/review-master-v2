# Phase 32: Superadmin Credit Controls - Context

**Gathered:** 2026-11-11
**Status:** Ready for planning

<domain>
## Phase Boundary

Superadmin can (1) set an organisation's **monthly credits per shop** (0–10,000, default 0) on Create and Edit Organisation, with CRED-06 timing (0 → N applies immediately this month; any other change N → M applies from the 1st of next month while current-month balances keep N), and (2) top up **one shop's current UTC month** with bonus credits from a **"Manage credits"** action on the organisation row (shop list with balances → pick shop → amount + optional reason → live before/after preview → confirm). Every credit endpoint is Superadmin-only; Org Admin and Staff get 403 and have no path to change an allocation or add bonus.

Requirements: CRED-01, CRED-06, CSUP-01, CSUP-02. Org Admin / Staff credit **visibility** (Shop Details card, badges, composer states) is Phase 33, not here.

</domain>

<decisions>
## Implementation Decisions

### Allocation edit — mid-month change UX (CRED-01, CRED-06)
- **D-01:** The Create/Edit Organisation forms show a **live inline hint** under "Monthly credits per shop" that updates as the value changes — no confirm dialog. Wording intent:
  - 0 → N (N > 0): "Takes effect immediately for this month."
  - N → M (any other change, including → 0): "Takes effect {1st of next month, e.g. Dec 1}. Shops keep {N} this month."
  - Value 0 on Create (or unchanged at 0): the spec §8.1 helper ("Each shop in this organisation gets this many credits at the start of every month. Unused credits lapse.") plus a note that 0 means AI replies are off.
  Exact copy and placement are for `/gsd-ui-phase 32`.
- **D-02:** **N → 0 follows the same N → M rule** — shops keep N for the rest of the current month and get 0 from next month. There is no immediate "kill switch"; CRED-06 stays as written.
- **D-03:** The allocation is **editable regardless of organisation status** (active/disabled). No credit-specific behaviour is tied to org status.
- **D-04:** Create Organisation **defaults to 0** (feature off), per CRED-01 and the Phase 30 deploy note (CQA-02).

### "Manage credits" modal — shop list (CSUP-01)
- **D-05:** The modal lists the org's **active shops only**. Deactivated shops are not shown and cannot receive bonus.
- **D-06:** Each row shows the shop name, **"Remaining {n}"** prominently, and a muted breakdown **"Monthly {allocated} · Bonus {bonus} · Used {consumed}"** (spec §8.2 read-only state). A shop with no current-month balance row shows its **virtual** balance (Phase 29 CRED-05 selector semantics) — listing must never create rows.
- **D-07:** The list has a **name search box and server-side pagination** (CLAUDE.md §8: every list endpoint paginated; must handle a ~200-shop brand).
- **D-08:** Each row has an **"Add bonus" button**; clicking switches the modal to that shop's bonus form, with a **Back to list** control. (No dropdown picker.)

### Bonus allocation flow (CSUP-01)
- **D-09:** **Single-step confirm with a live preview**: as the amount is typed, the form shows before → after (e.g. "Remaining 35 → 85 · Bonus 20 → 70"); the **Allocate** button is the only confirmation. No separate review screen.
- **D-10:** **No extra guard** beyond the per-allocation 1–10,000 range: no large-amount warning, no cumulative monthly bonus cap.
- **D-11:** On success: a toast ("Added {n} credits to {shop}"), then **return to the shop list** with that row's numbers refreshed, so several shops can be topped up in one session.
- **D-12:** On the **409 period mismatch** (UTC month rolled over while the dialog was open — roadmap note: request echoes the displayed period), show an explanatory message ("A new month started — balances have been refreshed. Review and try again."), **reload that shop's new-month numbers, and keep the typed amount and reason**. No generic error/close.
- **D-13:** Reason stays **optional** (spec §8.2), stored on the BONUS_ALLOCATION ledger row's note.

### Where the allocation is shown (Superadmin only)
- **D-14:** The Superadmin organisations table gets a **"Credits/shop" column**; 0 renders as a muted "Off".
- **D-15:** The View Organisation modal shows **"Monthly credits per shop: {M}"** and, when the current month still runs on a different value because of an N → M change, a note such as **"This month: {N} (changes to {M} on {1st of next month})"**. How "pending" is derived (e.g. from current-month materialised balances vs the org field) is the planner's call; it must be a read that never writes.
- **D-16:** The "Manage credits" modal header shows **org name, current month, and allocation per shop** only (e.g. "Acme — November 2026 · 100 credits per shop"). **No org-level aggregate totals** — cross-shop usage reporting is out of scope (spec §8.3).
- **D-17:** The org row action is labelled **"Manage credits"**, placed alongside "Adjust stores" in the row actions menu.

### Edge cases settled during /gsd-ui-phase 32 (UI-consideration probe)
- **D-18:** A change counts as "immediate" (the 0 → N case) **only when every shop in the org had 0 credits for the whole current month**, i.e. no current-month balance exists with `allocated_credits > 0`. Otherwise (e.g. 100 → 0 earlier this month, then 0 → 50) it is an N → M change and applies from the 1st of next month. The Edit form's live hint (D-01) and the backend use this same rule.
- **D-19:** Allocating bonus to a shop that was **deactivated while the modal was open** returns **404**; the UI shows a toast ("This shop is no longer active") and returns to a reloaded list without that shop (consistent with D-05).

### Carried forward (locked by earlier phases / roadmap — do not re-decide)
- Allocation range 0–10,000 is enforced by DB CHECK `org_monthly_credit_allocation_range` + model validators (Phase 29, T-29-08).
- `ensure_balance(shop_id=...)` is the only way to materialise a balance; read selectors (`get_shop_credit_balance`, `annotate_credit_state`) never write (Phase 29, CRED-05).
- Bonus: org derived server-side from the shop; the request echoes the displayed period (409 on mismatch); balance update is an `F()` increment after `ensure_balance()`; one BONUS_ALLOCATION ledger row + one `shop.credits.bonus_allocated` AuditLog row per allocation (ROADMAP Phase 32 notes, CSUP-01).
- CRED-01 persistence: add the field to `update_organisation`'s `_UPDATABLE_FIELDS`; write `organisation.credits.set` AuditLog **only on an actual change** (ROADMAP notes).
- CRED-06 mechanism: on N → M, materialise current-month balance rows at the old value inside the org-edit atomic; first-time 0 → N is effective immediately (ROADMAP notes).
- Endpoints are non-tenant (`IsAuthenticated & IsSuperadmin`, not `TenantScopedViewSet`), paginated and throttled; AuditLog payloads carry ids and counts only (CLAUDE.md §22).
- Run `tenant-security-auditor` + `orm-performance-auditor` (ROADMAP note; CLAUDE.md §27).

### Claude's Discretion
- Exact copy, layout, toast styling and empty states — defer to `/gsd-ui-phase 32` (roadmap says run it before planning).
- Page size and search semantics for the shop list (prefix vs contains), within D-07.
- API shape (endpoint paths, nested under the org viewset vs separate) and how D-15's "pending change" is computed, within the carried-forward constraints.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & roadmap
- `.planning/REQUIREMENTS.md` — CRED-01, CRED-06, CSUP-01, CSUP-02 and the binding "Spec reconciliations" line (bonus UI on the Superadmin org row with a shop picker; §7.3 refined by CRED-06)
- `.planning/ROADMAP.md` § Phase 32 — goal, success criteria 1–4, implementation notes (period echo / 409, `F()` after `ensure_balance`, `_UPDATABLE_FIELDS`, CRED-06 materialisation, auditors)

### Product spec
- `docs/in-progress/Requirements_Credits_System.md` §8.1 (org create/edit field, label, helper, validation, position below `number_of_stores`), §8.2 (bonus modal content — re-homed to the org row per the reconciliation), §8.3 (Superadmin reporting out of scope), §7.3 (mid-month change — refined by CRED-06), §4 audit event names

### Prior phase context
- `.planning/phases/29-credits-ledger-foundation/29-CONTEXT.md` — ledger/balance model, D-02 PROTECT FKs, D-05 append-only, BONUS_ALLOCATION row shape
- `.planning/phases/29-credits-ledger-foundation/29-0{1,3}-SUMMARY.md` — `ensure_balance`, `get_shop_credit_balance`, `annotate_credit_state` contracts
- `.planning/phases/30-metered-ai-reply-generation/30-CONTEXT.md` — consumption/settlement conventions, AuditLog payload rules

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `frontend/src/widgets/org-management/StoreAllocationModal.tsx` ("Adjust stores") + `RowActionsMenu.tsx`: closest precedent for a per-org-row modal; `frontend/src/entrypoints/org-management.tsx` wires row actions via `window._orgModalHandlers` — add "Manage credits" the same way.
- `CreateOrgModal.tsx` / `EditOrgModal.tsx` / `ViewOrgModal.tsx` / `OrgTable.tsx`: the forms and table that gain the field, hint (D-01), column (D-14) and View note (D-15).
- `apps/credits/selectors/balances.py`: `get_shop_credit_balance` (single shop, virtual when absent) and `annotate_credit_state` (one-query LEFT JOIN annotation for a shop queryset) — the shop list (D-06) should use `annotate_credit_state` to stay N+1-free.
- `apps/credits/services/allocation.py::ensure_balance` — materialise before the bonus `F()` increment and for CRED-06 old-value materialisation.

### Established Patterns
- `OrganisationViewSet` (`apps/organisations/views.py:237`) is `IsAuthenticated, IsSuperadmin`; serializers split list/detail/create/update (`apps/organisations/serializers.py`).
- `update_organisation` (`apps/organisations/services/organisations.py:19,200`) whitelists fields and saves only changed ones — it writes **no AuditLog today**; CRED-01's `organisation.credits.set` is the first audit write there.

### Integration Points
- New Superadmin endpoints for the shop credit list and bonus allocation; bonus writes go through a new `apps/credits` service (ledger BONUS_ALLOCATION + balance `bonus_credits` increment + AuditLog) in one atomic.

</code_context>

<specifics>
## Specific Ideas

- Preview line format: "Remaining 35 → 85 · Bonus 20 → 70".
- Row breakdown format: "Monthly 100 · Bonus 20 · Used 85".
- Modal header format: "Acme — November 2026 · 100 credits per shop".
- 409 copy intent: "A new month started — balances have been refreshed. Review and try again."
- Table: 0 credits shown as muted "Off".

</specifics>

<deferred>
## Deferred Ideas

- Org-level aggregate credit totals / cross-shop usage reporting for Superadmin — spec §8.3 future scope.
- Immediate "kill switch" (N → 0 effective now) — rejected for this phase (D-02); would need a CRED-06 change.
- Cumulative monthly bonus cap or large-amount warning — rejected (D-10).

</deferred>

---

*Phase: 32-superadmin-credit-controls*
*Context gathered: 2026-11-11*
