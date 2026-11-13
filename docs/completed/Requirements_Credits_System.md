# AI Reply Credits System

**Version 1.0 · November 2026**

## 1. Document Overview

This document specifies the AI Reply Credits system for ReviewBee. It introduces a per-shop credit allocation that governs how many AI-generated review replies a shop can create per month, surfaces remaining credit balances throughout the admin UI, and gives Superadmins the controls to allocate and top up credits for each organisation.

The feature responds to a real cost pressure: every "Generate with AI" reply call hits OpenAI and costs money. Without a credit system, heavy users could consume disproportionate AI budget. Credits give Superadmin a lever to allocate AI budget per organisation and per shop, and give the end user a visible accounting of their usage.

All conventions established in earlier modules (Django 6, Celery, OpenAI integration, AI cost tracking, services and selectors pattern, tenant scoping) apply unchanged and are not repeated here.

### 1.1 Scope

- New `credits` field on Organisation model, set during organisation creation by Superadmin
- Per-shop credit balance derived from the organisation's allocation (every shop in the organisation gets the organisation's credit amount at the start of each month)
- Credit consumption on AI-reply generation, with variable cost (1, 2, or 3 credits) based on the source review's comment length
- Visible remaining credits on Shop Details, Reviews page, and the reply screen
- "Generate with AI" button hidden for reviews with zero comment text (stars only)
- Credit cost displayed on the "Generate with AI" button before the user clicks
- "Buy More Credits" placeholder flow — popup saying "Contact ReviewBee admin"
- Superadmin controls to allocate extra credits to a specific shop for the current month
- Monthly credit renewal via Celery Beat; unused credits lapse
- Full audit log entries on every credit consumption and allocation event

### 1.2 Out of Scope

- Payment gateway integration for buying credits (a later iteration — "Buy More" is a placeholder popup here)
- Credit rollover across months
- Per-user credit allocation (credits are per-shop, not per-user)
- Credit transfer between shops within an organisation
- Credit alerts via email or push notification (in-app visibility only)
- Credit analytics dashboard for Org Admin (visibility, yes; analytics widget, no)
- Historical credit usage reporting for Superadmin beyond the audit log
- Different credit cost formulas per organisation (one formula applies to all)
- Credits for other AI features (dashboard summarization, action item generation) — scope here is reply generation only

### 1.3 Dependencies

- Superadmin module (Organisation creation flow extended)
- Shops and Team scoping
- Reviews list and reply UI
- OpenAI integration and AiUsageLog (credits sit alongside AiUsageLog for cost attribution)

## 2. Roles and Permissions

| Action | Superadmin | Org Admin / Manager | Staff |
|---|---|---|---|
| Set organisation-level credit allocation | Yes (at org creation and edit) | No | No |
| View organisation's credit allocation | Yes | Yes (read-only) | No |
| Allocate extra credits to a specific shop for the current month | Yes | No | No |
| View shop's remaining credits | Yes | Yes | Yes (for accessible shops) |
| Consume credits by generating AI reply | Not applicable | Yes | Yes (for accessible shops) |
| View credit audit log | Yes (org-wide) | Yes (org-wide) | No |
| Tap "Buy More Credits" and see the contact popup | Yes | Yes | Yes |

## 3. Data Model

### 3.1 Organisation Model Update

Add one field:

- `monthly_credit_allocation` — integer, NOT NULL, default 0. The number of credits granted to each shop in this organisation at the start of every calendar month. Set by Superadmin during organisation creation; editable thereafter from the organisation detail page.

### 3.2 New Model — ShopCreditBalance

Represents the current month's credit balance for one shop. One row per shop per month.

Fields:

