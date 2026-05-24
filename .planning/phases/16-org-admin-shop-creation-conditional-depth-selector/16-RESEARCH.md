# Phase 16: Org Admin Shop Creation — Conditional Depth Selector - Research

**Researched:** 2026-05-15
**Domain:** Django view context injection, DRF serializer extension, React prop threading, conditional form rendering
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** New `{{ allow_custom_sync_depth|json_script:"shop-org-data" }}` bootstrap tag in `templates/shops/shop_list.html`, immediately after the existing `shop-regions-data` tag. The view adds `"allow_custom_sync_depth": org.allow_custom_sync_depth` to context.
- **D-02:** Payload is flag-only: `{"allow_custom_sync_depth": true/false}`. Not the full org object.
- **D-03:** Entrypoint reads via `parseJson<{ allow_custom_sync_depth: boolean }>("shop-org-data", { allow_custom_sync_depth: false })` and passes down through `ShopModals` → `CreateShopModal` as `allowCustomSyncDepth: boolean`.
- **D-04:** Add `sync_depth = serializers.ChoiceField(choices=Shop.SyncDepth.choices, required=False, default=Shop.SyncDepth.TWO_YEARS)` to `ShopCreateSerializer`.
- **D-05:** No server-side enforcement of the org flag — frontend is the only gate.
- **D-06:** `create_shop()` must accept new keyword argument `sync_depth: str = Shop.SyncDepth.TWO_YEARS` and persist it to the model.
- **D-07:** Dropdown position: after Region, before Phone (listing pill → Shop Name → Region → Review History → Phone → Street Address → footer).
- **D-08:** Helper text below the label (between label and select): `"Sets how far back this shop's initial review sync will go."` using `<p className="mt-1 text-[12px] text-muted">`.
- **D-09:** `<select>` uses the same `inputCls` Tailwind class as the Region select. No new component.
- **D-10:** Default selected option is "Last 2 years" (`TWO_YEARS`). Dropdown completely absent from DOM (not hidden) when `allowCustomSyncDepth === false`.

### Claude's Discretion

- Exact prop threading path through `ShopModals` (prop-drilling is fine given the shallow depth)
- Whether `shop-org-data` bootstrap tag lives on the same line as `shop-regions-data` or in a separate line
- State variable name inside `CreateShopModal` for the selected sync depth value

### Deferred Ideas (OUT OF SCOPE)

- None — discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SDEP-01 | When the parent org has "Allow configurable sync depth" enabled, the Org Admin sees a "Review History" dropdown in the shop creation form with options: "Last 1 year", "Last 2 years", "All time" | Dropdown implemented as `<select>` in CreateShopModal Step 3, conditional on `allowCustomSyncDepth` prop; backed by `ShopCreateSerializer.sync_depth` and `create_shop(sync_depth=...)` |
</phase_requirements>

---

## Summary

Phase 16 is a focused, low-risk extension across three well-understood layers: Django view context, DRF serializer, and React prop threading. Every foundation needed is already in place from Phase 15: `Shop.SyncDepth` TextChoices exist on the model, `sync_depth` is already persisted and exposed by `ShopReadSerializer`, and `Organisation.allow_custom_sync_depth` is a boolean field already on the model. The phase adds no new models, no new migrations, and no new npm packages.

The backend work is minimal: two targeted changes (add `sync_depth` field to `ShopCreateSerializer`, add `sync_depth` kwarg to `create_shop()`). The frontend work is four targeted changes: one new bootstrap tag in the template, one `parseJson` call in the entrypoint, one new prop threaded through `ShopModals`, and one conditional `<select>` block in `CreateShopModal` Step 3. The `**data` splat in `perform_create()` already passes all serializer-validated data to `create_shop()` — once both ends accept `sync_depth`, the data flows through automatically.

**Primary recommendation:** Implement in order — backend (serializer → service → tests) then frontend (types → entrypoint → ShopModals → CreateShopModal → template). No migration needed (model field and migration already exist from Phase 15).

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Deliver `allow_custom_sync_depth` flag to browser | Frontend Server (Django view) | — | The flag is an org-level server-side truth; must be injected at render time, not fetched via AJAX |
| Accept and validate `sync_depth` on shop create | API / Backend (DRF serializer) | — | Input validation is a serializer responsibility per CLAUDE.md §8 |
| Persist `sync_depth` to shop row | API / Backend (service) | Database | `create_shop()` is the single entry point for all shop creation per CLAUDE.md §5 and §24 |
| Conditional dropdown rendering | Browser (React) | — | Pure client-side conditional render based on a prop passed from the entrypoint; no server round-trip needed |
| Org flag gate (show/hide dropdown) | Browser (React) | — | D-05 explicitly assigns this to the frontend only; the backend accepts any valid value regardless |

