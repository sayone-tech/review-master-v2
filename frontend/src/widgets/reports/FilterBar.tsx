import { useEffect, useState } from "react";
import { Calendar, MessageSquare, RefreshCw, ThumbsUp, Timer } from "lucide-react";
import type { DateRangePreset, ReplyStatus, ReportFilters, SentimentFilter } from "./types";

interface Draft {
  range: DateRangePreset;
  reply_status: ReplyStatus;
  sentiment: SentimentFilter;
  from: string;
  to: string;
}

interface Props {
  filters: ReportFilters;
  onApply: (f: ReportFilters) => void;
}

const selectCls =
  "appearance-none w-full px-3.5 py-[10px] pr-9 text-[14px] font-medium text-ink bg-white border border-line rounded-[10px] outline-none cursor-pointer transition-[border-color,box-shadow] hover:border-[#D4D4D8] focus:border-ink focus:shadow-[0_0_0_3px_rgba(10,10,10,0.05)]";

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

function FilterLabel({ icon, label }: { icon: React.ReactNode; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-[11.5px] font-medium text-subtle uppercase tracking-[0.05em]">
      <span className="text-muted">{icon}</span>
      <span>{label}</span>
    </span>
  );
}

function validateCustom(from: string, to: string): string | null {
  if (!from || !to) return "Select both start and end dates.";
  if (new Date(from) > new Date(to)) return "End date must be after start date.";
  const days = (new Date(to).getTime() - new Date(from).getTime()) / 86400000;
  if (days > 365) return "Range cannot exceed 365 days.";
  return null;
}

export function FilterBar({ filters, onApply }: Props) {
  const [draft, setDraft] = useState<Draft>({
    range: filters.range,
    reply_status: filters.reply_status,
    sentiment: filters.sentiment,
    from: filters.date_from ?? "",
    to: filters.date_to ?? "",
  });
  const [dateError, setDateError] = useState<string | null>(null);

  useEffect(() => {
    setDraft({
      range: filters.range,
      reply_status: filters.reply_status,
      sentiment: filters.sentiment,
      from: filters.date_from ?? "",
      to: filters.date_to ?? "",
    });
  }, [filters]);

  const hasActiveFilters =
    filters.range !== "30d" ||
    filters.reply_status !== "all" ||
    filters.sentiment !== "all";

  function handleReset() {
    const defaults: ReportFilters = {
      range: "30d",
      date_from: null,
      date_to: null,
      reply_status: "all",
      sentiment: "all",
    };
    setDraft({ range: "30d", reply_status: "all", sentiment: "all", from: "", to: "" });
    setDateError(null);
    onApply(defaults);
  }

  function handleApply() {
    if (draft.range === "custom") {
      const err = validateCustom(draft.from, draft.to);
      if (err) { setDateError(err); return; }
    }
    setDateError(null);
    onApply({
      range: draft.range,
      date_from: draft.range === "custom" ? draft.from : null,
      date_to: draft.range === "custom" ? draft.to : null,
      reply_status: draft.reply_status,
      sentiment: draft.sentiment,
    });
  }

  return (
    <div className="bg-white border border-line rounded-xl p-3.5 mb-[18px]">
      {/* Row 1 — period + reply + sentiment + actions */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "minmax(0,1.2fr) minmax(0,1fr) minmax(0,1fr) auto",
          gap: 14,
          alignItems: "end",
        }}
      >
        {/* Period */}
        <label className="flex flex-col gap-1.5 min-w-0">
          <FilterLabel icon={<Timer size={15} />} label="Period" />
          <div className="relative">
            <select
              aria-label="Filter by period"
              className={selectCls}
              value={draft.range}
              onChange={(e) =>
                setDraft((d) => ({ ...d, range: e.target.value as DateRangePreset }))
              }
            >
              <option value="all">All time</option>
              <option value="7d">Last 7 days</option>
              <option value="30d">Last 30 days</option>
              <option value="90d">Last 90 days</option>
              <option value="custom">Custom range</option>
            </select>
            <ChevronIcon />
          </div>
        </label>

        {/* Reply status */}
        <label className="flex flex-col gap-1.5 min-w-0">
          <FilterLabel icon={<MessageSquare size={15} />} label="Reply" />
          <div className="relative">
            <select
              aria-label="Filter by reply status"
              className={selectCls}
              value={draft.reply_status}
              onChange={(e) =>
                setDraft((d) => ({ ...d, reply_status: e.target.value as ReplyStatus }))
              }
            >
              <option value="all">All replies</option>
              <option value="replied">Replied</option>
              <option value="not_replied">Not replied</option>
            </select>
            <ChevronIcon />
          </div>
        </label>

        {/* Sentiment */}
        <label className="flex flex-col gap-1.5 min-w-0">
          <FilterLabel icon={<ThumbsUp size={15} />} label="Sentiment" />
          <div className="relative">
            <select
              aria-label="Filter by sentiment"
              className={selectCls}
              value={draft.sentiment}
              onChange={(e) =>
                setDraft((d) => ({ ...d, sentiment: e.target.value as SentimentFilter }))
              }
            >
              <option value="all">Any sentiment</option>
              <option value="positive">Positive</option>
              <option value="neutral">Neutral</option>
              <option value="negative">Negative</option>
            </select>
            <ChevronIcon />
          </div>
        </label>

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

      {/* Row 2 — custom date range (only when custom is selected) */}
      {draft.range === "custom" && (
        <div className="mt-3 pt-3 border-t border-dashed border-line">
          <label className="flex flex-col gap-1.5" style={{ maxWidth: 420 }}>
            <FilterLabel icon={<Calendar size={15} />} label="Date range" />
            <div className="flex items-center gap-2 px-3.5 py-[10px] border border-line rounded-[10px] bg-white focus-within:border-ink focus-within:shadow-[0_0_0_3px_rgba(10,10,10,0.05)] transition-[border-color,box-shadow]">
              <Calendar size={14} className="text-subtle shrink-0" aria-hidden="true" />
              <input
                type="date"
                aria-label="From date"
                className="flex-1 bg-transparent focus:outline-none text-[14px] text-ink min-w-0"
                value={draft.from}
                max={draft.to || undefined}
                onChange={(e) => setDraft((d) => ({ ...d, from: e.target.value }))}
              />
              <span className="text-faint font-medium shrink-0">—</span>
              <input
                type="date"
                aria-label="To date"
                className="flex-1 bg-transparent focus:outline-none text-[14px] text-ink min-w-0"
                value={draft.to}
                min={draft.from || undefined}
                onChange={(e) => setDraft((d) => ({ ...d, to: e.target.value }))}
              />
            </div>
          </label>
          {dateError && (
            <p className="mt-1.5 text-[12px] text-red-600">{dateError}</p>
          )}
        </div>
      )}
    </div>
  );
}