- `id` (PK, UUID)
- `shop_id` (FK to Shop, indexed)
- `organisation_id` (FK to Organisation, indexed, denormalised for faster queries)
- `period_year` — integer (e.g., 2026)
- `period_month` — integer 1–12
- `allocated_credits` — integer, NOT NULL. The base allocation inherited from `Organisation.monthly_credit_allocation` at the start of the month
- `bonus_credits` — integer, NOT NULL, default 0. Extra credits added by Superadmin after the initial allocation
- `consumed_credits` — integer, NOT NULL, default 0
- `created_at`, `updated_at`

Constraints:

- Unique on `(shop_id, period_year, period_month)` — one balance row per shop per month
- Indexes: `(organisation_id, period_year, period_month)` for Superadmin reports

Derived field (computed, not stored):

- `remaining_credits = allocated_credits + bonus_credits - consumed_credits`

### 3.3 New Model — CreditTransaction

Immutable log of every credit event. Separate from the audit log because credit events are frequent and have a structured shape worth querying directly.

Fields:

- `id` (PK, UUID)
- `shop_credit_balance_id` (FK to ShopCreditBalance, indexed)
- `shop_id` (FK, denormalised for query convenience, indexed)
- `organisation_id` (FK, denormalised, indexed)
- `transaction_type` — enum: `INITIAL_ALLOCATION` | `BONUS_ALLOCATION` | `CONSUMPTION` | `LAPSED`
- `credits_delta` — integer, positive for allocation, negative for consumption, negative for lapse
- `review_id` (FK to Review, nullable) — populated for CONSUMPTION transactions
- `ai_usage_log_id` (FK to AiUsageLog, nullable) — populated for CONSUMPTION, links to the actual OpenAI call
- `performed_by_user_id` (FK to User, nullable) — populated for CONSUMPTION (the user who clicked Generate) and BONUS_ALLOCATION (the Superadmin); null for INITIAL_ALLOCATION and LAPSED (system actions)
- `notes` — text, nullable (used for Superadmin bonus allocation reason)
- `created_at`

Indexes: `(shop_id, created_at)`, `(organisation_id, created_at)`

### 3.4 Audit Log Additions

New audit actions:

- `organisation.credits.set` — Superadmin sets or changes the organisation's monthly allocation
- `shop.credits.allocated` — monthly initial allocation runs for a shop
- `shop.credits.bonus_allocated` — Superadmin adds bonus credits to a specific shop
- `shop.credits.consumed` — AI reply generation consumes credits
- `shop.credits.lapsed` — end-of-month lapse of unused credits

## 4. Credit Cost Algorithm

The credit cost per AI reply generation is a function of the source review's comment length. The rationale: longer reviews need more context in the OpenAI prompt, consuming more tokens, so they cost more credits.

### 4.1 Cost Tiers

| Review Comment Length (chars) | Credits Cost |
|---|---|
| 1 – 100 | 1 credit |
| 101 – 500 | 2 credits |
| 501 and above | 3 credits |

Reviews with zero comment text (stars only, no written review) do not expose the "Generate with AI" button at all — see §5.2.

### 4.2 Why This Algorithm

Three reasons:

1. **Predictability** — three discrete tiers are easy for end users to understand and anticipate. A continuous formula would feel opaque.
2. **Alignment with cost** — based on real OpenAI pricing for GPT-4o-mini, a 1500-character review generates roughly 3× the prompt tokens of a 50-character review. The 1–2–3 credit scale tracks this roughly without being pedantic.
3. **Headroom for future adjustment** — thresholds and credit values are stored in configuration (settings or a small constants table), not hard-coded in business logic, so they can be tuned without code changes.

### 4.3 Implementation Location

A single pure function in `apps/reviews/services/credit_cost.py`:

```python
def calculate_credit_cost(*, comment_length: int) -> int:
    if comment_length <= 0:
        raise ValueError("Zero-length comments do not qualify for AI reply generation")
    if comment_length <= 100:
        return 1
    if comment_length <= 500:
        return 2
    return 3
```

This function is called by both the frontend (via a lightweight endpoint) and the backend consumption service, so the displayed cost and the actual charge always match.

