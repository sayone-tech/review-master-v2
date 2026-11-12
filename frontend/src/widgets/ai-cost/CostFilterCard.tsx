// Cost Explorer filter card (mirrors audit-log/AuditLogFilters): the user edits a draft and
// nothing is fetched until Apply; Clear resets to the default range and applies immediately.

import { useEffect, useState } from "react";
import { Calendar } from "lucide-react";
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

const selectCls =
  "appearance-none w-full px-3.5 py-[10px] pr-9 text-[14px] font-normal text-ink bg-white border border-line rounded-[10px] outline-none cursor-pointer transition-[border-color,box-shadow] hover:border-[#D4D4D8] focus:border-ink focus:shadow-[0_0_0_3px_rgba(10,10,10,0.05)]";

const dateInputCls =
  "w-full px-3.5 py-[10px] text-[14px] text-ink bg-white border border-line rounded-[10px] outline-none transition-[border-color,box-shadow] hover:border-[#D4D4D8] focus:border-ink focus:shadow-[0_0_0_3px_rgba(10,10,10,0.05)] [&::-webkit-calendar-picker-indicator]:opacity-60";

function ChevronIcon() {
  return (
    <svg
      width={16}
      height={16}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      className="absolute right-3 top-1/2 -translate-y-1/2 text-subtle pointer-events-none"
    >
      <polyline points="6 9 12 15 18 9" />
    </svg>
  );
}

function FilterLabel({
  icon,
  label,
  htmlFor,
}: {
  icon: React.ReactNode;
  label: string;
  htmlFor: string;
}) {
  return (
    <label
      htmlFor={htmlFor}
      className="inline-flex items-center gap-1.5 text-[12px] font-semibold text-subtle uppercase tracking-[0.05em]"
    >
      <span className="text-muted">{icon}</span>
      <span>{label}</span>
    </label>
  );
}

/** Returns an error message, or null when the draft may be applied. */
export function validateDraft(draft: CostFilters): string | null {
  if (draft.range !== "custom") return null;
  if (!draft.from || !draft.to) return "Select both a From and a To date.";
  if (draft.from > draft.to) return "‘From’ must be on or before ‘To’.";
  const days = Math.round((Date.parse(draft.to) - Date.parse(draft.from)) / 86_400_000) + 1;
  if (days > MAX_CUSTOM_SPAN_DAYS) {
    return `Custom range may span at most ${MAX_CUSTOM_SPAN_DAYS} days.`;
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
    <div className="bg-white border border-line rounded-xl p-4 mb-4" data-testid="ai-cost-filters">
      <div
        className="grid gap-4 items-end"
        style={{
          gridTemplateColumns: isCustom
            ? "minmax(0,1fr) minmax(0,1fr) minmax(0,1fr) auto"
            : "minmax(0,1fr) auto",
        }}
      >
        <div className="flex flex-col gap-1.5">
          <FilterLabel icon={<Calendar size={15} />} label="Date Range" htmlFor="ai-cost-range" />
          <div className="relative">
            <select
              id="ai-cost-range"
              aria-label="Date range"
              className={selectCls}
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
        </div>

        {isCustom && (
          <>
            <div className="flex flex-col gap-1.5">
              <FilterLabel icon={<Calendar size={15} />} label="From" htmlFor="ai-cost-from" />
              <input
                id="ai-cost-from"
                type="date"
                aria-label="From date"
                className={dateInputCls}
                value={draft.from ?? ""}
                onChange={(e) => setDraft((d) => ({ ...d, from: e.target.value || undefined }))}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <FilterLabel icon={<Calendar size={15} />} label="To" htmlFor="ai-cost-to" />
              <input
                id="ai-cost-to"
                type="date"
                aria-label="To date"
                className={dateInputCls}
                value={draft.to ?? ""}
                onChange={(e) => setDraft((d) => ({ ...d, to: e.target.value || undefined }))}
              />
            </div>
          </>
        )}

        <div className="flex items-center gap-2">
          <button
            type="button"
            className="bg-yellow text-black border border-yellow-hover text-[14px] font-semibold px-4 py-2 rounded-[10px] hover:bg-yellow-hover"
            onClick={apply}
          >
            Apply
          </button>
          {hasActiveFilters && (
            <button
              type="button"
              className="text-[14px] text-muted border border-dashed border-line px-4 py-2 rounded-[10px] hover:text-ink hover:border-ink"
              onClick={() => onApply(DEFAULT_FILTERS)}
            >
              Clear
            </button>
          )}
        </div>
      </div>
      {message && (
        <p role="alert" className="mt-3 text-[12px] text-red">
          {message}
        </p>
      )}
    </div>
  );
}
