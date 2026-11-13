# Compact Filter Toolbar Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the tall filter cards (and the Reviews stat cards) on Reviews, Action items and Reports with one compact, instantly-applying toolbar row, a "More filters" panel, active-filter chips, and a slim Reviews number bar.

**Architecture:** A small shared filter kit in `frontend/src/widgets/filters/` (pill select, search, more-filters panel with a draft, chips) is used by the three widgets. Each widget keeps its own filter state and API params; only the filter UI and the apply timing change. Reports' sort state moves from `ReportsTable` to `ReportsWidget`.

**Tech Stack:** React + TypeScript (Vite islands), Tailwind v4 tokens, lucide-react, Vitest + Testing Library (jsdom).

**Spec:** `docs/superpowers/specs/2026-11-13-compact-filter-toolbar-design.md`

## Global Constraints

- Brand tokens only: yellow `#FACC15` (`yellow`), black `#0A0A0A` (`black`), `ink`, `muted`, `line`, `line-soft`, `bg`; Geist; lucide icons. Sentence-case labels, never all caps.
- Controls: 34px-high white pills, icon + current value label + chevron; no field label above. "More filters": black pill, white text, yellow count badge (hidden at 0).
- Apply timing: main-row selects apply on change; search uses the pages' existing 300 ms debounce, immediate on Enter, immediate when cleared; panel = draft with Reset (clears panel filters, applies) and Apply (applies, closes); Escape/click-outside discards the draft; draft re-syncs from applied filters on every open; chips + badge reflect applied state.
- Page-level yellow Apply button removed on all three pages. Pagination resets to page 1 on any filter change. API params unchanged.
- Main rows: Reviews = Search, Store, Rating, Sentiment, More (Tags, Date range, Reply, Comment). Action items = Search, Store, Status, Assignee, More (Scope — only where shown today, never for Staff; Category; Date range). Reports = Period, Reply, Sentiment, sort links (right), "Reset" link when non-default; custom period shows from/to inline and applies only when both set, from ≤ to, ≤ 365 days (else today's inline error, no request).
- Chips only for panel filters; one chip per tag; date chip "Date: 1 Nov – 13 Nov" / "From 1 Nov" / "Until 13 Nov" (× clears both); "Clear all" resets to the page's load defaults; chip row not rendered when no panel filter is active.
- Reviews number bar: "N reviews | X avg rating | N awaiting reply | N% positive" with thin vertical rules (not characters), awaiting in amber, positive in green; same data/filters as today's cards.
- No horizontal overflow at any width; the row may wrap below ~1024px, controls stack on phones.
- Requirements first (CLAUDE.md §24): `UI-FILTER-01`, `UI-FILTER-02`.

## Review Focus

1. A tag clicked on a review row while the panel is closed, then the panel opened — the draft shows that tag (Task 2 test).
2. Escape pressed with the nested tag list open — closes only the tag list; a second Escape closes the panel (Task 1 + Task 2 tests).
3. Reports custom period with only one date entered — no request is made, no crash (Task 4 test).
4. Search box cleared with the ✕/backspace — results refresh immediately, not after the debounce (Task 2/3 tests).
5. Staff on Action items — the panel never offers Scope and no Scope chip can appear (Task 3 test).

---

### Task 1: Shared filter kit + requirements

**Files:**
- Create: `frontend/src/widgets/filters/FilterSelect.tsx`, `FilterSearch.tsx`, `MoreFiltersPanel.tsx`, `FilterChips.tsx`, `chips.ts`, `index.ts`
- Test: `frontend/src/widgets/filters/filters.test.tsx`
- Modify: `.planning/REQUIREMENTS.md` (Post-v0.10 changes table)

**Interfaces:**
- Produces:
  - `FilterSelect<T extends string | number>(props: { icon: LucideIcon; ariaLabel: string; placeholder: string; value: T | undefined; options: { value: T; label: string }[]; onChange: (v: T | undefined) => void }): JSX.Element` — a native `<select>` styled as the pill (first option = placeholder → `undefined`).
  - `FilterSearch(props: { value: string; placeholder: string; ariaLabel: string; onChange: (v: string) => void; onSubmit?: () => void }): JSX.Element` — fires `onChange` per keystroke (the widget's hook debounces), `onSubmit` on Enter.
  - `MoreFiltersPanel<D>(props: { applied: D; activeCount: number; onApply: (draft: D) => void; onReset: () => void; children: (draft: D, setDraft: (d: D) => void) => ReactNode }): JSX.Element` — button "More filters" + badge; panel ~320px, right-aligned under the button; draft initialised from `applied` on every open; Apply → `onApply(draft)` + close; Reset → `onReset()` + close; Escape/outside click → close, discard draft, focus back to the button. Escape is ignored by the panel when the event was already handled by a nested listbox (`event.defaultPrevented`); clicks inside elements marked `data-filter-popover` count as inside.
  - `FilterChips(props: { chips: { key: string; label: string; onRemove: () => void }[]; onClearAll: () => void }): JSX.Element | null` — `null` when `chips` is empty.
  - `formatDateChip(from?: string, to?: string): string | null` in `chips.ts` — `("2026-11-01","2026-11-13") → "Date: 1 Nov – 13 Nov"`, `("2026-11-01", undefined) → "From 1 Nov"`, `(undefined,"2026-11-13") → "Until 13 Nov"`, both missing → `null`.

- [ ] **Step 1: Add requirement rows** `UI-FILTER-01` (compact shared filter toolbar on Reviews, Action items, Reports — spec §2.1–2.4, 2.6–2.7) and `UI-FILTER-02` (Reviews slim number bar — spec §2.5), status `🚧 In progress`.
- [ ] **Step 2: Write failing tests** in `filters.test.tsx`:
  - `FilterSelect shows the selected label and calls onChange with undefined for the placeholder`
  - `FilterSearch calls onChange per keystroke and onSubmit on Enter`
  - `MoreFiltersPanel shows a badge only when activeCount > 0`
  - `MoreFiltersPanel initialises the draft from applied on every open` (open, change draft, Escape, change `applied` prop, reopen → shows new applied value)
  - `MoreFiltersPanel Apply calls onApply with the draft and closes; Reset calls onReset and closes`
  - `MoreFiltersPanel Escape and outside click discard the draft and return focus to the button`
  - `MoreFiltersPanel ignores an Escape already handled by a nested listbox` (child calls `e.preventDefault()` on Escape → panel stays open)
  - `FilterChips renders nothing with no chips; × calls onRemove; Clear all calls onClearAll`
  - `formatDateChip` — the four cases above.
- [ ] **Step 3: Run** `cd frontend && npx vitest run src/widgets/filters` — Expected: FAIL (modules missing).
- [ ] **Step 4: Implement** the five files per Interfaces and Global Constraints (styles from the approved mockup `.superpowers/brainstorm/7608-1794569358/content/toolbar-all-pages.html`).
- [ ] **Step 5: Run** the same command — Expected: PASS.
- [ ] **Step 6: Commit** `feat(ui): shared compact filter kit`.

---

### Task 2: Reviews toolbar + slim number bar

**Files:**
- Modify: `frontend/src/widgets/review-management/ReviewFilters.tsx` (rewrite onto the kit; keep `TagsFilter` as the nested multi-select inside the panel, wrapped in `data-filter-popover`, calling `preventDefault()` on the Escape it handles), `ReviewStatsCards.tsx` (becomes the slim bar; keep the export name so the widget import stays), `ReviewManagementWidget.tsx` (wire instant apply; remove Apply)
- Test: `ReviewManagementWidget.test.tsx` (update), new `ReviewFilters.test.tsx`

**Interfaces:**
- Consumes: Task 1 kit. Existing `ReviewFilterParams` and `applyFilters` in the widget; `useReviews` keeps its 300 ms search debounce.
- Produces: `ReviewFilters` props become `{ shops; filters: ReviewFilterParams; availableTags; onChange: (next: ReviewFilterParams) => void }` — every change (row, panel apply, chip remove, clear all) calls `onChange` with the full next params and `page: 1`.

- [ ] **Step 1: Write failing tests** (`ReviewFilters.test.tsx`):
  - `changing Store applies immediately with page 1` (onChange called once with `{shop: 3, page: 1}` merged)
  - `panel Apply sends tags, from/to date, is_replied and has_comment together`
  - `chips show Not replied, each tag, and the date chip; × removes just that filter`
  - `Clear all resets every filter including search`
  - `opening the panel after an external tag filter shows that tag selected` (Review Focus 1)
  - `Escape with the tag list open closes only the tag list` (Review Focus 2)
  - `clearing the search box applies immediately` (Review Focus 4)
  - Widget test: `renders the number bar with "reviews", "avg rating", "awaiting reply", "positive" and no Apply button`
- [ ] **Step 2: Run** `cd frontend && npx vitest run src/widgets/review-management` — Expected: new tests FAIL.
- [ ] **Step 3: Implement** per Interfaces; bar classes: white, `border-line`, `rounded-[10px]`, vertical rule separators `w-px h-[18px] bg-line`; awaiting `text-amber`, positive `text-green`.
- [ ] **Step 4: Run** the same command — Expected: PASS.
- [ ] **Step 5: Commit** `feat(reviews): compact filter toolbar and slim number bar`.

---

### Task 3: Action items toolbar

**Files:**
- Modify: `frontend/src/widgets/action-items/ActionItemFilters.tsx`, `ActionItemManagementWidget.tsx`
- Test: `frontend/src/widgets/action-items/ActionItemFilters.test.tsx` (create or extend), widget tests touching filters

**Interfaces:**
- Consumes: Task 1 kit; existing `ListParams`, `handleApplyFilters`/`handleReset` logic (keep the param mapping, drop the Apply button).
- Produces: `ActionItemFilters` props become `{ userRole; shops; teamMembers; filters: ListParams; onChange: (next: Partial<ListParams>) => void; onClearAll: () => void }`.

- [ ] **Step 1: Write failing tests:**
  - `Status and Assignee apply immediately`
  - `panel offers Scope, Category and Date range for Org Admin`
  - `panel offers only Category and Date range for Staff and no Scope chip ever renders` (Review Focus 5)
  - `chips show Category and the date chip; Clear all resets to defaults`
  - `clearing the search box applies immediately` (Review Focus 4)
- [ ] **Step 2: Run** `cd frontend && npx vitest run src/widgets/action-items` — Expected: new tests FAIL.
- [ ] **Step 3: Implement** per Interfaces.
- [ ] **Step 4: Run** the same command — Expected: PASS.
- [ ] **Step 5: Commit** `feat(action-items): compact filter toolbar`.

---

### Task 4: Reports toolbar (sort lifted, custom dates, Reset)

**Files:**
- Modify: `frontend/src/widgets/reports/FilterBar.tsx`, `ReportsWidget.tsx` (owns `sortKey`/`sortDir` + `DEFAULT_FILTERS`), `ReportsTable.tsx` (receives sort as props; rendering unchanged)
- Test: `frontend/src/widgets/reports/ReportsWidget.test.tsx` (update), new `FilterBar.test.tsx`

**Interfaces:**
- Consumes: Task 1 `FilterSelect`.
- Produces: `FilterBar` props `{ filters: ReportFilters; onChange: (next: ReportFilters) => void; sortKey; sortDir; onSort: (key) => void }`; `ReportsTable` props gain `sortKey`, `sortDir`, `onSort`.

- [ ] **Step 1: Write failing tests:**
  - `Period, Reply and Sentiment apply immediately`
  - `custom period shows from/to inputs and applies only when both dates are valid` (one date → no `onChange`; from > to → inline error, no `onChange`; > 365 days → inline error; valid → one `onChange`) (Review Focus 3)
  - `Reset link appears only when filters differ from 30d/all/all and restores them`
  - `sort links in the toolbar reorder the table exactly as before` (widget test)
  - Widget test: `no Apply button`
- [ ] **Step 2: Run** `cd frontend && npx vitest run src/widgets/reports` — Expected: new tests FAIL.
- [ ] **Step 3: Implement** per Interfaces; reuse today's validation messages verbatim.
- [ ] **Step 4: Run** the same command — Expected: PASS.
- [ ] **Step 5: Commit** `feat(reports): compact filter toolbar with sort on the same row`.

---

### Task 5: Verification and close-out

**Files:**
- Modify: `.planning/REQUIREMENTS.md` (UI-FILTER-01/02 → `✅ Delivered`)

- [ ] **Step 1:** Run `cd frontend && npx vitest run && npm run build`, `uv run pre-commit run --all-files`, `uv run pytest -q -p no:cacheprovider` — Expected: all pass.
- [ ] **Step 2:** (controller) Browser pass as Org Admin at 1440, 1280, 900 and 390px on Reviews, Action items and Reports: one row, panel, chips, number bar, instant apply, custom period, no horizontal overflow; first Reviews row within roughly the top quarter of the panel at 1440×900.
- [ ] **Step 3:** Mark UI-FILTER-01/02 delivered; commit `docs: compact filter toolbar delivered`.