---

## Standard Stack

### Core (no new packages — all already in the project)

| Library | Version (installed) | Purpose | Why Standard |
|---------|---------------------|---------|--------------|
| Django REST Framework | Current (project) | `ChoiceField` in `ShopCreateSerializer` | Existing serializer infrastructure |
| React 18 | Current (project) | Conditional `<select>` rendering in `CreateShopModal` | Existing frontend framework |
| Tailwind CSS | Current (project) | `inputCls` / `labelCls` — reuse existing constants | Zero new CSS needed |

### No New Packages

This phase installs zero new npm packages and zero new Python packages. All capabilities required are already in the installed project stack.

**Installation:** none required.

---

## Package Legitimacy Audit

No external packages are introduced in this phase.

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| — | — | — | — | — | — | N/A |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

---

## Architecture Patterns

### System Architecture Diagram

```
Django view (shop_list)
  └── adds allow_custom_sync_depth to context
       └── {{ allow_custom_sync_depth|json_script:"shop-org-data" }} in template
            └── parseJson("shop-org-data", fallback=false) in shop-management.tsx
                 └── allowCustomSyncDepth prop → ShopModals
                      └── allowCustomSyncDepth prop → CreateShopModal
                           └── {allowCustomSyncDepth && <select id="cs-sync-depth">}
                                └── syncDepth state (default: "TWO_YEARS")
                                     └── included in ShopCreatePayload.sync_depth
                                          └── POST /api/v1/shops/
                                               └── ShopCreateSerializer.sync_depth (ChoiceField)
                                                    └── perform_create → **data splat
                                                         └── create_shop(sync_depth=...)
                                                              └── Shop.objects.create(sync_depth=...)
```

### Recommended Project Structure

No new files or directories. All changes are to existing files:

```
apps/shops/
  serializers.py           # add sync_depth ChoiceField to ShopCreateSerializer
  services/shops.py        # add sync_depth kwarg to create_shop()
  tests/
    test_services.py       # add tests for sync_depth kwarg
    test_views.py          # add serializer acceptance test + view context test

frontend/src/
  widgets/shop-management/
    types.ts               # add sync_depth?: string to ShopCreatePayload
    CreateShopModal.tsx    # add allowCustomSyncDepth prop + syncDepth state + <select>
    ShopModals.tsx         # add allowCustomSyncDepth to ShopModalsProps + thread to CreateShopModal
  entrypoints/
    shop-management.tsx    # add parseJson("shop-org-data") + pass allowCustomSyncDepth to ShopModals

templates/shops/
  shop_list.html           # add {{ allow_custom_sync_depth|json_script:"shop-org-data" }}

apps/shops/views.py        # add allow_custom_sync_depth to shop_list context
```

### Pattern 1: Bootstrap Tag → React Prop Thread

**What:** Django's `json_script` filter serializes a Python value to a safe `<script>` tag; the entrypoint reads it with `parseJson<T>()` and passes it down as a prop.

**When to use:** Any server-side value that is known at page render time and needs to reach embedded React components without an AJAX request.

**Example (existing pattern from shop-management.tsx):**
```typescript
// Source: frontend/src/entrypoints/shop-management.tsx (lines 16-24 + 34-37)
function parseJson<T>(id: string, fallback: T): T {
  const el = document.getElementById(id);
  if (!el) return fallback;
  try {
    return JSON.parse(el.textContent ?? "") as T;
  } catch {
    return fallback;
  }
}

// Already used for: shop-data, shop-allocation, shop-has-regions, shop-regions-data
// Phase 16 adds: shop-org-data
const orgData = parseJson<{ allow_custom_sync_depth: boolean }>(
  "shop-org-data",
  { allow_custom_sync_depth: false },
);
```

**Django template side:**
```django
{# Placed immediately after shop-regions-data tag (line 30 of shop_list.html) #}
{{ allow_custom_sync_depth|json_script:"shop-org-data" }}
```

**Django view side:**
```python
# apps/shops/views.py — shop_list function, add to render() context dict:
"allow_custom_sync_depth": org.allow_custom_sync_depth,
```

