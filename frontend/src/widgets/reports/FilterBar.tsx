import { useEffect, useState } from "react";
import type { DateRangePreset, ReplyStatus, ReportFilters, SentimentFilter } from "./types";

interface Props {
  filters: ReportFilters;
  onApply: (f: ReportFilters) => void;
}

const selectCls =
  "appearance-none w-full px-3 py-[9px] pr-8 text-[13.5px] font-medium text-ink bg-white border border-line rounded-md outline-none cursor-pointer transition-[border-color] hover:border-[#D4D4D8] focus:border-ink focus:ring focus:ring-black/[0.06]";

function validateCustom(from: string, to: string): string | null {
  if (!from || !to) return "Select both start and end dates.";
  if (new Date(from) > new Date(to)) return "End date must be after start date.";
  const days = (new Date(to).getTime() - new Date(from).getTime()) / 86400000;
  if (days > 365) return "Range cannot exceed 365 days.";
  return null;
}

export function FilterBar({ filters, onApply }: Props) {
  const [draft, setDraft] = useState({ ...filters, from: filters.date_from ?? "", to: filters.date_to ?? "" });
  const [dateError, setDateError] = useState<string | null>(null);

  useEffect(() => {
    setDraft({ ...filters, from: filters.date_from ?? "", to: filters.date_to ?? "" });
  }, [filters]);

  function apply() {
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
    <div className="flex flex-wrap items-end gap-3 mb-6">
      <label className="flex flex-col gap-1 min-w-[140px]">
        <span className="text-[11.5px] font-medium text-subtle uppercase tracking-[0.05em]">Period</span>
        <select
          className={selectCls}
          value={draft.range}
          onChange={e => setDraft(d => ({ ...d, range: e.target.value as DateRangePreset }))}
        >
          <option value="all">All time</option>
          <option value="7d">Last 7 days</option>
          <option value="30d">Last 30 days</option>
          <option value="90d">Last 90 days</option>
          <option value="custom">Custom</option>
        </select>
      </label>

      {draft.range === "custom" && (
        <>
          <label className="flex flex-col gap-1">
            <span className="text-[11.5px] font-medium text-subtle uppercase tracking-[0.05em]">From</span>
            <input
              type="date"
              className={selectCls + " w-auto"}
              value={draft.from}
              onChange={e => setDraft(d => ({ ...d, from: e.target.value }))}
            />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-[11.5px] font-medium text-subtle uppercase tracking-[0.05em]">To</span>
            <input
              type="date"
              className={selectCls + " w-auto"}
              value={draft.to}
              onChange={e => setDraft(d => ({ ...d, to: e.target.value }))}
            />
          </label>
        </>
      )}

      <label className="flex flex-col gap-1 min-w-[140px]">
        <span className="text-[11.5px] font-medium text-subtle uppercase tracking-[0.05em]">Reply Status</span>
        <select
          className={selectCls}
          value={draft.reply_status}
          onChange={e => setDraft(d => ({ ...d, reply_status: e.target.value as ReplyStatus }))}
        >
          <option value="all">All</option>
          <option value="replied">Replied</option>
          <option value="not_replied">Not replied</option>
        </select>
      </label>

      <label className="flex flex-col gap-1 min-w-[140px]">
        <span className="text-[11.5px] font-medium text-subtle uppercase tracking-[0.05em]">Sentiment</span>
        <select
          className={selectCls}
          value={draft.sentiment}
          onChange={e => setDraft(d => ({ ...d, sentiment: e.target.value as SentimentFilter }))}
        >
          <option value="all">All</option>
          <option value="positive">Positive</option>
          <option value="neutral">Neutral</option>
          <option value="negative">Negative</option>
        </select>
      </label>

      <button
        onClick={apply}
        className="inline-flex items-center justify-center px-3.5 py-[9px] text-[13.5px] font-medium rounded-md bg-yellow text-black border border-yellow-hover hover:bg-yellow-hover transition-colors"
      >
        Apply
      </button>

      {dateError && (
        <p className="w-full text-[12px] text-red-600 mt-1">{dateError}</p>
      )}
    </div>
  );
}
