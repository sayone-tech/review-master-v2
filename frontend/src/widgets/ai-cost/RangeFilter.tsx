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
  // Custom dates live locally until both are set and ordered, so half-filled
  // input never reaches the API (which would 400 and blank the page).
  const [customPending, setCustomPending] = useState(false);
  const [from, setFrom] = useState(filters.from ?? "");
  const [to, setTo] = useState(filters.to ?? "");

  useEffect(() => {
    setCustomPending(false);
    setFrom(filters.from ?? "");
    setTo(filters.to ?? "");
  }, [filters.range, filters.from, filters.to]);

  const showCustom = customPending || filters.range === "custom";
  const ordered = from !== "" && to !== "" && from <= to;
  const invalidOrder = from !== "" && to !== "" && from > to;

  const commit = (f: string, t: string) => {
    if (f && t && f <= t) onChange({ range: "custom", from: f, to: t });
  };
  return (
    <div>
      <div className="flex flex-wrap items-center gap-2">
        <select
          aria-label="Date range"
          className={inputCls}
          value={showCustom ? "custom" : filters.range}
          onChange={(e) => {
            const range = e.target.value as RangeKey;
            if (range === "custom") {
              setCustomPending(true);
              commit(from, to);
            } else {
              setCustomPending(false);
              onChange({ range });
            }
          }}
        >
          {OPTIONS.map((o) => (
            <option key={o.key} value={o.key}>
              {o.label}
            </option>
          ))}
        </select>
        {showCustom && (
          <>
            <input
              type="date"
              aria-label="From date"
              className={inputCls}
              value={from}
              onChange={(e) => {
                setFrom(e.target.value);
                commit(e.target.value, to);
              }}
            />
            <input
              type="date"
              aria-label="To date"
              className={inputCls}
              value={to}
              onChange={(e) => {
                setTo(e.target.value);
                commit(from, e.target.value);
              }}
            />
          </>
        )}
      </div>
      {invalidOrder && !ordered && (
        <p role="alert" className="mt-1 text-[12px] text-red-600">
          &lsquo;From&rsquo; must be on or before &lsquo;To&rsquo;.
        </p>
      )}
      {error && (
        <p role="alert" className="mt-1 text-[12px] text-red-600">
          {error}
        </p>
      )}
    </div>
  );
}