### Pattern 2: DRF ChoiceField with Default

**What:** Add an optional field to `ShopCreateSerializer` using `serializers.ChoiceField` with `required=False` and `default=`.

**When to use:** When a field has a fixed set of valid string values, is optional on input, and always resolves to a known default when absent.

**Example:**
```python
# Source: apps/shops/serializers.py — ShopCreateSerializer class body
sync_depth = serializers.ChoiceField(
    choices=Shop.SyncDepth.choices,
    required=False,
    default=Shop.SyncDepth.TWO_YEARS,
)
```

DRF `ChoiceField` will:
- Reject any value not in `Shop.SyncDepth.choices` with a 400
- Substitute `TWO_YEARS` when the field is absent from the request body
- Pass the validated string through `serializer.validated_data` to `perform_create`

### Pattern 3: Service Keyword Argument Extension

**What:** Add a new keyword-only argument to `create_shop()` with a default matching the model default.

**When to use:** Any time a new column is written at creation time, the service is the sole entry point.

**Example:**
```python
# Source: apps/shops/services/shops.py — create_shop() signature
@transaction.atomic
def create_shop(
    *,
    organisation: Organisation,
    region: Region | None,
    name: str,
    connection_method: str,
    place_id: str = "",
    google_refresh_token: str = "",
    google_account_name: str = "",
    google_location_name: str = "",
    phone: str = "",
    street_address: str = "",
    sync_depth: str = Shop.SyncDepth.TWO_YEARS,   # NEW — Phase 16
    connection_status: str | None = None,
) -> Shop:
    ...
    return Shop.objects.create(
        ...
        sync_depth=sync_depth,   # NEW — Phase 16
    )
```

**Why this works with `perform_create`:** The view's `perform_create()` does:
```python
data = dict(serializer.validated_data)
region = data.pop("region", None)
...
shop = create_shop(organisation=user.organisation, region=region, **data)
```
Once `sync_depth` is in `validated_data` (from the serializer), `**data` splats it into `create_shop()` automatically. No changes needed to `perform_create()` or `ShopViewSet.create()`.

### Pattern 4: Conditional React Render (Absent, Not Hidden)

**What:** Use `{condition && <element>}` React pattern so the element is completely absent from the DOM when the condition is false.

**When to use:** D-10 and §specifics explicitly require DOM absence (not `display:none` / `disabled`) to prevent screen readers from encountering a hidden field and to prevent any form-field value from being submitted when the user's org does not have the flag.

**Example (exact implementation from UI-SPEC):**
```tsx
{allowCustomSyncDepth && (
  <div>
    <label htmlFor="cs-sync-depth" className={labelCls}>
      Review History
    </label>
    <p className="mt-1 text-[12px] text-muted">
      Sets how far back this shop&#39;s initial review sync will go.
    </p>
    <select
      id="cs-sync-depth"
      value={syncDepth}
      onChange={(e) => setSyncDepth(e.target.value as SyncDepth)}
      className={inputCls}
      aria-label="Review History"
    >
      <option value="ONE_YEAR">Last 1 year</option>
      <option value="TWO_YEARS">Last 2 years</option>
      <option value="ALL_TIME">All time</option>
    </select>
  </div>
)}
```

**State initialisation (inside `CreateShopModal`):**
```tsx
const [syncDepth, setSyncDepth] = useState<SyncDepth>("TWO_YEARS");
```

**Reset (inside `reset()` function):**
```tsx
setSyncDepth("TWO_YEARS");
```

### Anti-Patterns to Avoid

