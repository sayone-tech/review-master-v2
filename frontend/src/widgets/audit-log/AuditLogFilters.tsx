// Phase 21-04 — Audit log filter bar.
// Type, Date Range (with 7d/30d/90d/Custom presets), Actor + Apply/Reset.

import { useEffect, useMemo, useState } from "react";
import { Calendar, Tag, Users } from "lucide-react";
import type { ActorOption, FilterParams } from "./types";
import { isoDate } from "./utils";

const selectCls =
  "appearance-none w-full px-3.5 py-[10px] pr-9 text-[14px] font-normal text-ink bg-white border border-line rounded-[10px] outline-none cursor-pointer transition-[border-color,box-shadow] hover:border-[#D4D4D8] focus:border-ink focus:shadow-[0_0_0_3px_rgba(10,10,10,0.05)]";

const dateInputCls =
  "px-2 py-1 text-[14px] text-ink bg-white border-0 outline-none focus:ring-0 [&::-webkit-calendar-picker-indicator]:opacity-60";

type Preset = "7d" | "30d" | "90d" | "Custom";

interface Props {
  filters: FilterParams;
  actors: ActorOption[];
  onApply: (next: FilterParams) => void;
  onReset: () => void;
  hasActiveFilters: boolean;
}

function presetRange(preset: Exclude<Preset, "Custom">): { date_from: string; date_to: string } {
  const days = preset === "7d" ? 7 : preset === "30d" ? 30 : 90;
  const today = new Date();
  const from = new Date(Date.now() - days * 24 * 60 * 60 * 1000);
  return { date_from: isoDate(from), date_to: isoDate(today) };
}

function matchesPreset(filters: FilterParams, preset: Exclude<Preset, "Custom">): boolean {
  const r = presetRange(preset);
  return filters.date_from === r.date_from && filters.date_to === r.date_to;
}

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
    <span className="inline-flex items-center gap-1.5 text-[12px] font-semibold text-subtle uppercase tracking-[0.05em]">
      <span className="text-muted">{icon}</span>
      <span>{label}</span>
    </span>
  );
}

function detectPreset(filters: FilterParams): Preset {
  if (matchesPreset(filters, "7d")) return "7d";
  if (matchesPreset(filters, "30d")) return "30d";
  if (matchesPreset(filters, "90d")) return "90d";
  return "Custom";
}

export function AuditLogFilters({ filters, actors, onApply, onReset, hasActiveFilters }: Props) {
  const [draft, setDraft] = useState<FilterParams>(filters);
  const [preset, setPreset] = useState<Preset>(() => detectPreset(filters));

  // When parent filters change (e.g. reset, URL nav), resync the draft.
  useEffect(() => {
    setDraft(filters);
    setPreset(detectPreset(filters));
  }, [filters]);

  const sortedActors = useMemo(
    () => [...actors].sort((a, b) => a.full_name.localeCompare(b.full_name)),
    [actors],
  );

  const presetButtonCls = (p: Preset) => {
    const active = preset === p;
    return active
      ? "px-2 py-1 text-[12px] font-semibold bg-black text-white rounded-sm"
      : "px-2 py-1 text-[12px] font-semibold bg-white text-muted border border-line rounded-sm hover:text-ink";
  };

  function selectPreset(p: Preset) {
    setPreset(p);
    if (p === "Custom") {
      // leave date inputs as-is for manual editing; user must Apply
      return;
    }
    const range = presetRange(p);
    const next: FilterParams = { ...draft, ...range };
    setDraft(next);
    onApply(next);
  }

  function handleApply() {
    onApply(draft);
  }

  return (
    <div
      className="bg-white border border-line rounded-xl p-4 mb-4"
      data-testid="audit-log-filters"
    >
      <div
        className="grid gap-4 items-end"
        style={{
          gridTemplateColumns: "minmax(0,1fr) minmax(0,1.4fr) minmax(0,1fr) auto",
        }}
      >
        {/* Type */}
        <div className="flex flex-col gap-1.5">
          <FilterLabel icon={<Tag size={15} />} label="Type" />
          <div className="relative">
            <select
              aria-label="Type"
              className={selectCls}
              value={draft.entity_type ?? ""}
              onChange={(e) =>
                setDraft((d) => ({ ...d, entity_type: e.target.value || undefined }))
              }
            >
              <option value="">All types</option>
              <option value="review">Replies</option>
              <option value="action_item">Action Items</option>
            </select>
            <ChevronIcon />
          </div>
        </div>

        {/* Date Range */}
        <div className="flex flex-col gap-1.5">
          <FilterLabel icon={<Calendar size={15} />} label="Date Range" />
          <div className="flex flex-col gap-1.5">
            <div className="flex items-center gap-1">
              {(["7d", "30d", "90d", "Custom"] as Preset[]).map((p) => (
                <button
                  key={p}
                  type="button"
                  className={presetButtonCls(p)}
                  onClick={() => selectPreset(p)}
                  aria-pressed={preset === p}
                >
                  {p}
                </button>
              ))}
            </div>
            <div className="flex items-center gap-2 px-3 py-1 bg-white border border-line rounded-[10px]">
              <Calendar size={15} className="text-muted" aria-hidden="true" />
              <input
                type="date"
                aria-label="Date from"
                className={dateInputCls}
                value={draft.date_from ?? ""}
                onChange={(e) => {
                  setDraft((d) => ({ ...d, date_from: e.target.value || undefined }));
                  setPreset("Custom");
                }}
              />
              <span className="text-muted">—</span>
              <input
                type="date"
                aria-label="Date to"
                className={dateInputCls}
                value={draft.date_to ?? ""}
                onChange={(e) => {
                  setDraft((d) => ({ ...d, date_to: e.target.value || undefined }));
                  setPreset("Custom");
                }}
              />
            </div>
          </div>
        </div>

        {/* Actor */}
        <div className="flex flex-col gap-1.5">
          <FilterLabel icon={<Users size={15} />} label="Actor" />
          <div className="relative">
            <select
              aria-label="Actor"
              className={selectCls}
              value={draft.actor ?? ""}
              onChange={(e) => setDraft((d) => ({ ...d, actor: e.target.value || undefined }))}
            >
              <option value="">All actors</option>
              <option value="system">System</option>
              {sortedActors.map((a) => (
                <option key={a.id} value={String(a.id)}>
                  {a.full_name}
                </option>
              ))}
            </select>
            <ChevronIcon />
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-2">
          <button
            type="button"
            className="bg-yellow text-black border border-yellow-hover text-[14px] font-semibold px-4 py-2 rounded-[10px] hover:bg-yellow-hover"
            onClick={handleApply}
          >
            Apply
          </button>
          {hasActiveFilters && (
            <button
              type="button"
              className="text-[14px] text-muted border border-dashed border-line px-4 py-2 rounded-[10px] hover:text-ink hover:border-ink"
              onClick={onReset}
            >
              Reset
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
