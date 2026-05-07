import { useState } from "react";
import type { DashboardFilters, Region, Shop } from "./types";
import { isDefault } from "./useFilterState";

interface FilterBarProps {
  filters: DashboardFilters;
  regions: Region[];
  shops: Shop[];
  onRegionChange: (id: number | null) => void;
  onStoreChange: (id: number | null) => void;
  onRangeChange: (preset: DashboardFilters["range"]) => void;
  onCustomRange: (from: string, to: string) => void;
  onClear: () => void;
}

const selectCls =
  "px-3 py-2 text-[14px] bg-white border border-line rounded-md min-w-[160px] focus:outline-none focus:ring focus:ring-black/[0.06] focus:border-ink";

function validateCustom(from: string, to: string): string | null {
  if (!from || !to) return "Please select both dates.";
  const f = new Date(from);
  const t = new Date(to);
  if (f > t) return "End date must be after start date.";
  const days = Math.floor((t.getTime() - f.getTime()) / 86400000);
  if (days > 365) return "Date range cannot exceed 365 days.";
  return null;
}

export function FilterBar({
  filters,
  regions,
  shops,
  onRegionChange,
  onStoreChange,
  onRangeChange,
  onCustomRange,
  onClear,
}: FilterBarProps) {
  const [customFrom, setCustomFrom] = useState(filters.date_from ?? "");
  const [customTo, setCustomTo] = useState(filters.date_to ?? "");
  const [customError, setCustomError] = useState<string | null>(null);

  const visibleShops =
    filters.region_id === null
      ? shops
      : shops.filter((s) => s.region_id === filters.region_id);

  const handleRangeChange = (value: string) => {
    const preset = value as DashboardFilters["range"];
    onRangeChange(preset);
    if (preset === "custom") {
      setCustomFrom(filters.date_from ?? "");
      setCustomTo(filters.date_to ?? "");
      setCustomError(null);
    }
  };

  const handleApplyCustom = () => {
    const err = validateCustom(customFrom, customTo);
    if (err) {
      setCustomError(err);
      return;
    }
    setCustomError(null);
    onCustomRange(customFrom, customTo);
  };

  const customPanelOpen = filters.range === "custom";
  const applyDisabled = !customFrom || !customTo;

  return (
    <div className="flex flex-wrap gap-3 items-center relative">
      {/* Region select */}
      <select
        aria-label="Filter by region"
        className={selectCls}
        value={filters.region_id ?? ""}
        onChange={(e) =>
          onRegionChange(e.target.value === "" ? null : Number(e.target.value))
        }
      >
        <option value="">All Regions</option>
        {regions.map((r) => (
          <option key={r.id} value={r.id}>
            {r.name}
          </option>
        ))}
      </select>

      {/* Store select — cascades from region */}
      <select
        aria-label="Filter by store"
        className={selectCls}
        value={filters.shop_id ?? ""}
        onChange={(e) =>
          onStoreChange(e.target.value === "" ? null : Number(e.target.value))
        }
      >
        <option value="">All Stores</option>
        {visibleShops.map((s) => (
          <option key={s.id} value={s.id}>
            {s.name}
          </option>
        ))}
      </select>

      {/* Date Range select + custom panel */}
      <div className="relative">
        <select
          aria-label="Filter by date range"
          className={selectCls}
          value={filters.range}
          onChange={(e) => handleRangeChange(e.target.value)}
        >
          <option value="7d">Last 7 days</option>
          <option value="30d">Last 30 days</option>
          <option value="90d">Last 90 days</option>
          <option value="custom">Custom range</option>
        </select>

        {/* Custom date panel */}
        {customPanelOpen && (
          <div
            className="absolute top-[calc(100%+4px)] z-50 w-[320px] bg-white rounded-card border border-line shadow-sm p-4"
            style={{
              opacity: 1,
              transform: "translateY(0)",
              transition: "opacity 150ms ease-out, transform 150ms ease-out",
            }}
          >
            <div className="flex gap-2 mb-2">
              <input
                type="date"
                aria-label="From date"
                className="w-full px-3 py-2 text-[14px] bg-white border border-line rounded-md focus:outline-none focus:ring focus:ring-black/[0.06] focus:border-ink"
                value={customFrom}
                onChange={(e) => {
                  setCustomFrom(e.target.value);
                  setCustomError(null);
                }}
              />
              <input
                type="date"
                aria-label="To date"
                className="w-full px-3 py-2 text-[14px] bg-white border border-line rounded-md focus:outline-none focus:ring focus:ring-black/[0.06] focus:border-ink"
                value={customTo}
                onChange={(e) => {
                  setCustomTo(e.target.value);
                  setCustomError(null);
                }}
              />
            </div>

            {customError && (
              <p className="text-[14px] text-red mb-2">{customError}</p>
            )}

            <button
              type="button"
              onClick={handleApplyCustom}
              disabled={applyDisabled}
              className={`px-4 py-2 bg-black text-yellow text-[14px] font-bold rounded-md transition-colors duration-150${
                applyDisabled ? " opacity-50 cursor-not-allowed" : " hover:bg-ink/90"
              }`}
            >
              Apply
            </button>
          </div>
        )}
      </div>

      {/* Clear Filters */}
      <button
        type="button"
        onClick={onClear}
        disabled={isDefault(filters)}
        className={`text-muted hover:text-ink border border-line rounded-md bg-white px-3 py-2 text-[14px] transition-colors duration-150${
          isDefault(filters) ? " opacity-40 cursor-not-allowed pointer-events-none" : ""
        }`}
      >
        Clear Filters
      </button>

      {/* UTC notice */}
      <span className="text-[14px] text-subtle ml-auto self-center">All dates in UTC</span>
    </div>
  );
}
