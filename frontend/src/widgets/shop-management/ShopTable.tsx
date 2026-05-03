import { useEffect, useRef, useState } from "react";
import { ChevronDown, ChevronLeft, ChevronRight, Eye, Edit2, Power, PowerOff, RefreshCcw } from "lucide-react";
import { DataTable } from "../data-table/DataTable";
import { ShopsEmptyStateA } from "./ShopsEmptyStateA";
import { ShopsEmptyStateB } from "./ShopsEmptyStateB";
import { ShopRowActionsMenu, type RowAction } from "./ShopRowActionsMenu";
import { useShops } from "./useShops";
import type { AllocationStatus, ShopRow } from "./types";
import { ProgressModal } from "../review-management/ProgressModal";

function dispatchShopEvent(name: string, row: ShopRow) {
  window.dispatchEvent(new CustomEvent(name, { detail: row }));
}

const SHOP_ACTIONS: RowAction[] = [
  {
    key: "details",
    label: "View Details",
    icon: <Eye size={14} />,
    onSelect: (r) => dispatchShopEvent("shop:open-details", r),
  },
  {
    key: "edit",
    label: "Edit",
    icon: <Edit2 size={14} />,
    onSelect: (r) => dispatchShopEvent("shop:open-edit", r),
  },
  {
    key: "deactivate",
    label: "Deactivate",
    icon: <PowerOff size={14} />,
    tone: "amber",
    visible: (r) => r.is_active,
    onSelect: (r) => dispatchShopEvent("shop:open-deactivate", r),
  },
  {
    key: "activate",
    label: "Activate",
    icon: <Power size={14} />,
    visible: (r) => !r.is_active,
    onSelect: (r) => dispatchShopEvent("shop:open-activate", r),
  },
  {
    key: "reconnect",
    label: "Reconnect Google",
    icon: <RefreshCcw size={14} />,
    separatorBefore: true,
    visible: (r) =>
      r.connection_method === "GOOGLE_OAUTH" &&
      (r.connection_status === "ERROR" || r.connection_status === "EXPIRED"),
    onSelect: (r) => dispatchShopEvent("shop:open-reconnect", r),
  },
];

const inputCls =
  "px-3 py-2 text-[13.5px] bg-white border border-line rounded-md focus:outline-none focus:ring focus:ring-black/[0.06] focus:border-ink";

interface ShopTableWidgetProps {
  initial: { rows: ShopRow[]; allocation: AllocationStatus; hasRegions: boolean };
  openProgressShopId?: number | null;
}

