import { useEffect, useState } from "react";
import type { DashboardFilters, DateRangePreset, Region, Shop } from "./types";
import { isDefault } from "./useFilterState";

interface FilterBarProps {
  filters: DashboardFilters;
  regions: Region[];
  shops: Shop[];
  onApply: (region_id: number | null, shop_id: number | null, range: DateRangePreset, from: string | null, to: string | null) => void;
  onClear: () => void;
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

const RANGE_OPTIONS: { value: DateRangePreset; label: string }[] = [
  { value: "all", label: "all time" },
  { value: "7d", label: "the last 7 days" },
  { value: "30d", label: "the last 30 days" },
  { value: "90d", label: "the last 90 days" },
  { value: "custom", label: "a custom range" },
];

// One sentence part: the visible yellow words sit under a transparent native
// <select>, so the part is as wide as its words and phones get the native picker.
const PART =
  "relative inline-block max-w-full align-baseline rounded-[3px] [&:has(:focus-visible)]:outline-2 [&:has(:focus-visible)]:outline-offset-[3px] [&:has(:focus-visible)]:outline-[#FACC15]";
const WORDS =
  "px-0.5 text-[#FACC15] border-b-2 border-[rgba(250,204,21,0.45)] transition-[border-color] motion-reduce:transition-none [span:hover>&]:border-[#FACC15]";
const SELECT =
  "absolute inset-0 h-full w-full cursor-pointer appearance-none opacity-0 text-[16px]";
const DATE =
  "mx-0.5 bg-transparent px-0.5 text-[#FACC15] text-[16px] sm:text-[17px] font-semibold border-b-2 border-[rgba(250,204,21,0.45)] [color-scheme:dark] cursor-pointer outline-none rounded-[3px] focus-visible:outline-2 focus-visible:outline-offset-[3px] focus-visible:outline-[#FACC15]";

interface PartProps<V extends string> {
  label: string;
  value: V;
  options: { value: V; label: string }[];
  onChange: (value: V) => void;
}

function SentencePart<V extends string>({ label, value, options, onChange }: PartProps<V>) {
  const shown = options.find((o) => o.value === value)?.label ?? options[0].label;
  return (
    <span className={PART}>
      <span aria-hidden="true" className={WORDS}>
        {shown}
        <span className="text-[0.7em] opacity-80"> ▾</span>
      </span>
      <select
        aria-label={label}
        className={SELECT}
        value={value}
        onChange={(e) => onChange(e.target.value as V)}
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>
    </span>
  );
}

export function FilterBar({ filters, regions, shops, onApply, onClear }: FilterBarProps) {
  // Range is local only while a custom range is being typed; everything
  // else reads straight from the applied filters.
  const [range, setRange] = useState<DateRangePreset>(filters.range);
  const [from, setFrom] = useState(filters.date_from ?? "");
  const [to, setTo] = useState(filters.date_to ?? "");
  const [dateError, setDateError] = useState<string | null>(null);

  useEffect(() => {
    setRange(filters.range);
    setFrom(filters.range === "custom" ? (filters.date_from ?? "") : "");
    setTo(filters.range === "custom" ? (filters.date_to ?? "") : "");
  }, [filters.range, filters.date_from, filters.date_to]);

  const applied = (): [DateRangePreset, string | null, string | null] =>
    filters.range === "custom"
      ? [filters.range, filters.date_from, filters.date_to]
      : [filters.range, null, null];

  const showRegion = regions.length > 1;
  const showStore = shops.length > 1;
  const visibleShops =
    filters.region_id === null
      ? shops
      : shops.filter((s) => s.region_id === filters.region_id);

  const handleRegion = (val: string) => {
    onApply(val === "" ? null : Number(val), null, ...applied());
  };

  const handleStore = (val: string) => {
    onApply(filters.region_id, val === "" ? null : Number(val), ...applied());
  };

  const handleRange = (val: DateRangePreset) => {
    setRange(val);
    setFrom("");
    setTo("");
    setDateError(null);
    if (val !== "custom") onApply(filters.region_id, filters.shop_id, val, null, null);
  };

  const handleDate = (nextFrom: string, nextTo: string) => {
    setFrom(nextFrom);
    setTo(nextTo);
    if (!nextFrom || !nextTo) {
      setDateError(null);
      return;
    }
    const err = validateCustom(nextFrom, nextTo);
    setDateError(err);
    if (!err) onApply(filters.region_id, filters.shop_id, "custom", nextFrom, nextTo);
  };

  const handleReset = () => {
    setRange("all");
    setFrom("");
    setTo("");
    setDateError(null);
    onClear();
  };

  const showReset =
    !isDefault(filters) ||
    filters.date_from !== null ||
    filters.date_to !== null ||
    range !== "all";

  const regionPart = showRegion && (
    <SentencePart
      label="Filter by region"
      value={filters.region_id === null ? "" : String(filters.region_id)}
      options={[
        { value: "", label: "all regions" },
        ...regions.map((r) => ({ value: String(r.id), label: r.name })),
      ]}
      onChange={handleRegion}
    />
  );

  const storePart = showStore && (
    <SentencePart
      label="Filter by store"
      value={filters.shop_id === null ? "" : String(filters.shop_id)}
      options={[
        { value: "", label: "all stores" },
        ...visibleShops.map((s) => ({ value: String(s.id), label: s.name })),
      ]}
      onChange={handleStore}
    />
  );

  return (
    <div className="mb-[18px] rounded-[14px] bg-[#0A0A0A] px-4 py-4 sm:px-[22px] sm:py-[18px]">
      <div className="flex flex-wrap items-baseline gap-x-4 gap-y-2">
        <p
          data-testid="filter-sentence"
          className="min-w-0 flex-1 text-[18px] sm:text-[20px] font-semibold leading-[1.6] text-[#E4E4E7] [overflow-wrap:anywhere]"
        >
          Showing{" "}
          {regionPart}
          {regionPart && storePart && ", "}
          {storePart}
          {(regionPart || storePart) && " for "}
          <SentencePart
            label="Filter by date range"
            value={range}
            options={RANGE_OPTIONS}
            onChange={handleRange}
          />
          {range === "custom" && (
            <>
              {" "}from{" "}
              <input
                type="date"
                aria-label="From date"
                className={DATE}
                value={from}
                max={to || undefined}
                onChange={(e) => handleDate(e.target.value, to)}
              />
              {" "}to{" "}
              <input
                type="date"
                aria-label="To date"
                className={DATE}
                value={to}
                min={from || undefined}
                onChange={(e) => handleDate(from, e.target.value)}
              />
            </>
          )}
        </p>
        {showReset && (
          <button
            type="button"
            onClick={handleReset}
            className="text-[13px] text-[#A1A1AA] underline underline-offset-2 hover:text-white rounded-[3px] outline-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#FACC15]"
          >
            Reset
          </button>
        )}
      </div>
      {dateError && (
        <p role="alert" className="mt-2 text-[13px] text-[#F87171]">{dateError}</p>
      )}
    </div>
  );
}
