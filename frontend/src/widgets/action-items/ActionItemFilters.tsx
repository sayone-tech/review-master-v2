import { useState } from "react";
import { Calendar, Search, SlidersHorizontal, X } from "lucide-react";
import type {
  ActionItemScope,
  ActionItemStatus,
  ListParams,
  ShopOption,
  TeamMember,
  UserRole,
} from "./types";

const selectCls =
  "px-3 py-2 text-[13.5px] bg-white border border-line rounded-md focus:outline-none focus:ring focus:ring-black/[0.06] focus:border-ink";

interface DraftFilters {
  search: string;
  shop?: number;
  status?: ActionItemStatus;
  scope?: ActionItemScope;
  assignee?: string;
  from_date?: string;
  to_date?: string;
}

interface Props {
  userRole: UserRole;
  shops: ShopOption[];
  teamMembers: TeamMember[];
  filters: ListParams;
  onApply: (draft: DraftFilters) => void;
  onReset: () => void;
}

const STATUS_OPTIONS: { value: ActionItemStatus; label: string }[] = [
  { value: "TODO", label: "To Do" },
  { value: "IN_PROGRESS", label: "In Progress" },
  { value: "COMPLETE", label: "Complete" },
  { value: "WONT_DO", label: "Won't Do" },
];

const SCOPE_OPTIONS: { value: ActionItemScope; label: string }[] = [
  { value: "SHOP", label: "Shop" },
  { value: "BRAND", label: "Brand" },
];

export function ActionItemFilters({
  userRole,
  shops,
  teamMembers,
  filters,
  onApply,
  onReset,
}: Props) {
  const [draft, setDraft] = useState<DraftFilters>({
    search: filters.search ?? "",
    shop: filters.shop,
    status: filters.status as ActionItemStatus | undefined,
    scope: filters.scope as ActionItemScope | undefined,
    assignee: filters.assignee,
    from_date: filters.from_date,
    to_date: filters.to_date,
  });

  const hasActiveFilters = Boolean(
    filters.search ||
      filters.shop !== undefined ||
      filters.status ||
      filters.scope ||
      filters.assignee ||
      filters.from_date ||
      filters.to_date,
  );

  const handleReset = () => {
    setDraft({
      search: "",
      shop: undefined,
      status: undefined,
      scope: undefined,
      assignee: undefined,
      from_date: undefined,
      to_date: undefined,
    });
    onReset();
  };

  return (
    <div className="space-y-2">
      {/* Row 1 — search first, then select filters */}
      <div className="flex flex-wrap items-stretch gap-2">
        <div className="flex items-center gap-2 px-3 py-2 bg-white border border-line rounded-md flex-[2] min-w-[220px] focus-within:border-ink focus-within:ring focus-within:ring-black/[0.06]">
          <Search size={14} className="text-muted shrink-0" aria-hidden="true" />
          <input
            type="text"
            className="flex-1 min-w-0 bg-transparent focus:outline-none text-[13.5px]"
            placeholder="Search action items…"
            value={draft.search}
            onChange={(e) => setDraft((d) => ({ ...d, search: e.target.value }))}
            aria-label="Search action items"
          />
        </div>

        <select
          className={`${selectCls} flex-1 min-w-[140px]`}
          value={draft.shop ?? ""}
          onChange={(e) =>
            setDraft((d) => ({ ...d, shop: e.target.value ? Number(e.target.value) : undefined }))
          }
          aria-label="Filter by store"
        >
          <option value="">All Stores</option>
          {shops.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </select>

        <select
          className={`${selectCls} flex-1 min-w-[140px]`}
          value={draft.status ?? ""}
          onChange={(e) =>
            setDraft((d) => ({
              ...d,
              status: (e.target.value || undefined) as ActionItemStatus | undefined,
            }))
          }
          aria-label="Filter by status"
        >
          <option value="">Any Status</option>
          {STATUS_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>

        {userRole === "ORG_ADMIN" && (
          <select
            className={`${selectCls} flex-1 min-w-[130px]`}
            value={draft.scope ?? ""}
            onChange={(e) =>
              setDraft((d) => ({
                ...d,
                scope: (e.target.value || undefined) as ActionItemScope | undefined,
              }))
            }
            aria-label="Filter by scope"
          >
            <option value="">Any Scope</option>
            {SCOPE_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        )}
      </div>

      {/* Row 2 — assignee, date range, action buttons */}
      <div className="flex flex-wrap items-stretch gap-2">
        <select
          className={`${selectCls} flex-1 min-w-[160px]`}
          value={draft.assignee ?? ""}
          onChange={(e) =>
            setDraft((d) => ({ ...d, assignee: e.target.value || undefined }))
          }
          aria-label="Filter by assignee"
        >
          <option value="">All Assignees</option>
          <option value="me">Assigned to me</option>
          <option value="unassigned">Unassigned</option>
          {teamMembers.map((m) => (
            <option key={m.id} value={String(m.id)}>
              {m.full_name}
            </option>
          ))}
        </select>

        <div className="flex items-center gap-1 px-3 bg-white border border-line rounded-md text-[13.5px] flex-[2] min-w-[260px]">
          <Calendar size={13} className="text-muted shrink-0" aria-hidden="true" />
          <input
            type="date"
            className="flex-1 bg-transparent focus:outline-none text-[13px] min-w-0 py-2"
            value={draft.from_date ?? ""}
            onChange={(e) => setDraft((d) => ({ ...d, from_date: e.target.value || undefined }))}
            aria-label="From date"
          />
          <span className="text-muted px-0.5">–</span>
          <input
            type="date"
            className="flex-1 bg-transparent focus:outline-none text-[13px] min-w-0 py-2"
            value={draft.to_date ?? ""}
            onChange={(e) => setDraft((d) => ({ ...d, to_date: e.target.value || undefined }))}
            aria-label="To date"
          />
        </div>

        <button
          type="button"
          onClick={() => onApply(draft)}
          className="inline-flex items-center gap-1.5 px-4 py-2 bg-black text-yellow text-[13.5px] font-semibold rounded-md hover:bg-ink/90 shrink-0"
        >
          <SlidersHorizontal size={13} aria-hidden="true" />
          Filter
        </button>

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

    </div>
  );
}