export function ShopTableWidget({ initial, openProgressShopId }: ShopTableWidgetProps) {
  const {
    rows,
    count,
    loading,
    allocation,
    hasRegions,
    filters,
    setSearch,
    setStatus,
    setRegion,
    setPage,
    setPageSize,
  } = useShops(initial);

  const [searchInput, setSearchInput] = useState(filters.search ?? "");

  const [progressShopId, setProgressShopId] = useState<number | null>(
    openProgressShopId ?? null,
  );
  const [progressShopName, setProgressShopName] = useState<string>("");

  useEffect(() => {
    if (progressShopId !== null) {
      const found = rows.find((r) => r.id === progressShopId);
      setProgressShopName(found?.name ?? `Shop ${progressShopId}`);
      // Clear ?open_progress from URL so refresh doesn't re-open the modal.
      try {
        const url = new URL(window.location.href);
        url.searchParams.delete("open_progress");
        window.history.replaceState({}, "", url.toString());
      } catch {
        // no-op
      }
    }
  }, [progressShopId, rows]);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Debounced search — 300 ms
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      setSearch(searchInput);
    }, 300);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchInput]);

  // Compute distinct regions from current rows
  // TODO: fetch full region list from API for complete dropdown
  const regions = Array.from(
    new Map(
      rows
        .filter((r) => r.region !== null)
        .map((r) => [r.region, r.region_name] as [number, string]),
    ).entries(),
  );

  const noActiveFilters =
    !filters.search && !filters.status && (filters.region === undefined || filters.region === "");

  const emptyState = noActiveFilters ? (
    !hasRegions ? <ShopsEmptyStateA /> : <ShopsEmptyStateB />
  ) : (
    <div className="p-12 text-center text-muted text-[13.5px]">No matching shops.</div>
  );

  const columns = [
    {
      key: "name",
      label: "SHOP NAME",
      skeletonWidth: "180px",
      accessor: (row: ShopRow) => (
        <button
          type="button"
          onClick={() => dispatchShopEvent("shop:open-details", row)}
          className="font-semibold text-ink hover:underline text-left"
          data-testid={`shop-name-${row.id}`}
        >
          {row.name}
        </button>
      ),
    },
    {
      key: "region",
      label: "REGION",
      skeletonWidth: "60px",
      accessor: (row: ShopRow) =>
        row.region_region_id ? (
          <span className="inline-flex items-center px-2 py-[2px] rounded-full text-[12px] font-medium bg-line-soft text-ink font-mono">
            {row.region_region_id}
          </span>
        ) : (
          <span className="text-muted">—</span>
        ),
    },
    {
      key: "contact",
      label: "CONTACT",
      skeletonWidth: "100px",
      accessor: (row: ShopRow) =>
        row.phone ? row.phone : <span className="text-muted">—</span>,
    },
    {
      key: "status",
      label: "STATUS",
      skeletonWidth: "60px",
      accessor: (row: ShopRow) => (
        <span
          style={
            row.is_active
              ? { backgroundColor: "#F0FDF4", color: "#16A34A" }
              : { backgroundColor: "#F9FAFB", color: "#6B7280" }
          }
          className="inline-flex items-center px-2 py-[2px] rounded-full text-[12px] font-medium"
        >
          {row.is_active ? "Active" : "Inactive"}
        </span>
      ),
    },
    {
      key: "created",
      label: "CREATED",
      skeletonWidth: "80px",
      accessor: (row: ShopRow) => row.created_at?.slice(0, 10) ?? "",
    },
  ];

  const pageSize = filters.page_size ?? 10;
  const page = filters.page ?? 1;
  const start = count === 0 ? 0 : (page - 1) * pageSize + 1;
  const end = Math.min(page * pageSize, count);

  return (
    <div className="space-y-3">
      {/* Filters */}
      <div className="flex items-center gap-2 flex-wrap">
        <input
          type="search"
          placeholder="Search name, address…"
          value={searchInput}
          onChange={(e) => setSearchInput(e.target.value)}
          className={`${inputCls} flex-1 min-w-[180px]`}
          data-testid="shops-search"
        />
        <select
          value={filters.status ?? ""}
          onChange={(e) =>
            setStatus((e.target.value as "active" | "inactive" | "") || "")
          }
          className={inputCls}
          data-testid="shops-status-filter"
        >
          <option value="">All Statuses</option>
          <option value="active">Active</option>
          <option value="inactive">Inactive</option>
        </select>
        <select
          value={
            filters.region === undefined || filters.region === ""
              ? ""
              : String(filters.region)
          }
          onChange={(e) => setRegion(e.target.value ? Number(e.target.value) : "")}
          className={inputCls}
          data-testid="shops-region-filter"
        >
          <option value="">All Regions</option>
          {regions.map(([id, name]) => (
            <option key={String(id)} value={String(id)}>
              {name}
            </option>
          ))}
        </select>
      </div>

      <div className="border border-line rounded-card overflow-hidden">
        <DataTable<ShopRow>
          columns={columns}
          rows={rows}
          loading={loading}
          rowKey={(r) => String(r.id)}
          emptyState={emptyState}
          renderRowActions={(row) => <ShopRowActionsMenu row={row} actions={SHOP_ACTIONS} />}
          wrapperClassName="bg-white overflow-hidden"
        />
        <nav
          className="flex items-center justify-between px-4 py-3 border-t border-line bg-[#FBFBFB] text-[13px] text-muted"
          aria-label="Pagination"
          data-testid="pagination"
        >
        <div className="flex items-center gap-3">
          {count > 0 ? (
            <span>
              Showing <strong className="text-ink font-semibold">{start}–{end}</strong>{" "}
              of <strong className="text-ink font-semibold">{count}</strong>
            </span>
          ) : (
            <span className="text-muted">No results</span>
          )}
          <div className="flex items-center gap-1.5">
            <label htmlFor="shops-page-size" className="text-[12px] text-muted">Rows:</label>
            <div className="inline-flex items-center bg-white border border-line rounded-sm focus-within:border-ink">
              <select
                id="shops-page-size"
                value={pageSize}
                onChange={(e) => setPageSize(Number(e.target.value))}
                className="appearance-none pl-2 pr-1 py-1 text-[12.5px] bg-transparent focus:outline-none cursor-pointer"
                data-testid="shops-page-size"
              >
                {[10, 25, 50, 100].map((n) => (
                  <option key={n} value={n}>{n}</option>
                ))}
              </select>
              <ChevronDown className="pointer-events-none shrink-0 w-3 h-3 text-muted mr-1.5" aria-hidden="true" />
            </div>
          </div>
        </div>
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={() => setPage(Math.max(1, page - 1))}
            disabled={page <= 1}
            className="w-[30px] h-[30px] rounded-sm bg-white border border-line text-[13px] font-medium flex items-center justify-center disabled:opacity-40 disabled:cursor-not-allowed enabled:hover:bg-line-soft"
            aria-label="Previous page"
          >
            <ChevronLeft className="w-3.5 h-3.5" aria-hidden="true" />
          </button>
          <button
            type="button"
            onClick={() => setPage(page + 1)}
            disabled={end >= count}
            className="w-[30px] h-[30px] rounded-sm bg-white border border-line text-[13px] font-medium flex items-center justify-center disabled:opacity-40 disabled:cursor-not-allowed enabled:hover:bg-line-soft"
            aria-label="Next page"
          >
            <ChevronRight className="w-3.5 h-3.5" aria-hidden="true" />
          </button>
        </div>
        </nav>
      </div>

      {progressShopId !== null && (
        <ProgressModal
          open
          shopId={progressShopId}
          shopName={progressShopName}
          onClose={() => setProgressShopId(null)}
        />
      )}
    </div>
  );
}
