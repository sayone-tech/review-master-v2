import { useState } from "react";
import { Calendar, SlidersHorizontal, X } from "lucide-react";
import type { DashboardFilters, DateRangePreset, Region, Shop } from "./types";
import { isDefault } from "./useFilterState";

interface FilterBarProps {
  filters: DashboardFilters;
  regions: Region[];
  shops: Shop[];
  onApply: (region_id: number | null, shop_id: number | null, range: DateRangePreset, from: string | null, to: string | null) => void;
  onClear: () => void;
}

const selectCls =
  "px-3 py-2 text-[13.5px] bg-white border border-line rounded-md focus:outline-none focus:ring focus:ring-black/[0.06] focus:border-ink";

interface Draft {
  region_id: number | null;
  shop_id: number | null;
  range: DateRangePreset;
  from: string;
  to: string;
}

function validateCustom(from: string, to: string): string | null {
  if (!from || !to) return "Please select both start and end dates.";
  const f = new Date(from);
  const t = new Date(to);
  if (f > t) return "End date must be after start date.";
  if ((t.getTime() - f.getTime()) / 86400000 > 365)
    return "Date range cannot exceed 365 days.";
  return null;
}

export function FilterBar({ filters, regions, shops, onApply, onClear }: FilterBarProps) {
  const [draft, setDraft] = useState<Draft>({
    region_id: filters.region_id,
    shop_id: filters.shop_id,
    range: filters.range,
    from: filters.date_from ?? "",
    to: filters.date_to ?? "",
  });
  const [dateError, setDateError] = useState<string | null>(null);

  const visibleShops =
    draft.region_id === null
      ? shops
      : shops.filter((s) => s.region_id === draft.region_id);

  const handleRangeChange = (val: string) => {
    setDraft((d) => ({ ...d, range: val as DateRangePreset, from: "", to: "" }));
    setDateError(null);
  };

  const handleRegionChange = (val: string) => {
    setDraft((d) => ({
      ...d,
      region_id: val === "" ? null : Number(val),
      shop_id: null,
    }));
  };

  const handleApply = () => {
    if (draft.range === "custom") {
      const err = validateCustom(draft.from, draft.to);
      if (err) {
        setDateError(err);
        return;
      }
    }
    setDateError(null);
    onApply(
      draft.region_id,
      draft.shop_id,
      draft.range,
      draft.range === "custom" ? draft.from : null,
      draft.range === "custom" ? draft.to : null,
    );
  };

  const handleReset = () => {
    setDraft({ region_id: null, shop_id: null, range: "all", from: "", to: "" });
    setDateError(null);
    onClear();
  };

  const hasActiveFilters =
    !isDefault(filters) ||
    filters.date_from !== null ||
    filters.date_to !== null;

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-stretch gap-2">
        {/* Region */}
        <select
          aria-label="Filter by region"
          className={`${selectCls} flex-1 min-w-[140px]`}
          value={draft.region_id ?? ""}
          onChange={(e) => handleRegionChange(e.target.value)}
        >
          <option value="">All Regions</option>
          {regions.map((r) => (
            <option key={r.id} value={r.id}>{r.name}</option>
          ))}
        </select>

        {/* Store — cascades from region */}
        <select
          aria-label="Filter by store"
          className={`${selectCls} flex-1 min-w-[140px]`}
          value={draft.shop_id ?? ""}
          onChange={(e) =>
            setDraft((d) => ({
              ...d,
              shop_id: e.target.value === "" ? null : Number(e.target.value),
            }))
          }
        >
          <option value="">All Stores</option>
          {visibleShops.map((s) => (
            <option key={s.id} value={s.id}>{s.name}</option>
          ))}
        </select>

        {/* Date preset */}
        <select
          aria-label="Filter by date range"
          className={`${selectCls} flex-1 min-w-[150px]`}
          value={draft.range}
          onChange={(e) => handleRangeChange(e.target.value)}
        >
          <option value="all">All time</option>
          <option value="7d">Last 7 days</option>
          <option value="30d">Last 30 days</option>
          <option value="90d">Last 90 days</option>
          <option value="custom">Custom range</option>
        </select>

        {/* Filter button */}
        <button
          type="button"
          onClick={handleApply}
          className="inline-flex items-center gap-1.5 px-4 py-2 bg-black text-yellow text-[13.5px] font-semibold rounded-md hover:bg-ink/90 shrink-0"
        >
          <SlidersHorizontal size={13} aria-hidden="true" />
          Filter
        </button>

        {/* Reset — only when active */}
        {hasActiveFilters && (
          <button
            type="button"
            onClick={handleReset}
            className="inline-flex items-center gap-1.5 px-3 py-2 text-[13.5px] text-muted hover:text-ink border border-line rounded-md bg-white shrink-0"
          >
            <X size={13} aria-hidden="true" />
            Reset
          </button>
        )}
      </div>

      {/* Inline custom date row — shown only when custom is selected */}
      {draft.range === "custom" && (
        <div className="flex flex-wrap items-stretch gap-2">
          <div className="flex items-center gap-1 px-3 bg-white border border-line rounded-md text-[13.5px] flex-[2] min-w-[280px] focus-within:border-ink focus-within:ring focus-within:ring-black/[0.06]">
            <Calendar size={13} className="text-muted shrink-0" aria-hidden="true" />
            <input
              type="date"
              aria-label="From date"
              className="flex-1 bg-transparent focus:outline-none text-[13px] min-w-0 py-2"
              value={draft.from}
              onChange={(e) => {
                setDraft((d) => ({ ...d, from: e.target.value }));
                setDateError(null);
              }}
            />
            <span className="text-muted px-0.5">–</span>
            <input
              type="date"
              aria-label="To date"
              className="flex-1 bg-transparent focus:outline-none text-[13px] min-w-0 py-2"
              value={draft.to}
              onChange={(e) => {
                setDraft((d) => ({ ...d, to: e.target.value }));
                setDateError(null);
              }}
            />
          </div>
          {dateError && (
            <p className="self-center text-[13px] text-red">{dateError}</p>
          )}
        </div>
      )}
    </div>
  );
}