## 5. "Generate with AI" Button Behavior

### 5.1 Button Visibility

The "Generate with AI" button is visible on the reply composition area ONLY when the source review has non-empty comment text.

- Review with stars only, no comment → the button is hidden entirely. The reply composer is still available for manual typing; only the AI-generation shortcut is removed.
- Review with any comment text (1+ character) → the button is visible.

This behavior is enforced on both the frontend (to avoid showing an unusable button) and the backend (to reject AI-generation requests for empty-comment reviews with a 400 response).

### 5.2 Button Label — Showing the Credit Cost

The button label includes the credit cost so users know what they're about to spend:

- 1 credit: `Generate with AI (1 credit)`
- 2 credits: `Generate with AI (2 credits)`
- 3 credits: `Generate with AI (3 credits)`

Button sub-caption (optional small gray text beneath the button): `X credits remaining this month`.

### 5.3 Button States

| State | Trigger | Behavior |
|---|---|---|
| Enabled | Shop has enough remaining credits | Yellow button, clickable |
| Disabled — insufficient credits | Remaining credits < cost | Gray button, tooltip "Not enough credits. Buy more credits below." A "Buy More Credits" link appears beneath the composer |
| Loading | User clicked, generation in progress | Spinner inside button, disabled, other actions disabled |
| Error | Generation failed | Button returns to enabled; inline error above composer; credits NOT consumed |

### 5.4 Confirmation on Click

To avoid accidental spend, clicking "Generate with AI" shows a brief confirmation inline above the composer:

- "This will use X credits. Continue?" with Confirm (primary) and Cancel (secondary) buttons.
- If the user has set a "Don't ask again this session" checkbox, the confirmation is skipped for the remainder of the session.

Optional — this adds friction and may be removed after user testing. Lock the decision during design review.

### 5.5 Successful Generation Flow

1. User clicks Generate with AI
2. Confirmation shown (if not dismissed)
3. On Confirm, button goes to loading state
4. Backend atomically: verifies credit sufficiency, deducts credits, calls OpenAI, parses response, writes CreditTransaction + AiUsageLog
5. Generated reply text populates the composer textarea
6. User reviews, edits if needed, clicks Submit Reply as usual
7. Toast: "Reply generated. X credits used. Y credits remaining."

If the user cancels or discards the generated reply before submitting, **credits are still consumed** — the OpenAI call already happened and was billed. This behavior is documented in a small tooltip near the Generate button on first use.

## 6. Credit Consumption Service

### 6.1 Flow

The consumption service is atomic and must prevent race conditions (two concurrent generate requests racing on the same shop balance).

```
def consume_credits_for_ai_reply(*, shop_id, review_id, user_id):
    1. Compute credit_cost from review.text length
    2. Begin transaction
    3. SELECT FOR UPDATE on current month's ShopCreditBalance for the shop
       - If row does not exist, create it with allocated_credits = org.monthly_credit_allocation
    4. If remaining_credits < credit_cost:
         - Raise InsufficientCreditsError
    5. Call OpenAI to generate reply (inside transaction? see §6.2)
    6. Increment consumed_credits by credit_cost
    7. Insert CreditTransaction row with transaction_type=CONSUMPTION
    8. Insert AiUsageLog row (existing OpenAI integration pattern)
    9. Write audit log entry
    10. Commit transaction
    11. Return generated reply text
```

### 6.2 OpenAI Call Inside or Outside the Transaction?

Trade-off:

- **Inside transaction**: slow OpenAI call (300–1000ms) holds the row lock, blocking other generate requests for the same shop. For a busy shop, this serialises replies.
- **Outside transaction**: faster, but harder to maintain atomicity. If OpenAI fails after the credit deduction commits, the user lost credits for nothing.

Recommended approach: **two-phase pattern**.

