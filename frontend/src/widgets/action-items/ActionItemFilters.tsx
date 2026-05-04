import { Search } from "lucide-react";
import type {
  ActionItemScope,
  ActionItemStatus,
  ListParams,
  ShopOption,
  TeamMember,
  UserRole,
} from "./types";

interface Props {
  params: ListParams;
  onChange: (next: ListParams) => void;
  searchInput: string;
  onSearchChange: (value: string) => void;
  userRole: UserRole;
  shops: ShopOption[];
  teamMembers: TeamMember[];
  total: number;
  filtered: number;
  onClearFilters: () => void;
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

const SELECT_CLS =
  "px-3 py-2 text-[14px] bg-white border border-line rounded-md text-ink";

export function ActionItemFilters({
  params,
  onChange,
  searchInput,
  onSearchChange,
  userRole,
  shops,
  teamMembers,
  total,
  filtered,
  onClearFilters,
}: Props) {
  const hasAnyFilter = Boolean(
    params.shop !== undefined ||
      params.status ||
      params.scope ||
      params.assignee ||
      params.from_date ||
      params.to_date ||
      params.search ||
      params.review !== undefined,
  );

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-2 items-center">
        <select
          className={SELECT_CLS}
          style={{ width: "160px" }}
          value={params.shop ?? ""}
          onChange={(e) =>
            onChange({
              ...params,
              shop: e.target.value ? Number(e.target.value) : undefined,
              page: 1,
            })
          }
          aria-label="Filter by store"
        >
          <option value="">All stores</option>
          {shops.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </select>

        <select
          className={SELECT_CLS}
          style={{ width: "150px" }}
          value={params.status ?? ""}
          onChange={(e) =>
            onChange({
              ...params,
              status: (e.target.value || undefined) as ActionItemStatus | undefined,
              page: 1,
            })
          }
          aria-label="Filter by status"
        >
          <option value="">All statuses</option>
          {STATUS_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>

        {userRole === "ORG_ADMIN" && (
          <select
            className={SELECT_CLS}
            style={{ width: "130px" }}
            value={params.scope ?? ""}
            onChange={(e) =>
              onChange({
                ...params,
                scope: (e.target.value || undefined) as ActionItemScope | undefined,
                page: 1,
              })
            }
            aria-label="Filter by scope"
          >
            <option value="">All scopes</option>
            {SCOPE_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        )}

        <select
          className={SELECT_CLS}
          style={{ width: "160px" }}
          value={params.assignee ?? ""}
          onChange={(e) =>
            onChange({
              ...params,
              assignee: e.target.value || undefined,
              page: 1,
            })
          }
          aria-label="Filter by assignee"
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

        <input
          type="date"
          className={SELECT_CLS}
          style={{ width: "140px" }}
          value={params.from_date ?? ""}
          onChange={(e) =>
            onChange({ ...params, from_date: e.target.value || undefined, page: 1 })
          }
          aria-label="From date"
        />
        <input
          type="date"
          className={SELECT_CLS}
          style={{ width: "140px" }}
          value={params.to_date ?? ""}
          onChange={(e) =>
            onChange({ ...params, to_date: e.target.value || undefined, page: 1 })
          }
          aria-label="To date"
        />

        <div className="relative">
          <Search
            size={14}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-muted pointer-events-none"
            aria-hidden="true"
          />
          <input
            type="search"
            placeholder="Search..."
            className={`${SELECT_CLS} pl-8`}
            style={{ width: "200px" }}
            value={searchInput}
            onChange={(e) => onSearchChange(e.target.value)}
            aria-label="Search action items"
          />
        </div>

        {hasAnyFilter && (
          <button
            type="button"
            onClick={onClearFilters}
            className="text-[14px] text-muted underline hover:text-ink"
          >
            Clear filters
          </button>
        )}
      </div>

      <p className="text-[14px] text-muted">
        Showing {filtered} of {total} action items
      </p>
    </div>
  );
}