- **Hidden or disabled field when `allowCustomSyncDepth === false`:** D-10 requires DOM absence. Do not use `display: none`, `hidden`, `aria-hidden`, or `disabled`. Use `{condition && <div>…</div>}`.
- **Modifying `ShopUpdateSerializer` or `EditShopModal`:** `sync_depth` is set at creation only. `ShopUpdateSerializer` must NOT receive a `sync_depth` field (SDEP-01 scope; UI-SPEC "What Is NOT Changing").
- **Enforcing the org flag in the serializer or service:** D-05 explicitly prohibits server-side enforcement. The backend accepts any valid `sync_depth` value regardless of `allow_custom_sync_depth`.
- **Adding `sync_depth` to `ShopUpdatePayload` in `types.ts`:** Only `ShopCreatePayload` receives `sync_depth?: string`. `ShopUpdatePayload` is untouched.
- **Fetching `allow_custom_sync_depth` via an AJAX call:** It is available at render time via the bootstrap tag pattern. No new API endpoint needed.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Choice validation for sync_depth | Custom `validate_sync_depth()` method | `serializers.ChoiceField(choices=Shop.SyncDepth.choices)` | DRF handles invalid-choice 400 automatically |
| Safe JSON injection into HTML | Custom script tag generation | Django's `json_script` template filter | Built-in XSS protection; used by four existing tags on this page |
| TypeScript string union for SyncDepth | Inline string literal union | `SyncDepth` type already in `types.ts` (line 9) | Type already defined: `"ONE_YEAR" | "TWO_YEARS" | "ALL_TIME"` |
| Dropdown option labels | Hardcoded strings in new constant | `SYNC_DEPTH_LABELS` already in `types.ts` (lines 11–15) | Already maps values to display labels |

**Key insight:** Phase 15 intentionally pre-built the types and model infrastructure. Phase 16 only needs to wire the existing pieces together.

---

## Common Pitfalls

### Pitfall 1: Placing `sync_depth` Before `connection_status` in `create_shop()` signature

**What goes wrong:** `connection_status` has special handling with a `None` default and conditional logic based on `connection_method`. Inserting `sync_depth` after it is safer to avoid confusion.

**Why it happens:** New kwargs are sometimes appended before the last kwarg.

**How to avoid:** Insert `sync_depth: str = Shop.SyncDepth.TWO_YEARS` before `connection_status: str | None = None` in the signature. The `**data` splat in `perform_create` does not depend on argument order.

**Warning signs:** mypy type error if `connection_status` is not last.

---

### Pitfall 2: Forgetting to Reset `syncDepth` in `reset()`

**What goes wrong:** If the user opens the modal, selects "All time", closes it, and re-opens it, the select still shows "All time" on a fresh wizard.

**Why it happens:** `reset()` is called `on !open` via `useEffect`. If `setSyncDepth` is not added to `reset()`, the state persists across open/close cycles.

**How to avoid:** Add `setSyncDepth("TWO_YEARS")` to the `reset()` function in `CreateShopModal.tsx` alongside the other `setState` calls.

**Warning signs:** Manual test: select "All time" → Cancel → re-open → should show "Last 2 years".

---

### Pitfall 3: `sync_depth` Not Included in `ShopCreatePayload` Submission

**What goes wrong:** If `sync_depth` is conditionally assembled into the payload only when `allowCustomSyncDepth` is true but the field is not included in the TypeScript type, TypeScript will flag it.

**Why it happens:** Type mismatch between the payload object literal and `ShopCreatePayload`.

**How to avoid:** Add `sync_depth?: string` to `ShopCreatePayload` in `types.ts`. Both patterns (always include / conditionally include) are valid per UI-SPEC. Always-include is simpler.

**Warning signs:** TypeScript compilation error in `handleSubmit`.

---

### Pitfall 4: `json_script` Boolean Serialisation

**What goes wrong:** Django's `json_script` filter serialises Python `True` as JSON `true` (lowercase). If the template passes a truthy string like `"True"` instead of a boolean, `JSON.parse` will fail or produce a string.

**Why it happens:** Using `{{ org.allow_custom_sync_depth|yesno:"true,false" }}` instead of the boolean directly.

**How to avoid:** Pass `org.allow_custom_sync_depth` (a Python `bool`) directly in the view context. `json_script` handles `bool` → JSON `true`/`false` correctly. Do NOT use `|yesno` on the value passed to `json_script`.

**Warning signs:** `parseJson` fallback returns `false` even when the org has the flag enabled; debug by inspecting the rendered `<script id="shop-org-data">` tag's `textContent`.

---

### Pitfall 5: `OrganisationFactory` Missing `allow_custom_sync_depth` Kwarg

**What goes wrong:** Tests that need `allow_custom_sync_depth=True` find `OrganisationFactory` does not declare the field, causing `TypeError`.

**Why it happens:** `OrganisationFactory` currently has no `allow_custom_sync_depth` attribute; it relies on the model default (`False`). Factory Boy passes unknown kwargs as model field overrides, so `OrganisationFactory(allow_custom_sync_depth=True)` actually works without a factory attribute declaration.

