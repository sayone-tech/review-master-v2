// Phase 21-04 — AuditLogWidget root.
// Composes filters, table, and cursor pagination footer.

import { ChevronLeft, ChevronRight } from "lucide-react";
import { AuditLogFilters } from "./AuditLogFilters";
import { AuditLogTable } from "./AuditLogTable";
import type { ActorOption, FilterParams } from "./types";
import { useAuditLog } from "./useAuditLog";

interface Props {
  userRole: string;
  actors: ActorOption[];
}

const DEFAULT_DATE_WINDOW_DAYS = 30;

function isoDate(d: Date): string {
  return d.toISOString().split("T")[0];
}

function defaultDateRange(): { date_from: string; date_to: string } {
  const today = new Date();
  const from = new Date(Date.now() - DEFAULT_DATE_WINDOW_DAYS * 24 * 60 * 60 * 1000);
  return { date_from: isoDate(from), date_to: isoDate(today) };
}

function computeHasActiveFilters(filters: FilterParams): boolean {
  const defaults = defaultDateRange();
  if (filters.entity_type) return true;
  if (filters.actor) return true;
  if (filters.date_from && filters.date_from !== defaults.date_from) return true;
  if (filters.date_to && filters.date_to !== defaults.date_to) return true;
  return false;
}

const pageBtnCls =
  "w-8 h-8 rounded-sm bg-white border border-line flex items-center justify-center disabled:opacity-40 disabled:cursor-not-allowed enabled:hover:bg-line-soft";

export function AuditLogWidget({ userRole: _userRole, actors }: Props) {
  // userRole is currently unused at the React layer — server-side scoping handles
  // role filtering. Prop is retained on the public API so the entrypoint contract
  // is stable and future role-specific UI can hook in without changing callers.
  void _userRole;
  const {
    rows,
    loading,
    error,
    filters,
    pageSize,
    hasNext,
    hasPrev,
    goNext,
    goPrev,
    applyFilters,
    resetFilters,
    changePageSize,
    refetch,
    expandedId,
    setExpandedId,
  } = useAuditLog();

  const hasActiveFilters = computeHasActiveFilters(filters);

  return (
    <div className="space-y-4">
      <h1 className="text-[20px] font-semibold text-ink">Activity Log</h1>

      <AuditLogFilters
        filters={filters}
        actors={actors}
        onApply={applyFilters}
        onReset={resetFilters}
        hasActiveFilters={hasActiveFilters}
      />

      <div className="border border-line rounded-card overflow-hidden">
        <AuditLogTable
          rows={rows}
          loading={loading}
          error={error}
          onRetry={refetch}
          hasActiveFilters={hasActiveFilters}
          onClearFilters={resetFilters}
          expandedId={expandedId}
          onExpand={setExpandedId}
        />

        <nav
          aria-label="Pagination"
          className="flex items-center justify-between px-4 py-3 border-t border-line bg-[#FBFBFB] text-[12px] text-muted"
        >
          <label className="inline-flex items-center gap-2">
            <span>Rows:</span>
            <select
              aria-label="Rows per page"
              value={pageSize}
              onChange={(e) => changePageSize(Number(e.target.value))}
              className="px-2 py-1 text-[12px] text-ink bg-white border border-line rounded-sm outline-none cursor-pointer"
            >
              <option value={10}>10</option>
              <option value={25}>25</option>
              <option value={50}>50</option>
            </select>
          </label>

          <div className="flex items-center gap-2">
            <button
              type="button"
              aria-label="Previous page"
              disabled={!hasPrev}
              onClick={goPrev}
              className={pageBtnCls}
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <button
              type="button"
              aria-label="Next page"
              disabled={!hasNext}
              onClick={goNext}
              className={pageBtnCls}
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </nav>
      </div>
    </div>
  );
}
