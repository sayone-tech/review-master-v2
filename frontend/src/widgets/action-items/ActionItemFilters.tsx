import { CircleDot, Store, Users } from "lucide-react";
import {
  FilterChips,
  FilterSearch,
  FilterSelect,
  MoreFiltersPanel,
  formatDateChip,
  type FilterChip,
} from "../filters";
import type {
  ActionItemCategory,
  ActionItemScope,
  ActionItemStatus,
  ListParams,
  ShopOption,
  TeamMember,
  UserRole,
} from "./types";

interface PanelDraft {
  scope?: ActionItemScope;
  category?: ActionItemCategory;
  from_date?: string;
  to_date?: string;
}

interface Props {
  userRole: UserRole;
  shops: ShopOption[];
  teamMembers: TeamMember[];
  filters: ListParams;
  searchInput: string;
  onSearchChange: (value: string) => void;
  onChange: (next: Partial<ListParams>) => void;
  onClearAll: () => void;
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

const fieldCls =
  "w-full h-[34px] px-2 text-[13px] text-text bg-white border border-line rounded-[8px] outline-none focus:border-ink";
const labelCls = "flex flex-col gap-1 text-[12px] text-muted";

export function ActionItemFilters({
  userRole,
  shops,
  teamMembers,
  filters,
  searchInput,
  onSearchChange,
  onChange: onChangeProp,
  onClearAll,
}: Props) {
  // A typed-but-not-yet-applied search is folded into any other change so it is ONE request;
  // the hook's later debounce then finds search already applied and does nothing.
  const onChange = (patch: Partial<ListParams>) => {
    const pending = searchInput !== (filters.search ?? "");
    onChangeProp(pending && !("search" in patch) ? { ...patch, search: searchInput || undefined } : patch);
  };
  const isOrgAdmin = userRole === "ORG_ADMIN";
  const hasDate = Boolean(filters.from_date || filters.to_date);
  const scopeActive = isOrgAdmin && Boolean(filters.scope);
  const activeCount = (scopeActive ? 1 : 0) + (filters.category ? 1 : 0) + (hasDate ? 1 : 0);

  const chips: FilterChip[] = [];
  if (scopeActive) {
    const label = SCOPE_OPTIONS.find((o) => o.value === filters.scope)?.label;
    chips.push({
      key: "scope",
      label: `Scope: ${label}`,
      onRemove: () => onChange({ scope: undefined }),
    });
  }
  if (filters.category) {
    const label = CATEGORY_OPTIONS.find((o) => o.value === filters.category)?.label;
    chips.push({
      key: "category",
      label: `Category: ${label}`,
      onRemove: () => onChange({ category: undefined }),
    });
  }
  const dateLabel = formatDateChip(filters.from_date, filters.to_date);
  if (dateLabel) {
    chips.push({
      key: "date",
      label: dateLabel,
      onRemove: () => onChange({ from_date: undefined, to_date: undefined }),
    });
  }

  const applied: PanelDraft = {
    scope: isOrgAdmin ? filters.scope : undefined,
    category: filters.category,
    from_date: filters.from_date,
    to_date: filters.to_date,
  };

  return (
    <div className="mb-[14px]">
      <div className="flex flex-wrap items-center gap-2">
        <FilterSearch
          value={searchInput}
          placeholder="Search action items…"
          ariaLabel="Search action items"
          onChange={(v) => {
            onSearchChange(v);
            if (v === "") onChange({ search: undefined });
          }}
          onSubmit={() => onChange({ search: searchInput || undefined })}
        />
        <FilterSelect<number>
          icon={Store}
          ariaLabel="Filter by store"
          placeholder="All stores"
          value={filters.shop}
          options={shops.map((s) => ({ value: s.id, label: s.name }))}
          onChange={(v) => onChange({ shop: v })}
        />
        <FilterSelect<ActionItemStatus>
          icon={CircleDot}
          ariaLabel="Filter by status"
          placeholder="Any status"
          value={filters.status}
          options={STATUS_OPTIONS}
          onChange={(v) => onChange({ status: v })}
        />
        <FilterSelect<string>
          icon={Users}
          ariaLabel="Filter by assignee"
          placeholder="All assignees"
          value={filters.assignee}
          options={[
            { value: "me", label: "Assigned to me" },
            { value: "unassigned", label: "Unassigned" },
            ...teamMembers.map((m) => ({ value: String(m.id), label: m.full_name })),
          ]}
          onChange={(v) => onChange({ assignee: v })}
        />
        <MoreFiltersPanel<PanelDraft>
          applied={applied}
          activeCount={activeCount}
          onApply={(d) =>
            onChange({
              scope: isOrgAdmin ? d.scope : undefined,
              category: d.category,
              from_date: d.from_date,
              to_date: d.to_date,
            })
          }
          onReset={() =>
            onChange({
              scope: undefined,
              category: undefined,
              from_date: undefined,
              to_date: undefined,
            })
          }
        >
          {(draft, setDraft) => (
            <>
              {isOrgAdmin && (
                <label className={labelCls}>
                  Scope
                  <select
                    aria-label="Filter by scope"
                    className={fieldCls}
                    value={draft.scope ?? ""}
                    onChange={(e) =>
                      setDraft({ ...draft, scope: (e.target.value || undefined) as ActionItemScope | undefined })
                    }
                  >
                    <option value="">Any scope</option>
                    {SCOPE_OPTIONS.map((o) => (
                      <option key={o.value} value={o.value}>
                        {o.label}
                      </option>
                    ))}
                  </select>
                </label>
              )}
              <label className={labelCls}>
                Category
                <select
                  aria-label="Filter by category"
                  className={fieldCls}
                  value={draft.category ?? ""}
                  onChange={(e) =>
                    setDraft({
                      ...draft,
                      category: (e.target.value || undefined) as ActionItemCategory | undefined,
                    })
                  }
                >
                  <option value="">Any category</option>
                  {CATEGORY_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </label>
              <div className={labelCls}>
                Date range
                <div className="flex items-center gap-2">
                  <input
                    type="date"
                    aria-label="From date"
                    className={fieldCls}
                    value={draft.from_date ?? ""}
                    max={draft.to_date ?? undefined}
                    onChange={(e) => setDraft({ ...draft, from_date: e.target.value || undefined })}
                  />
                  <span className="text-faint">–</span>
                  <input
                    type="date"
                    aria-label="To date"
                    className={fieldCls}
                    value={draft.to_date ?? ""}
                    min={draft.from_date ?? undefined}
                    onChange={(e) => setDraft({ ...draft, to_date: e.target.value || undefined })}
                  />
                </div>
              </div>
            </>
          )}
        </MoreFiltersPanel>
      </div>
      <FilterChips chips={chips} onClearAll={onClearAll} />
    </div>
  );
}
