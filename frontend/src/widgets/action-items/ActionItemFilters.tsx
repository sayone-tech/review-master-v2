import { useState } from "react";
import { Calendar, RefreshCw, Search, Tag, Users } from "lucide-react";
import type {
  ActionItemCategory,
  ActionItemScope,
  ActionItemStatus,
  ListParams,
  ShopOption,
  TeamMember,
  UserRole,
} from "./types";

const selectCls =
  "appearance-none w-full px-3.5 py-[10px] pr-9 text-[14px] font-medium text-ink bg-white border border-line rounded-[10px] outline-none cursor-pointer transition-[border-color,box-shadow] hover:border-[#D4D4D8] focus:border-ink focus:shadow-[0_0_0_3px_rgba(10,10,10,0.05)]";

interface DraftFilters {
  search: string;
  shop?: number;
  status?: ActionItemStatus;
  scope?: ActionItemScope;
  category?: ActionItemCategory;
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

const CATEGORY_OPTIONS: { value: ActionItemCategory; label: string }[] = [
  { value: "QUALITY", label: "Quality" },
  { value: "SERVICE", label: "Service" },
  { value: "EXPERIENCE", label: "Experience" },
  { value: "OPERATIONS", label: "Operations" },
  { value: "OTHER", label: "Other" },
];

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

function StoreIcon({ size = 15 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.75}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M3 9l1-4h16l1 4" />
      <path d="M3 9v11h18V9" />
      <path d="M9 9v11" />
      <path d="M15 9v11" />
    </svg>
  );
}

function StatusIcon({ size = 15 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.75}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <circle cx="12" cy="12" r="10" />
      <polyline points="12 6 12 12 16 14" />
    </svg>
  );
}