1. Phase A (reserve): SELECT FOR UPDATE, verify credits, atomically deduct and commit. Write a CreditTransaction with status=RESERVED.
2. Phase B (fulfill): call OpenAI outside the transaction. On success, update the CreditTransaction to status=COMMITTED. On failure, refund by reverse-updating consumed_credits and marking the transaction REFUNDED.

This requires adding a `status` enum to CreditTransaction (`RESERVED | COMMITTED | REFUNDED`). Cleaner concurrency and honest refunds on OpenAI failure.

A reaper Celery Beat task runs every 10 minutes to refund RESERVED transactions older than 5 minutes (safety net for crashed workers).

### 6.3 Refund Policy

Credits are refunded only when the OpenAI call itself fails (network error, OpenAI 5xx, OpenAI rate limit). Credits are NOT refunded when:

- The user cancels the generated reply before submitting
- The user discards the generated reply
- The user edits the generated reply heavily
- The generated reply is of low quality in the user's judgment

This aligns credit cost with OpenAI cost: ReviewBee paid OpenAI for the call, so credits are spent.

## 7. Monthly Allocation and Renewal

### 7.1 Initial Allocation (On Shop's First AI Reply of the Month)

ShopCreditBalance rows are created lazily. When the first AI reply attempt happens in a given month for a given shop, the service checks for a ShopCreditBalance for `(shop_id, current_year, current_month)`. If none exists, it creates one with `allocated_credits = organisation.monthly_credit_allocation` and `consumed_credits = 0`.

Lazy creation avoids running a batch job that inserts rows for shops that may never use AI replies that month.

### 7.2 Monthly Renewal — Lapse of Unused Credits

A Celery Beat task runs at 00:05 on the 1st of every month (in UTC) that:

1. Finds all ShopCreditBalance rows for the **previous** month (not the just-started month)
2. For each with `remaining_credits > 0`:
   - Writes a CreditTransaction with transaction_type=LAPSED, credits_delta = -remaining_credits
   - No change to ShopCreditBalance fields themselves (the row stays as a historical record)
3. Writes a single audit log entry per shop: `shop.credits.lapsed` with the lapsed amount

New balance rows for the current month are NOT pre-created. They're created lazily (§7.1) on first use.

### 7.3 Changing Organisation Allocation Mid-Month

When Superadmin changes `Organisation.monthly_credit_allocation`, the change applies **only to future months**. Current-month ShopCreditBalance rows are not modified.

If Superadmin needs to give more credits to a shop in the current month, they use the Bonus Allocation feature (§8.2), not the organisation-level allocation.

> **Amendment (2026-11-13): inactive shops.** Credit allocation skips inactive shops. Editing the organisation's allocation never creates or raises current-month balances for shops with `is_active=False`; balances they already hold are left as-is (no clawback) and lapse normally. A shop reactivated later gets its month's allocation lazily on first use (§7.1). This supersedes Phase 29 D-13 for allocation only; balance reads and the lapse job still treat inactive shops like active ones.

## 8. Superadmin Credit Management

### 8.1 Organisation Creation and Edit

Add a `Credits per shop per month` numeric field to the Create Organisation and Edit Organisation forms:

- Field label: "Monthly credits per shop"
- Helper text: "Each shop in this organisation gets this many credits at the start of every month. Unused credits lapse."
- Validation: integer, 0 to 10,000
- Default: 0 (feature disabled — no AI replies possible)
- Field position: below `number_of_stores` in the form

Changing this value on an existing organisation writes an audit log entry `organisation.credits.set` and takes effect from the next calendar month.

### 8.2 Bonus Allocation to a Specific Shop

New action on the Shop Details screen (Superadmin only, hidden for all other roles):

- Button: "Allocate Bonus Credits" in the shop header area
- Opens a modal:
  - "Allocate bonus credits to {shop_name} for {current month}"
  - Current state shown read-only: `Monthly allocation: 100 · Bonus so far: 20 · Consumed: 85 · Remaining: 35`
  - Input: "Additional credits to allocate" — integer, 1 to 10,000
  - Textarea: "Reason (optional)" — stored in CreditTransaction.notes
  - Buttons: Cancel + Allocate (primary yellow)
