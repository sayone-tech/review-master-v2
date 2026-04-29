import { useEffect, useRef, useState } from "react";
import { Edit2, Mail, Trash2 } from "lucide-react";
import { DataTable } from "../data-table/DataTable";
import { useTeam } from "./useTeam";
import { RoleBadge } from "./RoleBadge";
import { AccessChips } from "./AccessChips";
import { EnabledToggle } from "./EnabledToggle";
import { TeamStatsCards } from "./TeamStatsCards";
import { SoloMemberBanner } from "./SoloMemberBanner";
import { TeamEmptyState } from "./TeamEmptyState";
import type { TeamMemberRow, RegionOption, ShopOption, TeamStats } from "./types";

function dispatchTeamEvent(name: string, detail: TeamMemberRow) {
  window.dispatchEvent(new CustomEvent(name, { detail }));
}

interface TeamTableWidgetProps {
  initial: { rows: TeamMemberRow[]; stats: TeamStats };
  regions: RegionOption[];
  activeShops: ShopOption[];
  currentUserId: number;
}

const inputCls =
  "px-3 py-2 text-[14px] bg-white border border-line rounded-md focus:outline-none focus:ring focus:ring-black/[0.06] focus:border-ink";

export function TeamTableWidget({
  initial,
  regions,
  activeShops,
  currentUserId,
}: TeamTableWidgetProps) {
  const { rows, count, loading, stats, filters, setSearch, setRegion, setShop, setPage, setPageSize, refetch } =
    useTeam(initial);
  const [searchInput, setSearchInput] = useState(filters.search ?? "");
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const managerCount = stats.managers;

  // Debounced search
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => setSearch(searchInput), 300);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchInput]);

  // Subscribe to refresh events
  useEffect(() => {
    const handler = () => {
      refetch();
    };
    const events = [
      "team:member-added",
      "team:member-updated",
      "team:member-removed",
      "team:member-toggled",
    ];
    events.forEach((evt) => window.addEventListener(evt, handler));
    return () => {
      events.forEach((evt) => window.removeEventListener(evt, handler));
    };
  }, [refetch]);

  // Filter store options by selected region (UI-side only)
  const filteredShops = filters.region_id
    ? activeShops.filter((s) => s.region === filters.region_id)
    : activeShops;

  const isSoloAdmin = stats.total_members === 1;

  const columns = [
    {
      key: "member",
      label: "MEMBER",
      accessor: (row: TeamMemberRow) => (
        <div>
          <div className="text-[14px] font-semibold text-ink">{row.full_name}</div>
          <div className="text-[12px] text-muted">{row.email}</div>
        </div>
      ),
    },
    {
      key: "role",
      label: "ROLE",
      accessor: (row: TeamMemberRow) => <RoleBadge role={row.role} />,
    },
    {
      key: "access",
      label: "ACCESS",
      accessor: (row: TeamMemberRow) => <AccessChips member={row} />,
    },
    {
      key: "status",
      label: "STATUS",
      accessor: (row: TeamMemberRow) => {
        const map = {
          ACTIVE: { backgroundColor: "#F0FDF4", color: "#16A34A", label: "Active" },
          PENDING: { backgroundColor: "#FEF3C7", color: "#D97706", label: "Pending" },
          DISABLED: { backgroundColor: "#F9FAFB", color: "#6B7280", label: "Disabled" },
        } as const;
        const v = map[row.status];
        return (
          <span
            style={{ backgroundColor: v.backgroundColor, color: v.color }}
            className="inline-flex items-center px-2 py-[2px] rounded-full text-[12px] font-semibold"
          >
            {v.label}
          </span>
        );
      },
    },
    {
      key: "invited",
      label: "INVITED",
      accessor: (row: TeamMemberRow) => row.invited_at?.slice(0, 10) ?? "—",
    },
    {
      key: "enabled",
      label: "ENABLED",
      accessor: (row: TeamMemberRow) => {
        const isOwnRow = row.id === currentUserId;
        return (
          <EnabledToggle
            enabled={row.is_active}
            memberName={row.full_name}
            disabled={isOwnRow || row.status === "PENDING"}
            disabledReason={
              isOwnRow
                ? "You cannot disable yourself."
                : "Pending members cannot be toggled."
            }
            onDisableRequest={() => dispatchTeamEvent("team:open-disable", row)}
            onEnableRequest={() => {
              dispatchTeamEvent("team:open-enable", row);
            }}
          />
        );
      },
    },
  ];

  function renderRowActions(row: TeamMemberRow) {
    const isOwnRow = row.id === currentUserId;
    const isLastManager = row.role === "ORG_ADMIN" && managerCount === 1;
    const isPending = row.status === "PENDING";
    return (
      <div className="flex items-center gap-1">
        {isPending ? (
          <button
            type="button"
            onClick={() => dispatchTeamEvent("team:open-resend", row)}
            className="w-8 h-8 inline-flex items-center justify-center text-subtle hover:text-blue rounded"
            aria-label={`Resend invitation to ${row.email}`}
            title={`Resend invitation to ${row.email}`}
          >
            <Mail size={14} />
          </button>
        ) : (
          <button
            type="button"
            onClick={() => !isOwnRow && dispatchTeamEvent("team:open-edit", row)}
            disabled={isOwnRow}
            aria-disabled={isOwnRow || undefined}
            className={`w-8 h-8 inline-flex items-center justify-center rounded ${
              isOwnRow ? "opacity-40 cursor-not-allowed" : "text-subtle hover:text-ink"
            }`}
            aria-label={`Edit ${row.full_name}`}
            title={isOwnRow ? "You cannot edit yourself." : `Edit ${row.full_name}`}
          >
            <Edit2 size={14} />
          </button>
        )}
        <button
          type="button"
          onClick={() =>
            !(isOwnRow || isLastManager) && dispatchTeamEvent("team:open-remove", row)
          }
          disabled={isOwnRow || isLastManager}
          aria-disabled={isOwnRow || isLastManager || undefined}
          className={`w-8 h-8 inline-flex items-center justify-center rounded ${
            isOwnRow || isLastManager
              ? "opacity-40 cursor-not-allowed"
              : "text-subtle hover:text-red"
          }`}
          aria-label={`Remove ${row.full_name}`}
          title={
            isOwnRow
              ? "You cannot remove yourself."
              : isLastManager
                ? "Cannot remove the last Manager."
                : `Remove ${row.full_name}`
          }
        >
          <Trash2 size={14} />
        </button>
      </div>
    );
  }

  const noActiveFilters = !filters.search && !filters.region_id && !filters.shop_id;
  const emptyState = noActiveFilters ? (
    <TeamEmptyState />
  ) : (
    <div className="p-12 text-center text-muted text-[14px]">No matching team members.</div>
  );

  const pageSize = filters.page_size ?? 10;
  const page = filters.page ?? 1;
  const start = count === 0 ? 0 : (page - 1) * pageSize + 1;
  const end = Math.min(page * pageSize, count);

  return (
    <div className="space-y-4">
      <TeamStatsCards stats={stats} />
      {isSoloAdmin && <SoloMemberBanner />}
      <div className="flex items-center gap-2 flex-wrap">
        <input
          type="search"
          placeholder="Search name or email…"
          value={searchInput}
          onChange={(e) => setSearchInput(e.target.value)}
          className={`${inputCls} flex-1 min-w-[200px]`}
          data-testid="team-search"
        />
        <select
          value={filters.region_id ?? ""}
          onChange={(e) =>
            setRegion(e.target.value ? Number(e.target.value) : undefined)
          }
          className={inputCls}
          data-testid="team-region-filter"
        >
          <option value="">All Regions</option>
          {regions.map((r) => (
            <option key={r.id} value={r.id}>
              {r.name}
            </option>
          ))}
        </select>
        <select
          value={filters.shop_id ?? ""}
          onChange={(e) =>
            setShop(e.target.value ? Number(e.target.value) : undefined)
          }
          className={inputCls}
          disabled={!filters.region_id}
          title={!filters.region_id ? "Select a region first" : undefined}
          data-testid="team-shop-filter"
        >
          <option value="">All Stores</option>
          {filteredShops.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </select>
      </div>
      <DataTable<TeamMemberRow>
        columns={columns}
        rows={rows}
        loading={loading}
        rowKey={(r) => String(r.id)}
        emptyState={emptyState}
        renderRowActions={renderRowActions}
      />
      <div className="flex items-center justify-between text-[13px] text-muted">
        <div>
          Showing {start}–{end} of {count}
        </div>
        <div className="flex items-center gap-2">
          <label htmlFor="team-page-size" className="text-[12px]">
            Rows per page:
          </label>
          <select
            id="team-page-size"
            value={pageSize}
            onChange={(e) => setPageSize(Number(e.target.value))}
            className={inputCls}
          >
            {[10, 25, 50, 100].map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </select>
          <button
            type="button"
            onClick={() => setPage(Math.max(1, page - 1))}
            disabled={page <= 1}
            className="px-2 py-1 border border-line rounded-md disabled:opacity-50"
          >
            Prev
          </button>
          <button
            type="button"
            onClick={() => setPage(page + 1)}
            disabled={end >= count}
            className="px-2 py-1 border border-line rounded-md disabled:opacity-50"
          >
            Next
          </button>
        </div>
      </div>
    </div>
  );
}
