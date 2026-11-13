import { useState } from "react";
import { ArrowDown, ArrowUp, MessageSquare, RefreshCw, ThumbsUp, Timer } from "lucide-react";
import { FilterSelect } from "../filters";
import type {
  DateRangePreset,
  ReplyStatus,
  ReportFilters,
  SentimentFilter,
  SortDir,
  SortKey,
} from "./types";

interface Props {
  filters: ReportFilters;
  onChange: (next: ReportFilters) => void;
  sortKey: SortKey;
  sortDir: SortDir;
  onSort: (key: SortKey) => void;
}

const SORT_OPTIONS: [SortKey, string][] = [
  ["total_reviews", "Reviews"],
  ["avg_rating", "Avg Rating"],
  ["replied_count", "Replied"],
  ["not_replied_count", "Not Replied"],
  ["positive_count", "Positive"],
  ["negative_count", "Negative"],
];

const DEFAULTS: ReportFilters = {
  range: "30d",
  date_from: null,
  date_to: null,
  reply_status: "all",
  sentiment: "all",
};

function validateCustom(from: string, to: string): string | null {
  if (!from || !to) return "Select both start and end dates.";
  if (new Date(from) > new Date(to)) return "End date must be after start date.";
  const days = (new Date(to).getTime() - new Date(from).getTime()) / 86400000;
  if (days > 365) return "Range cannot exceed 365 days.";
  return null;
}

const dateInputCls =
  "h-[34px] px-2 text-[13px] text-ink bg-white border border-line rounded-[8px] outline-none focus:border-ink";

export function FilterBar({ filters, onChange, sortKey, sortDir, onSort }: Props) {
  const [customOpen, setCustomOpen] = useState(filters.range === "custom");
  const [from, setFrom] = useState(filters.date_from ?? "");
  const [to, setTo] = useState(filters.date_to ?? "");
  const [dateError, setDateError] = useState<string | null>(null);

  const hasActiveFilters =
    filters.range !== DEFAULTS.range ||
    filters.reply_status !== DEFAULTS.reply_status ||
    filters.sentiment !== DEFAULTS.sentiment;

  function handleRange(v: DateRangePreset | undefined) {
    const range = v ?? "all";
    // Locally kept dates never outlive the choice: nothing applies until both are valid.
    setFrom("");
    setTo("");
    setDateError(null);
    if (range === "custom") {
      setCustomOpen(true);
      return;
    }
    setCustomOpen(false);
    onChange({ ...filters, range, date_from: null, date_to: null });
  }

  function handleDates(nextFrom: string, nextTo: string) {
    setFrom(nextFrom);
    setTo(nextTo);
    if (!nextFrom || !nextTo) {
      setDateError(null);
      return;
    }
    const err = validateCustom(nextFrom, nextTo);
    setDateError(err);
    if (err) return;
    onChange({ ...filters, range: "custom", date_from: nextFrom, date_to: nextTo });
  }

  function handleReset() {
    setCustomOpen(false);
    setFrom("");
    setTo("");
    setDateError(null);
    onChange(DEFAULTS);
  }

  return (
    <div className="mb-[18px]">
      <div className="flex flex-wrap items-center gap-2">
        <FilterSelect<DateRangePreset>
          icon={Timer}
          ariaLabel="Filter by period"
          placeholder="All time"
          value={customOpen ? "custom" : filters.range === "all" ? undefined : filters.range}
          options={[
            { value: "7d", label: "Last 7 days" },
            { value: "30d", label: "Last 30 days" },
            { value: "90d", label: "Last 90 days" },
            { value: "custom", label: "Custom range" },
          ]}
          onChange={handleRange}
        />
        {customOpen && (
          <div className="flex items-center gap-1.5">
            <input
              type="date"
              aria-label="From date"
              className={dateInputCls}
              value={from}
              max={to || undefined}
              onChange={(e) => handleDates(e.target.value, to)}
            />
            <span className="text-faint">—</span>
            <input
              type="date"
              aria-label="To date"
              className={dateInputCls}
              value={to}
              min={from || undefined}
              onChange={(e) => handleDates(from, e.target.value)}
            />
          </div>
        )}
        <FilterSelect<ReplyStatus>
          icon={MessageSquare}
          ariaLabel="Filter by reply status"
          placeholder="All replies"
          value={filters.reply_status === "all" ? undefined : filters.reply_status}
          options={[
            { value: "replied", label: "Replied" },
            { value: "not_replied", label: "Not replied" },
          ]}
          onChange={(v) => onChange({ ...filters, reply_status: v ?? "all" })}
        />
        <FilterSelect<SentimentFilter>
          icon={ThumbsUp}
          ariaLabel="Filter by sentiment"
          placeholder="Any sentiment"
          value={filters.sentiment === "all" ? undefined : filters.sentiment}
          options={[
            { value: "positive", label: "Positive" },
            { value: "neutral", label: "Neutral" },
            { value: "negative", label: "Negative" },
          ]}
          onChange={(v) => onChange({ ...filters, sentiment: v ?? "all" })}
        />
        {hasActiveFilters && (
          <button
            type="button"
            onClick={handleReset}
            className="inline-flex items-center gap-1.5 text-[13px] text-subtle hover:text-ink transition-colors"
          >
            <RefreshCw size={13} aria-hidden="true" />
            Reset
          </button>
        )}

        <div className="ml-auto flex items-center gap-3 text-[12px] text-muted">
          <span>Sort by:</span>
          {SORT_OPTIONS.map(([key, label]) => (
            <button
              key={key}
              type="button"
              onClick={() => onSort(key)}
              className={`inline-flex items-center gap-0.5 transition-colors ${
                sortKey === key ? "text-ink font-semibold" : "hover:text-ink"
              }`}
            >
              {label}
              {sortKey === key &&
                (sortDir === "desc" ? (
                  <ArrowDown size={10} aria-hidden="true" />
                ) : (
                  <ArrowUp size={10} aria-hidden="true" />
                ))}
            </button>
          ))}
        </div>
      </div>
      {customOpen && dateError && <p className="mt-1.5 text-[12px] text-red-600">{dateError}</p>}
    </div>
  );
}