**Confirmed:** The existing Phase 15 tests in `apps/organisations/tests/test_services.py` already use `OrganisationFactory(allow_custom_sync_depth=True)` successfully (lines 518–530). No factory change needed.

**Warning signs:** N/A — this is confirmed to already work.

---

## Code Examples

### Verified: Existing `parseJson` Pattern (reuse exactly)

```typescript
// Source: frontend/src/entrypoints/shop-management.tsx lines 16-37
function parseJson<T>(id: string, fallback: T): T {
  const el = document.getElementById(id);
  if (!el) return fallback;
  try {
    return JSON.parse(el.textContent ?? "") as T;
  } catch {
    return fallback;
  }
}

// Phase 16 addition after line 37:
const orgData = parseJson<{ allow_custom_sync_depth: boolean }>(
  "shop-org-data",
  { allow_custom_sync_depth: false },
);
```

### Verified: Existing `ShopModalsProps` (current, to extend)

```typescript
// Source: frontend/src/widgets/shop-management/ShopModals.tsx lines 59-64
interface ShopModalsProps {
  allocation: AllocationStatus;
  regions: RegionLite[];
  initialPlaceIds?: string[];
  isOrgAdmin?: boolean;
  // Phase 16 adds:
  allowCustomSyncDepth?: boolean;
}
```

### Verified: Existing Region `<select>` (exact copy template for Review History)

```typescript
// Source: frontend/src/widgets/shop-management/CreateShopModal.tsx lines 432-455
<div>
  <label htmlFor="cs-region" className={labelCls}>
    Region
  </label>
  <select
    id="cs-region"
    value={region === "" ? "" : String(region)}
    onChange={(e) => setRegion(e.target.value ? Number(e.target.value) : "")}
    className={fieldError("region") ? inputErrorCls : inputCls}
    aria-label="Region"
  >
    <option value="">Select region…</option>
    {regions.map((r) => (
      <option key={r.id} value={r.id}>
        {r.name} ({r.region_id})
      </option>
    ))}
  </select>
  {fieldError("region") && (
    <p role="alert" className="mt-1 text-[12px]" style={{ color: "#DC2626" }}>
      {fieldError("region")}
    </p>
  )}
</div>
```

The Review History `<select>` replicates this structure with: different id/htmlFor, different label text, a helper `<p>` between label and select (instead of an error `<p>` after), static options instead of mapped regions, and no error state.

### Verified: Existing `SyncDepth` type (already in types.ts)

```typescript
// Source: frontend/src/widgets/shop-management/types.ts lines 9-15
export type SyncDepth = "ONE_YEAR" | "TWO_YEARS" | "ALL_TIME";

export const SYNC_DEPTH_LABELS: Record<SyncDepth, string> = {
  ONE_YEAR: "Last 1 year",
  TWO_YEARS: "Last 2 years",
  ALL_TIME: "All time",
};
```

### Verified: `shop_list` view context dict (current, to extend)

```python
# Source: apps/shops/views.py lines 101-117
return render(
    request,
    "shops/shop_list.html",
    {
        "shops_json": shops_data,
        "shops_count": len(shops_data),
        "allocation": get_allocation_status(organisation=org),
        "has_regions": get_has_regions(organisation_id=org.pk),
        "regions_json": regions_data,
        "page_obj": page_obj,
        "per_page": per_page,
        "per_page_options": list(_SHOP_PER_PAGE_OPTIONS),
        "page_url_params": _shop_page_url_params(request, per_page),
        "page_title": "Shops",
        "is_org_admin": user.role == User.Role.ORG_ADMIN,
        # Phase 16 adds:
        "allow_custom_sync_depth": org.allow_custom_sync_depth,
    },
)
```

### Verified: Bootstrap tag placement in `shop_list.html` (current, to extend)

