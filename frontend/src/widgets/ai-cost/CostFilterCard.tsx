// Cost Explorer date filter, shown inline in the page header (Apply/Clear semantics mirror
// audit-log/AuditLogFilters): the user edits a draft and nothing is fetched until Apply; Clear
// resets to the default range and applies immediately.

import { useEffect, useState } from "react";
import type { CostFilters, RangeKey } from "./types";

const OPTIONS: { key: RangeKey; label: string }[] = [
  { key: "this_month", label: "This month" },
  { key: "last_month", label: "Last month" },
  { key: "7d", label: "Last 7 days" },
  { key: "30d", label: "Last 30 days" },
  { key: "90d", label: "Last 90 days" },
  { key: "custom", label: "Custom" },
];

const MAX_CUSTOM_SPAN_DAYS = 365;
const DEFAULT_FILTERS: CostFilters = { range: "this_month" };

const fieldCls =
  "py-2 text-[13.5px] text-ink bg-white border border-line rounded-md outline-none transition-[border-color,box-shadow] hover:border-[#D4D4D8] focus:border-ink focus:shadow-[0_0_0_3px_rgba(10,10,10,0.05)]";

function ChevronIcon() {
  return (
    <svg
      width={14}
      height={14}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className="absolute right-2.5 top-1/2 -translate-y-1/2 text-subtle pointer-events-none"
    >
      <polyline points="6 9 12 15 18 9" />
    </svg>
  );
}

/** Returns an error message, or null when the draft may be applied. */
export function validateDraft(draft: CostFilters): string | null {
  if (draft.range !== "custom") return null;
  if (!draft.from || !draft.to) return "Choose both a start and an end date.";
  if (draft.from > draft.to) return "The start date must be on or before the end date.";
  const days = Math.round((Date.parse(draft.to) - Date.parse(draft.from)) / 86_400_000) + 1;
  if (days > MAX_CUSTOM_SPAN_DAYS) {
    return `Choose a range of ${MAX_CUSTOM_SPAN_DAYS} days or fewer.`;
  }
  return null;
}

export function CostFilterCard({
  filters,
  onApply,
  serverError,
}: {
  filters: CostFilters;
  onApply: (f: CostFilters) => void;
  serverError?: string | null;
}) {
  const [draft, setDraft] = useState<CostFilters>(filters);
  const [error, setError] = useState<string | null>(null);

  // Resync when the applied filters change (Clear, Back/forward navigation).
  useEffect(() => {
    setDraft(filters);
    setError(null);
  }, [filters.range, filters.from, filters.to]); // eslint-disable-line react-hooks/exhaustive-deps

  const hasActiveFilters = filters.range !== DEFAULT_FILTERS.range;
  const isCustom = draft.range === "custom";
  const message = error ?? serverError ?? null;

  const apply = () => {
    const err = validateDraft(draft);
    setError(err);
    if (err) return;
    onApply(draft.range === "custom" ? draft : { range: draft.range });
  };

  return (
    <div className="flex flex-col items-start gap-1.5 sm:items-end" data-testid="ai-cost-filters">
      <div className="flex flex-wrap items-center gap-2">
        <div className="relative">
          <select
            id="ai-cost-range"
            aria-label="Date range"
            className={`${fieldCls} appearance-none cursor-pointer pl-3 pr-8`}
            value={draft.range}
            onChange={(e) => {
              const range = e.target.value as RangeKey;
              setError(null);
              setDraft(range === "custom" ? { ...draft, range } : { range });
            }}
          >
            {OPTIONS.map((o) => (
              <option key={o.key} value={o.key}>
                {o.label}
              </option>
            ))}
          </select>
          <ChevronIcon />
        </div>

        {isCustom && (
          <>
            <input
              id="ai-cost-from"
              type="date"
              aria-label="From date"
              className={`${fieldCls} px-2.5 [&::-webkit-calendar-picker-indicator]:opacity-60`}
              value={draft.from ?? ""}
              onChange={(e) => setDraft((d) => ({ ...d, from: e.target.value || undefined }))}
            />
            <span className="text-[13px] text-muted">to</span>
            <input
              id="ai-cost-to"
              type="date"
              aria-label="To date"
              className={`${fieldCls} px-2.5 [&::-webkit-calendar-picker-indicator]:opacity-60`}
              value={draft.to ?? ""}
              onChange={(e) => setDraft((d) => ({ ...d, to: e.target.value || undefined }))}
            />
          </>
        )}

        <button
          type="button"
          className="px-3.5 py-2 bg-yellow text-black border border-yellow-hover rounded-md text-[13.5px] font-medium hover:bg-yellow-hover"
          onClick={apply}
        >
          Apply
        </button>
        {hasActiveFilters && (
          <button
            type="button"
            className="px-3 py-2 rounded-md text-[13.5px] font-medium text-muted hover:bg-line-soft hover:text-ink"
            onClick={() => onApply(DEFAULT_FILTERS)}
          >
            Clear
          </button>
        )}
      </div>
      {message && (
        <p role="alert" className="text-[12.5px] text-red">
          {message}
        </p>
      )}
    </div>
  );
}