- On submit: updates ShopCreditBalance.bonus_credits, writes CreditTransaction with type=BONUS_ALLOCATION, writes audit log entry

Only Superadmin sees this button. Org Admin and Manager see the balance but cannot allocate bonus credits.

### 8.3 Credit Usage Visibility (Superadmin)

Future scope (not in this iteration): a Superadmin report showing credits consumed per organisation per month. For now, Superadmin can query the audit log and CreditTransaction table directly via Django admin for investigation.

## 9. Credit Visibility — Where Credits Are Shown

### 9.1 Shop Details Page (Org Admin, Manager, Staff, Superadmin)

New card in the Shop Details screen: "AI Reply Credits"

- Current month label: "November 2026"
- Big number: `35 / 100` (remaining / allocated, where allocated = allocated_credits + bonus_credits)
- Small progress bar beneath — green up to 75%, amber 75–95%, red above 95%
- Footer line: "85 credits used · 15 credits available"
- Resets-on line: "Renews on Dec 1, 2026"
- Buy More Credits link (all roles) — opens the Buy More popup (§9.4)
- For Superadmin: additional "Allocate Bonus Credits" button (§8.2)

### 9.2 Shops List Row

Each row in the Shops list has a small credit indicator:

- Compact badge in a dedicated column: "35 credits"
- Color-coded: green if remaining > 25% of allocated, amber if 5–25%, red if < 5%, dark gray if 0
- Tooltip on hover: "35 credits remaining this month"
- Clicking the badge opens the Shop Details credits card

### 9.3 Shops Side Menu / Shop Switcher

If the application has a shop switcher (e.g., filter dropdown that scopes other pages to a specific shop), each entry shows a tiny credit badge inline:

- Format: `Downtown Store · 35 cr`
- Red if 0

### 9.4 Reply Screen

In the reply composer area (expanded inline, or in the full-screen mobile compose):

- Small text above the composer: `This shop has X credits remaining this month.`
- "Generate with AI" button shows the cost per §5.2
- If remaining credits < cost: Buy More Credits link appears directly beneath the composer

### 9.5 Buy More Credits Popup (Placeholder)

Triggered by any "Buy More Credits" link on any surface:

- Modal title: "Buy More Credits"
- Icon: Mail or similar
- Body text: "To purchase additional credits for this month, please contact your ReviewBee administrator. Credits are added within 24 hours of request."
- "Contact Admin" button (primary) — opens mailto: link to the support email configured in settings (`settings.REVIEWBEE_SUPPORT_EMAIL`)
- "Close" button (secondary)

No actual purchase flow in this iteration. The UX hook is designed so that a future payment flow can swap the popup for a real checkout without changing where the triggers are placed.

## 10. API Endpoints

| Method + Path | Purpose | Permissions |
|---|---|---|
| `GET /api/v1/shops/{shop_id}/credits/` | Current month's balance for a shop | Role has access to shop |
| `GET /api/v1/shops/{shop_id}/credits/history/` | Transaction history (paginated, filterable by type) | Role has access to shop |
| `POST /api/v1/reviews/{review_id}/generate-reply/` | Generate AI reply, consume credits | Role has reply permission for shop |
| `GET /api/v1/reviews/{review_id}/generate-reply/cost/` | Lightweight endpoint returning the credit cost for this review (so UI shows the right number) | Role has access to shop |
| `POST /api/v1/superadmin/shops/{shop_id}/credits/bonus/` | Superadmin bonus allocation | Superadmin only |
| `PATCH /api/v1/superadmin/organisations/{org_id}/` | Existing endpoint; extended to accept `monthly_credit_allocation` | Superadmin only |

