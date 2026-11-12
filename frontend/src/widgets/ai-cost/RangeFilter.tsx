import type { CostFilters, RangeKey } from "./types";

const OPTIONS: { key: RangeKey; label: string }[] = [
  { key: "this_month", label: "This month" },
  { key: "last_month", label: "Last month" },
  { key: "7d", label: "Last 7 days" },
  { key: "30d", label: "Last 30 days" },
  { key: "90d", label: "Last 90 days" },
  { key: "custom", label: "Custom" },
];

const inputCls = "h-9 rounded-sm border border-line bg-white px-2 text-[13px] text-ink";

export function RangeFilter({
  filters,
  onChange,
  error,
}: {
  filters: CostFilters;
  onChange: (f: CostFilters) => void;
  error?: string | null;
}) {
  return (
    <div>
      <div className="flex flex-wrap items-center gap-2">
        <select
          aria-label="Date range"
          className={inputCls}
          value={filters.range}
          onChange={(e) => {
            const range = e.target.value as RangeKey;
            onChange(range === "custom" ? { ...filters, range } : { range });
          }}
        >
          {OPTIONS.map((o) => (
            <option key={o.key} value={o.key}>
              {o.label}
            </option>
          ))}
        </select>
        {filters.range === "custom" && (
          <>
            <input
              type="date"
              aria-label="From date"
              className={inputCls}
              value={filters.from ?? ""}
              onChange={(e) => onChange({ ...filters, from: e.target.value || undefined })}
            />
            <input
              type="date"
              aria-label="To date"
              className={inputCls}
              value={filters.to ?? ""}
              onChange={(e) => onChange({ ...filters, to: e.target.value || undefined })}
            />
          </>
        )}
      </div>
      {error && (
        <p role="alert" className="mt-1 text-[12px] text-red-600">
          {error}
        </p>
      )}
    </div>
  );
}