export function ActionItemFilters({
  userRole,
  shops,
  teamMembers,
  filters,
  onApply,
  onReset,
}: Props) {
  const isOrgAdmin = userRole === "ORG_ADMIN";

  const [draft, setDraft] = useState<DraftFilters>({
    search: filters.search ?? "",
    shop: filters.shop,
    status: filters.status as ActionItemStatus | undefined,
    scope: filters.scope as ActionItemScope | undefined,
    category: filters.category as ActionItemCategory | undefined,
    assignee: filters.assignee,
    from_date: filters.from_date,
    to_date: filters.to_date,
  });

  const hasActiveFilters = Boolean(
    filters.search ||
      filters.shop !== undefined ||
      filters.status ||
      filters.scope ||
      filters.category ||
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
      category: undefined,
      assignee: undefined,
      from_date: undefined,
      to_date: undefined,
    });
    onReset();
  };

  // Row 1 columns: Search | Store | Status | [Scope — OrgAdmin only] | Category
  const row1Cols = isOrgAdmin
    ? "minmax(0,1.6fr) minmax(0,1fr) minmax(0,1fr) minmax(0,1fr) minmax(0,1fr)"
    : "minmax(0,1.6fr) minmax(0,1fr) minmax(0,1fr) minmax(0,1fr)";

  return (
    <div className="bg-white border border-line rounded-xl p-3.5 mb-[18px]">
      {/* Row 1 — search + store + status + [scope] + actions */}
      <div style={{ display: "grid", gridTemplateColumns: row1Cols, gap: 14, alignItems: "end" }}>
        {/* Search */}
        <label className="flex flex-col gap-1.5 min-w-0">
          <FilterLabel icon={<Search size={15} />} label="Search" />
          <div className="flex items-center gap-2 px-3.5 py-[10px] bg-white border border-line rounded-[10px] transition-[border-color,box-shadow] hover:border-[#D4D4D8] focus-within:border-ink focus-within:shadow-[0_0_0_3px_rgba(10,10,10,0.05)]">
            <Search size={14} className="text-muted shrink-0" aria-hidden="true" />
            <input
              type="text"
              className="flex-1 min-w-0 bg-transparent focus:outline-none text-[14px] font-medium text-ink placeholder:text-faint placeholder:font-normal"
              placeholder="Search action items…"
              value={draft.search}
              onChange={(e) => setDraft((d) => ({ ...d, search: e.target.value }))}
              aria-label="Search action items"
            />
          </div>
        </label>

        {/* Store */}
        <label className="flex flex-col gap-1.5 min-w-0">
          <FilterLabel icon={<StoreIcon size={15} />} label="Store" />
          <div className="relative">
            <select
              aria-label="Filter by store"
              className={selectCls}
              value={draft.shop ?? ""}
              onChange={(e) =>
                setDraft((d) => ({
                  ...d,
                  shop: e.target.value ? Number(e.target.value) : undefined,
                }))
              }
            >
              <option value="">All stores</option>
              {shops.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
            <ChevronIcon />
          </div>
        </label>

        {/* Status */}
        <label className="flex flex-col gap-1.5 min-w-0">
          <FilterLabel icon={<StatusIcon size={15} />} label="Status" />
          <div className="relative">
            <select
              aria-label="Filter by status"
              className={selectCls}
              value={draft.status ?? ""}
              onChange={(e) =>
                setDraft((d) => ({
                  ...d,
                  status: (e.target.value || undefined) as ActionItemStatus | undefined,
                }))
              }
            >
              <option value="">Any status</option>
              {STATUS_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
            <ChevronIcon />
          </div>
        </label>

        {/* Scope — org admin only */}
        {isOrgAdmin && (
          <label className="flex flex-col gap-1.5 min-w-0">
            <FilterLabel icon={<Tag size={15} />} label="Scope" />
            <div className="relative">
              <select
                aria-label="Filter by scope"
                className={selectCls}
                value={draft.scope ?? ""}
                onChange={(e) =>
                  setDraft((d) => ({
                    ...d,
                    scope: (e.target.value || undefined) as ActionItemScope | undefined,
                  }))
                }
              >
                <option value="">Any scope</option>
                {SCOPE_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
              <ChevronIcon />
            </div>
          </label>
        )}

        {/* Category */}
        <label className="flex flex-col gap-1.5 min-w-0">
          <FilterLabel icon={<Tag size={15} />} label="Category" />
          <div className="relative">
            <select
              aria-label="Filter by category"
              className={selectCls}
              value={draft.category ?? ""}
              onChange={(e) =>
                setDraft((d) => ({
                  ...d,
                  category: (e.target.value || undefined) as ActionItemCategory | undefined,
                }))
              }
            >
              <option value="">Any category</option>
              {CATEGORY_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
            <ChevronIcon />
          </div>
        </label>
      </div>

      {/* Row 2 — date range + assignee + actions */}
      <div
        className="mt-3 pt-3 border-t border-dashed border-line"
        style={{
          display: "grid",
          gridTemplateColumns: "minmax(0,1.6fr) minmax(0,1fr) auto",
          gap: 14,
          alignItems: "end",
        }}
      >
        {/* Date range */}
        <label className="flex flex-col gap-1.5 min-w-0">
          <FilterLabel icon={<Calendar size={15} />} label="Date range" />
          <div className="flex items-center gap-2 px-3.5 py-[10px] border border-line rounded-[10px] bg-white focus-within:border-ink focus-within:shadow-[0_0_0_3px_rgba(10,10,10,0.05)] transition-[border-color,box-shadow]">
            <Calendar size={14} className="text-subtle shrink-0" aria-hidden="true" />
            <input
              type="date"
              aria-label="From date"
              className="flex-1 bg-transparent focus:outline-none text-[14px] text-ink min-w-0"
              value={draft.from_date ?? ""}
              max={draft.to_date ?? undefined}
              onChange={(e) =>
                setDraft((d) => ({ ...d, from_date: e.target.value || undefined }))
              }
            />
            <span className="text-faint font-medium shrink-0">—</span>
            <input
              type="date"
              aria-label="To date"
              className="flex-1 bg-transparent focus:outline-none text-[14px] text-ink min-w-0"
              value={draft.to_date ?? ""}
              min={draft.from_date ?? undefined}
              onChange={(e) =>
                setDraft((d) => ({ ...d, to_date: e.target.value || undefined }))
              }
            />
          </div>
        </label>

        {/* Assignee */}
        <label className="flex flex-col gap-1.5 min-w-0">
          <FilterLabel icon={<Users size={15} />} label="Assignee" />
          <div className="relative">
            <select
              aria-label="Filter by assignee"
              className={selectCls}
              value={draft.assignee ?? ""}
              onChange={(e) =>
                setDraft((d) => ({ ...d, assignee: e.target.value || undefined }))
              }
            >
              <option value="">All assignees</option>
              <option value="me">Assigned to me</option>
              <option value="unassigned">Unassigned</option>
              {teamMembers.map((m) => (
                <option key={m.id} value={String(m.id)}>
                  {m.full_name}
                </option>
              ))}
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
            onClick={() => onApply(draft)}
            className="inline-flex items-center gap-1.5 px-3.5 py-[10px] rounded-[10px] bg-yellow text-black border border-yellow-hover text-[14px] font-medium hover:bg-yellow-hover transition-colors shrink-0"
          >
            Apply
          </button>
        </div>
      </div>
    </div>
  );
}
