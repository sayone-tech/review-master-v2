import { useState } from "react";
import { Calendar, RefreshCw, Tag } from "lucide-react";
import type { DashboardFilters, DateRangePreset, Region, Shop } from "./types";
import { isDefault } from "./useFilterState";

interface FilterBarProps {
  filters: DashboardFilters;
  regions: Region[];
  shops: Shop[];
  onApply: (region_id: number | null, shop_id: number | null, range: DateRangePreset, from: string | null, to: string | null) => void;
  onClear: () => void;
}

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

function StoreIcon({ size = 15 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 9l1-4h16l1 4"/>
      <path d="M3 9v11h18V9"/>
      <path d="M9 9v11"/>
      <path d="M15 9v11"/>
    </svg>
  );
}

interface ControlProps {
  label: string;
  icon: React.ReactNode;
  hint?: string;
  children: React.ReactNode;
}

function FilterControl({ label, icon, hint, children }: ControlProps) {
  return (
    <label className="flex flex-col gap-1.5 min-w-0">
      <span className="inline-flex items-center gap-1.5 text-[11.5px] font-medium text-subtle uppercase tracking-[0.05em]">
        <span className="text-muted">{icon}</span>
        <span>{label}</span>
        {hint && (
          <span className="normal-case tracking-normal font-normal text-[11px] text-faint italic ml-1">{hint}</span>
        )}
      </span>
      {children}
    </label>
  );
}

const selectCls =
  "appearance-none w-full px-3.5 py-[10px] pr-9 text-[14px] font-medium text-ink bg-white border border-line rounded-[10px] outline-none cursor-pointer transition-[border-color,box-shadow] hover:border-[#D4D4D8] focus:border-ink focus:shadow-[0_0_0_3px_rgba(10,10,10,0.05)]";

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
      if (err) { setDateError(err); return; }
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
    <div className="bg-white border border-line rounded-xl p-3.5 mb-[18px]">
      {/* Main filter row */}
      <div
        style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr auto", gap: 14, alignItems: "end" }}
      >
        {/* Region */}
        <FilterControl label="Region" icon={<Tag size={15} />}>
          <div className="relative">
            <select
              aria-label="Filter by region"
              className={selectCls}
              value={draft.region_id ?? ""}
              onChange={(e) => handleRegionChange(e.target.value)}
            >
              <option value="">All regions</option>
              {regions.map((r) => (
                <option key={r.id} value={r.id}>{r.name}</option>
              ))}
            </select>
            <ChevronIcon />
          </div>
        </FilterControl>

        {/* Store */}
        <FilterControl
          label="Store"
          icon={<StoreIcon size={15} />}
        >
          <div className="relative">
            <select
              aria-label="Filter by store"
              className={selectCls}
              value={draft.shop_id ?? ""}
              onChange={(e) =>
                setDraft((d) => ({
                  ...d,
                  shop_id: e.target.value === "" ? null : Number(e.target.value),
                }))
              }
            >
              <option value="">All stores</option>
              {visibleShops.map((s) => (
                <option key={s.id} value={s.id}>{s.name}</option>
              ))}
            </select>
            <ChevronIcon />
          </div>
        </FilterControl>

        {/* Date range */}
        <FilterControl label="Range" icon={<Calendar size={15} />}>
          <div className="relative">
            <select
              aria-label="Filter by date range"
              className={selectCls}
              value={draft.range}
              onChange={(e) => handleRangeChange(e.target.value)}
            >
              <option value="all">All time</option>
              <option value="7d">Last 7 days</option>
              <option value="30d">Last 30 days</option>
              <option value="90d">Last 90 days</option>
              <option value="custom">Custom range</option>
            </select>
            <ChevronIcon />
          </div>
        </FilterControl>

        {/* Actions */}
        <div className="flex items-center gap-2">
          {hasActiveFilters && (
            <button
              type="button"
              onClick={handleReset}
              className="inline-flex items-center gap-1.5 px-3 py-[10px] rounded-[10px] bg-transparent border border-dashed border-line text-subtle text-[13px] hover:text-ink hover:border-ink transition-colors"
            >
              <RefreshCw size={13} aria-hidden="true" />
              Reset
            </button>
          )}
          <button
            type="button"
            onClick={handleApply}
            className="inline-flex items-center gap-1.5 px-3.5 py-[10px] rounded-[10px] bg-yellow text-black border border-yellow-hover text-[14px] font-medium hover:bg-yellow-hover transition-colors shrink-0"
          >
            Apply
          </button>
        </div>
      </div>

      {/* Custom date row */}
      {draft.range === "custom" && (
        <div className="flex items-center gap-3 mt-3 pt-3 border-t border-dashed border-line">
          <div className="flex-1 flex items-center gap-2 px-3.5 py-[10px] border border-line rounded-[10px] bg-white focus-within:border-ink focus-within:shadow-[0_0_0_3px_rgba(10,10,10,0.05)] transition-[border-color,box-shadow]">
            <Calendar size={15} className="text-subtle shrink-0" aria-hidden="true" />
            <input
              type="date"
              aria-label="From date"
              className="flex-1 bg-transparent focus:outline-none text-[14px] text-ink min-w-0"
              value={draft.from}
              max={draft.to || undefined}
              onChange={(e) => { setDraft((d) => ({ ...d, from: e.target.value })); setDateError(null); }}
            />
          </div>
          <span className="text-faint text-base font-medium shrink-0">—</span>
          <div className="flex-1 flex items-center gap-2 px-3.5 py-[10px] border border-line rounded-[10px] bg-white focus-within:border-ink focus-within:shadow-[0_0_0_3px_rgba(10,10,10,0.05)] transition-[border-color,box-shadow]">
            <Calendar size={15} className="text-subtle shrink-0" aria-hidden="true" />
            <input
              type="date"
              aria-label="To date"
              className="flex-1 bg-transparent focus:outline-none text-[14px] text-ink min-w-0"
              value={draft.to}
              min={draft.from || undefined}
              onChange={(e) => { setDraft((d) => ({ ...d, to: e.target.value })); setDateError(null); }}
            />
          </div>
          {dateError && (
            <p className="text-[13px] text-red shrink-0">{dateError}</p>
          )}
        </div>
      )}
    </div>
  );
}

function ChevronIcon() {
  return (
    <svg
      width={16} height={16}
      viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth={2} strokeLinecap="round" strokeLinejoin="round"
      className="absolute right-3 top-1/2 -translate-y-1/2 text-subtle pointer-events-none"
    >
      <polyline points="6 9 12 15 18 9" />
    </svg>
  );
}