Rate limits:

- `generate-reply`: 30 per minute per user (matches existing reply rate limit)
- `cost` endpoint: unthrottled — it's a cheap read

## 11. Celery Tasks

| Task | Queue | Schedule | Purpose |
|---|---|---|---|
| `lapse_previous_month_credits_task` | `default` | Beat: 1st of every month at 00:05 UTC | Writes LAPSED transactions for unused credits |
| `reap_stale_reserved_transactions_task` | `default` | Beat: every 10 minutes | Refunds RESERVED credit transactions older than 5 minutes |

Both are thin wrappers over service functions following the Celery convention from CLAUDE.md.

## 12. Settings Additions

```python
# config/settings/base.py

# Credit cost tiers (comment length in chars -> credit cost)
REVIEWBEE_CREDIT_TIERS = [
    (100, 1),
    (500, 2),
    (10000, 3),  # effective ceiling; any comment above 500 chars costs 3
]

# Grace period for reserved transactions before reaper refunds them
REVIEWBEE_CREDIT_RESERVATION_TTL_MINUTES = 5

# Support contact for "Buy More Credits" placeholder
REVIEWBEE_SUPPORT_EMAIL = env("REVIEWBEE_SUPPORT_EMAIL", default="support@reviewbee.in")
```

## 13. Tech Design Notes

### 13.1 Module Layout

- `apps/credits/` — new Django app
  - `models.py` — ShopCreditBalance, CreditTransaction
  - `services/consumption.py` — the two-phase consume-and-fulfill service
  - `services/allocation.py` — initial lazy allocation + bonus allocation
  - `services/lapse.py` — monthly lapse logic
  - `services/credit_cost.py` — the pure cost calculation function
  - `selectors/balances.py` — read primitives for current balance + history
  - `tasks.py` — Celery tasks for lapse and reaper

- `apps/reviews/services/replies.py` — extend to call `apps.credits.services.consumption` before OpenAI call

### 13.2 Query Optimisation

- `GET /api/v1/shops/{shop_id}/credits/` must resolve in a single query via a selector that eagerly joins the latest ShopCreditBalance row
- `GET /api/v1/shops/` (existing list endpoint) should annotate `remaining_credits` to avoid an N+1 when rendering the credits badge per row — use a single subquery or window function
- Add index `(shop_id, period_year, period_month)` on ShopCreditBalance — already covered by the unique constraint

### 13.3 Concurrency

The SELECT FOR UPDATE in the consumption service is the critical section. Under extreme concurrency (same shop, many simultaneous generate requests), requests serialise. This is acceptable — a shop's team is unlikely to click Generate more than a few times per second.

### 13.4 Timezone

Monthly boundaries use UTC consistently. This simplifies the lapse scheduling and avoids timezone edge cases where a shop in Asia/Kolkata would have different "months" than one in UTC. The label displayed to users ("Resets Dec 1, 2026") shows the date in the user's timezone but the underlying boundary is UTC midnight.

## 14. Acceptance Criteria

### 14.1 Data Model

1. `Organisation.monthly_credit_allocation` field is present with a default of 0 and NOT NULL constraint
2. ShopCreditBalance rows are created lazily on first use in a month
3. CreditTransaction rows are immutable (no update endpoint)
4. Unique constraint `(shop_id, period_year, period_month)` enforced

### 14.2 Credit Consumption

5. Generating an AI reply atomically deducts credits and writes a CreditTransaction with status=COMMITTED on OpenAI success
6. OpenAI failure refunds credits and marks the transaction REFUNDED
7. Concurrent generate requests on the same shop are serialised correctly — no over-spending past the limit
8. Credits cost matches the tier algorithm: 1 / 2 / 3 credits for 1–100 / 101–500 / 501+ chars
9. Attempting to generate when `remaining_credits < cost` returns 402 with a clear error message
10. Reviews with zero comment text reject AI generation requests with 400 server-side
11. The reaper task refunds RESERVED transactions older than 5 minutes