```django
{# Source: templates/shops/shop_list.html lines 26-31 (current) #}
{% if shops_count > 0 %}
  {{ shops_json|json_script:"shop-data" }}
{% endif %}
{{ allocation|json_script:"shop-allocation" }}
{{ has_regions|json_script:"shop-has-regions" }}
{{ regions_json|json_script:"shop-regions-data" }}
{# Phase 16 adds immediately after: #}
{{ allow_custom_sync_depth|json_script:"shop-org-data" }}
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `sync_depth` not on `ShopCreateSerializer` | `sync_depth` added as optional ChoiceField | Phase 16 | Serializer now accepts and validates `sync_depth` from the frontend |
| `create_shop()` ignores `sync_depth` | `create_shop()` accepts `sync_depth` kwarg | Phase 16 | Persists caller-specified depth at creation; default remains `TWO_YEARS` |
| `ShopCreatePayload` has no `sync_depth` | `sync_depth?: string` added to type | Phase 16 | TypeScript knows the field exists without type errors |
| `shop_list` view context lacks org flag | `allow_custom_sync_depth` added to context | Phase 16 | Bootstrap tag available in template |

**Nothing deprecated:** No existing Phase 15 behaviour is removed or altered. The model default (`TWO_YEARS`) continues to apply when `sync_depth` is absent from the request.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `perform_create`'s `**data` splat automatically passes `sync_depth` from `validated_data` to `create_shop()` without any changes to `perform_create` | Architecture Patterns (Pattern 3) | Low — confirmed by reading `perform_create` source (line 222-256 in views.py): `data = dict(serializer.validated_data)` then `create_shop(..., **data)` |
| A2 | `OrganisationFactory(allow_custom_sync_depth=True)` works without adding the field to the factory declaration | Common Pitfalls (Pitfall 5) | Very Low — confirmed by Phase 15 tests already using this pattern successfully |

**Both assumptions are LOW risk.** A1 is confirmed by reading source code (not training knowledge). A2 is confirmed by existing passing tests.

---

## Open Questions (RESOLVED)

1. **Payload inclusion strategy for `sync_depth`**
   - What we know: UI-SPEC offers two valid patterns — always include `sync_depth` in the payload, or conditionally include only when `allowCustomSyncDepth === true`.
   - What's unclear: The planner must choose one. D-05 says the backend accepts either.
   - Recommendation: Always include `sync_depth` in the payload. Simpler code — no conditional spread. The backend ignores the value when the flag is `False` (accepts it but the flag is frontend-only).
   - RESOLVED: Always include `sync_depth` in the payload unconditionally. Plan 16-02 Task 2 implements this. Backend accepts any valid value per D-05.

---

## Environment Availability

Step 2.6: SKIPPED — this phase is purely code/config changes to existing files with no external tool, service, runtime, or CLI dependencies beyond what is already running.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.3.3 + pytest-django 4.9.0 |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `pytest apps/shops/tests/ -x -q` |
| Full suite command | `pytest --cov=apps --cov-fail-under=85 -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SDEP-01 | `create_shop()` accepts `sync_depth` kwarg and persists it | unit | `pytest apps/shops/tests/test_services.py -x -q -k "sync_depth"` | ✅ (add to existing file) |
| SDEP-01 | `ShopCreateSerializer` accepts valid `sync_depth` values | unit | `pytest apps/shops/tests/ -x -q -k "serializer"` | ✅ (add to existing file) |
| SDEP-01 | `ShopCreateSerializer` rejects invalid `sync_depth` value | unit | `pytest apps/shops/tests/ -x -q -k "sync_depth"` | ✅ (add to existing file) |
| SDEP-01 | `ShopCreateSerializer` defaults `sync_depth` to `TWO_YEARS` when absent | unit | `pytest apps/shops/tests/test_services.py -x -q -k "sync_depth"` | ✅ (add to existing file) |
| SDEP-01 | `POST /api/v1/shops/` with `sync_depth=ONE_YEAR` creates shop with that depth | integration | `pytest apps/shops/tests/test_views.py -x -q -k "sync_depth"` | ✅ (add to existing file) |
| SDEP-01 | `shop_list` view context includes `allow_custom_sync_depth` | integration | `pytest apps/shops/tests/test_views.py -x -q -k "allow_custom"` | ✅ (add to existing file) |

### Sampling Rate