### 14.3 Monthly Allocation and Lapse

12. Lapse task runs at 00:05 UTC on the 1st of each month
13. All previous-month ShopCreditBalance rows with remaining > 0 produce a LAPSED CreditTransaction
14. Previous-month ShopCreditBalance rows stay in the database as historical records
15. Current-month balance is created lazily with `allocated_credits = organisation.monthly_credit_allocation`
16. Changing organisation allocation mid-month does not alter current-month balances

### 14.4 UI Visibility

17. Shop Details page shows AI Reply Credits card with current / allocated and progress bar
18. Shops list row shows a compact credit badge color-coded by remaining
19. Reply composer shows remaining credits above and cost on the Generate button
20. "Generate with AI" button is hidden for reviews with empty comment text
21. "Buy More Credits" popup appears from any entry point and shows the placeholder contact message

### 14.5 Superadmin Controls

22. Organisation Create and Edit forms include the `Monthly credits per shop` field with validation
23. Shop Details page shows the "Allocate Bonus Credits" button to Superadmin only
24. Submitting a bonus allocation updates ShopCreditBalance.bonus_credits and writes a CreditTransaction with type=BONUS_ALLOCATION
25. Audit log entries are written for every credit-affecting event listed in §3.4

### 14.6 Permissions

26. Org Admin / Manager / Staff cannot change the organisation's monthly allocation
27. Org Admin / Manager / Staff cannot allocate bonus credits
28. Staff cannot see credits for shops outside their StaffAccessScope
29. The `/api/v1/superadmin/*` credit endpoints return 403 for non-Superadmin requests

### 14.7 Buy More Credits Popup Test Cases

30. Popup opens from Shop Details credits card
31. Popup opens from Shops list row when credits are 0
32. Popup opens from reply composer when credits are insufficient
33. Popup opens from shop switcher/menu
34. "Contact Admin" button opens a mailto link with `settings.REVIEWBEE_SUPPORT_EMAIL`
35. Popup closes on Cancel, backdrop click, or ESC key
36. Popup is accessible — focus trapped inside, ARIA labels on buttons, dismissable by keyboard

### 14.8 Cross-cutting

37. All new endpoints have CaptureQueriesContext tests asserting query count ceilings
38. All credit consumption writes to AiUsageLog as well (existing OpenAI integration pattern preserved)
39. Timezone handling is correct — lapse at UTC midnight, display in user timezone
40. The cost-tier function has unit tests covering boundary cases (0, 1, 100, 101, 500, 501, 10000)

## 15. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Users spend credits and get low-quality AI replies, then complain | Clear messaging: "Generated replies are AI-suggested. Review and edit before sending." No refunds on edit or discard. Users learn to inspect before clicking. |
| Race condition causes a shop to go negative on credits | SELECT FOR UPDATE inside transaction prevents this. Unit tests simulate concurrent requests. |
| OpenAI outage consumes all credits silently | Two-phase pattern refunds on OpenAI failure. Reaper task cleans up stuck reservations. |
| Monthly lapse fires late (Celery Beat issue) | Idempotent lapse task — running late or twice has no bad effect. Monitoring alerts if the task hasn't completed by 00:30 UTC. |
| Superadmin forgets to set allocation on new organisation | Default of 0 means feature is off; users see "No credits available" with Buy More link until Superadmin acts. Not a correctness bug, just a config reminder. |
| Credit tier thresholds don't match actual OpenAI costs | Tiers in config, not code; adjustable without deploy. Periodic review against actual AiUsageLog costs. |
| Users confused by lapse of unused credits | Visible messaging on Shop Details: "Credits reset on Dec 1 — unused credits do not carry forward." Avoids surprise. |
| Buy More Credits popup is a dead end — users may churn | The placeholder is intentional. A real payment integration should follow within 2 months to avoid this. |