- **Per task commit:** `pytest apps/shops/tests/ -x -q`
- **Per wave merge:** `pytest --cov=apps --cov-fail-under=85 -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

None — existing test infrastructure covers all phase requirements. No new test files, config, or fixtures are needed. All new tests go into existing files (`test_services.py`, `test_views.py`). No new `factories.py` changes required.

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | — |
| V3 Session Management | no | — |
| V4 Access Control | no | — |
| V5 Input Validation | yes | `serializers.ChoiceField(choices=Shop.SyncDepth.choices)` — DRF rejects invalid values with 400 |
| V6 Cryptography | no | — |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Crafted POST with invalid `sync_depth` value | Tampering | DRF `ChoiceField` rejects with 400; not a security concern since no privilege escalation is possible via a bad string |
| Crafted POST with `sync_depth` when org flag is `False` | Tampering | D-05: accepted silently. No security impact — any valid `sync_depth` is functionally equivalent from a data integrity perspective. The org flag is a UX gate, not a security boundary. |
| XSS via `allow_custom_sync_depth` bootstrap tag | XSS | Django's `json_script` filter is XSS-safe (serialises to JSON inside a `<script type="application/json">` tag, which browsers do not execute as JavaScript) |

**Security assessment:** This phase has no meaningful security surface. The `sync_depth` field is a string enum with no privilege implications. The `allow_custom_sync_depth` flag is a read-only boolean from the org model, rendered safely via `json_script`.

---

## Project Constraints (from CLAUDE.md)

Directives that govern Phase 16 implementation:

| Directive | Section | Constraint |
|-----------|---------|------------|
| Services/selectors pattern | §5 | `create_shop()` is the sole entry point for shop creation — no `Shop.objects.create()` calls in views |
| Thin views | §5 | `ShopViewSet.create` and `shop_list` must remain thin — no business logic added there |
| No N+1 | §6 | `org.allow_custom_sync_depth` is already loaded when `org = request.user.organisation` is accessed in `shop_list` — no additional query needed |
| `select_related` | §6.1 | No new FK traversal introduced in this phase; `org` is already on `request.user` |
| Test coverage 85% | §16 | New service behaviour and new serializer field must have tests; existing test files are the right location |
| Write tests first | §24 | Backend test (service + serializer) before implementation |
| No business logic in serializers | §5, §24 | `ShopCreateSerializer` only validates and shapes — no org-flag lookup in the serializer (D-05 enforces this) |
| `update_fields` on partial saves | §6.10 | Not applicable — this is a `create`, not an `update` |
| Type annotations | §24 | `sync_depth: str = Shop.SyncDepth.TWO_YEARS` must be fully annotated in the service signature |

---

## Sources

### Primary (HIGH confidence)

- Codebase — `apps/shops/serializers.py` directly read: current `ShopCreateSerializer` shape confirmed
- Codebase — `apps/shops/services/shops.py` directly read: current `create_shop()` signature confirmed
- Codebase — `apps/shops/views.py` directly read: `perform_create` `**data` splat confirmed; `shop_list` context dict confirmed
- Codebase — `frontend/src/entrypoints/shop-management.tsx` directly read: `parseJson` utility and `ShopModals` render call confirmed
- Codebase — `frontend/src/widgets/shop-management/types.ts` directly read: `SyncDepth` type and `ShopCreatePayload` confirmed
- Codebase — `frontend/src/widgets/shop-management/ShopModals.tsx` directly read: `ShopModalsProps` interface confirmed
- Codebase — `frontend/src/widgets/shop-management/CreateShopModal.tsx` directly read: Step 3 form, `inputCls`/`labelCls` constants, Region `<select>` template confirmed
- Codebase — `templates/shops/shop_list.html` directly read: bootstrap tag positions confirmed
- Codebase — `apps/shops/models.py` directly read: `Shop.SyncDepth` TextChoices, model `sync_depth` field confirmed
- Codebase — `apps/organisations/models.py`: `allow_custom_sync_depth = models.BooleanField(default=False)` confirmed
- Codebase — `apps/shops/tests/factories.py` directly read: `ShopFactory` shape confirmed
- Codebase — `apps/shops/tests/test_services.py` directly read: existing test patterns for `create_shop()` confirmed; Phase 15 `sync_depth` default test present
- Codebase — `apps/shops/tests/test_views.py` directly read: existing API test patterns confirmed; no template view tests exist

### Secondary (MEDIUM confidence)

- CONTEXT.md: All decisions (D-01 through D-10) copied verbatim — design rationale accepted as stated
- UI-SPEC.md: Exact Tailwind classes, field structure, and prop interface shapes locked by the approved UI design contract

### Tertiary (LOW confidence)

None — all findings verified directly against codebase source files.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new packages; all verified in codebase
- Architecture: HIGH — data flow confirmed by reading `perform_create` source; `**data` splat is explicit
- Pitfalls: HIGH — identified from direct code inspection (reset(), ChoiceField behaviour, json_script filter)
- Test patterns: HIGH — existing test files read directly; patterns confirmed

**Research date:** 2026-05-15
**Valid until:** 2026-06-15 (stable domain — no fast-moving dependencies)
