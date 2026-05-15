import { useEffect, useMemo, useState, type ReactNode } from "react";
import { ChevronDown, ChevronLeft, ChevronRight } from "lucide-react";
import { ActionItemFilters } from "./ActionItemFilters";
import { ActionItemTable } from "./ActionItemTable";
import { ActionItemModal } from "./ActionItemModal";
import { AssignModal } from "./AssignModal";
import { transitionStatus } from "./api";
import { useActionItems } from "./useActionItems";
import { emitToast } from "../../lib/toast";
import type {
  ActionItemCategory,
  ActionItemListRow,
  ActionItemScope,
  ActionItemStatus,
  ListParams,
  PaginatedActionItems,
  ShopOption,
  TeamMember,
  UserRole,
} from "./types";
import { STATUS_LABEL } from "./types";

interface Props {
  userRole: UserRole;
  userId: number;
  shops: ShopOption[];
  teamMembers: TeamMember[];
}

const DEFAULT_ORDERING = "-created_at";

function buildPageRange(current: number, total: number): (number | "…")[] {
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1);
  if (current <= 4) return [1, 2, 3, 4, 5, "…", total];
  if (current >= total - 3)
    return [1, "…", total - 4, total - 3, total - 2, total - 1, total];
  return [1, "…", current - 1, current, current + 1, "…", total];
}

function pickEmptyState(
  params: ListParams,
  data: PaginatedActionItems | null,
  userRole: UserRole,
  onClearFilters: () => void,
): ReactNode {
  if (!data || data.results.length > 0) return null;

  const hasFilter = Boolean(
    params.shop !== undefined ||
      params.status ||
      params.scope ||
      params.assignee ||
      params.from_date ||
      params.to_date ||
      params.search ||
      params.review !== undefined,
  );

  if (hasFilter) {
    return (
      <div className="px-4 py-12 text-center">
        <h3 className="text-[14px] font-semibold text-ink">No results</h3>
        <p className="text-[14px] text-muted mt-1">
          No action items match your current filters.
        </p>
        <button
          type="button"
          onClick={onClearFilters}
          className="text-[14px] text-muted underline hover:text-ink mt-3"
        >
          Clear filters
        </button>
      </div>
    );
  }

  if (userRole === "STAFF_ADMIN") {
    return (
      <div className="px-4 py-12 text-center">
        <h3 className="text-[14px] font-semibold text-ink">
          No action items for your shops
        </h3>
        <p className="text-[14px] text-muted mt-1">
          Action items for your assigned shops will appear here.
        </p>
      </div>
    );
  }

  return (
    <div className="px-4 py-12 text-center">
      <h3 className="text-[14px] font-semibold text-ink">No action items yet</h3>
      <p className="text-[14px] text-muted mt-1">
        Action items will appear here once reviews are enriched by AI.
      </p>
    </div>
  );
}

export function ActionItemManagementWidget({
  userRole,
  userId: _userId,
  shops,
  teamMembers,
}: Props) {
  const reviewParam = useMemo(() => {
    const p = new URLSearchParams(window.location.search);
    return p.get("review") ?? undefined;
  }, []);
  const { data, loading, params, setParams, refetch } = useActionItems({ reviewParam });

  const [openModalId, setOpenModalId] = useState<number | null>(null);
  const [assignRow, setAssignRow] = useState<ActionItemListRow | null>(null);

  const isOrgAdmin = userRole === "ORG_ADMIN";

  // Deep-link support: ?id={N} opens the detail modal on mount, then strips
  // the param so refresh doesn't re-open.
  useEffect(() => {
    const p = new URLSearchParams(window.location.search);
    const idParam = p.get("id");
    if (idParam && /^\d+$/.test(idParam)) {
      setOpenModalId(Number(idParam));
      p.delete("id");
      const qs = p.toString();
      const newUrl =
        window.location.pathname + (qs ? `?${qs}` : "") + window.location.hash;
      window.history.replaceState({}, "", newUrl);
    }
  }, []);

  const handleApplyFilters = (draft: {
    search: string;
    shop?: number;
    status?: ActionItemStatus;
    scope?: ActionItemScope;
    category?: ActionItemCategory;
    assignee?: string;
    from_date?: string;
    to_date?: string;
  }) => {
    setParams({
      ...params,
      page: 1,
      search: draft.search || undefined,
      shop: draft.shop,
      status: draft.status,
      scope: draft.scope,
      category: draft.category,
      assignee: draft.assignee,
      from_date: draft.from_date,
      to_date: draft.to_date,
    });
  };

  const handleReset = () => {
    setParams({
      page: 1,
      page_size: params.page_size,
      ordering: params.ordering,
    });
  };

  const handleTransition = async (id: number, status: ActionItemStatus) => {
    try {
      await transitionStatus(id, status);
      emitToast({ kind: "success", title: `Status updated to ${STATUS_LABEL[status]}` });
      void refetch();
    } catch {
      emitToast({
        kind: "error",
        title: "Could not update status. Please try again.",
      });
    }
  };

  const total = data?.count ?? 0;
  const currentPage = params.page;
  const pageSize = params.page_size;
  const totalPages = total > 0 ? Math.ceil(total / pageSize) : 1;
  const showingFrom = total === 0 ? 0 : (currentPage - 1) * pageSize + 1;
  const showingTo = total === 0 ? 0 : Math.min(currentPage * pageSize, total);

  return (
    <div className="space-y-4">
      <h1 className="text-[20px] font-semibold text-ink">Action Items</h1>

      <ActionItemFilters
        userRole={userRole}
        shops={shops}
        teamMembers={teamMembers}
        filters={params}
        onApply={handleApplyFilters}
        onReset={handleReset}
      />

      <div className="border border-line rounded-card overflow-hidden">
        <ActionItemTable
          rows={data?.results ?? []}
          loading={loading}
          emptyState={pickEmptyState(params, data, userRole, handleReset)}
          onOpenModal={setOpenModalId}
          onTransitionStatus={handleTransition}
          onAssign={setAssignRow}
          onViewTargets={(shopId) => { window.location.href = `/admin/org/shops/${shopId}/targets/`; }}
        />
        <nav
          className="flex items-center justify-between px-4 py-3 border-t border-line bg-[#FBFBFB] text-[13px] text-muted"
          aria-label="Pagination"
        >
          <div className="flex items-center gap-3">
            {total > 0 ? (
              <span>
                Showing{" "}
                <strong className="text-ink font-semibold">
                  {showingFrom}–{showingTo}
                </strong>{" "}
                of <strong className="text-ink font-semibold">{total}</strong>
              </span>
            ) : (
              <span className="text-muted">No results</span>
            )}
            <div className="flex items-center gap-1.5">
              <label className="text-[12px] text-muted">Rows:</label>
              <div className="inline-flex items-center bg-white border border-line rounded-sm focus-within:border-ink">
                <select
                  className="appearance-none pl-2 pr-1 py-1 text-[12.5px] bg-transparent focus:outline-none cursor-pointer"
                  value={pageSize}
                  onChange={(e) =>
                    setParams({
                      ...params,
                      page: 1,
                      page_size: Number(e.target.value),
                    })
                  }
                  aria-label="Rows per page"
                >
                  <option value={10}>10</option>
                  <option value={25}>25</option>
                  <option value={50}>50</option>
                  <option value={100}>100</option>
                </select>
                <ChevronDown
                  className="pointer-events-none shrink-0 w-3 h-3 text-muted mr-1.5"
                  aria-hidden="true"
                />
              </div>
            </div>
            <div className="flex items-center gap-1.5">
              <label className="text-[12px] text-muted">Sort:</label>
              <div className="inline-flex items-center bg-white border border-line rounded-sm focus-within:border-ink">
                <select
                  className="appearance-none pl-2 pr-1 py-1 text-[12.5px] bg-transparent focus:outline-none cursor-pointer"
                  value={params.ordering ?? DEFAULT_ORDERING}
                  onChange={(e) =>
                    setParams({ ...params, page: 1, ordering: e.target.value })
                  }
                  aria-label="Sort order"
                >
                  <option value="-created_at">Newest first</option>
                  <option value="created_at">Oldest first</option>
                  <option value="due_date">Due date (soonest)</option>
                  <option value="status">Status (To Do first)</option>
                  <option value="-priority">Priority (high first)</option>
                </select>
                <ChevronDown
                  className="pointer-events-none shrink-0 w-3 h-3 text-muted mr-1.5"
                  aria-hidden="true"
                />
              </div>
            </div>
          </div>
          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={() => setParams({ ...params, page: Math.max(1, currentPage - 1) })}
              disabled={currentPage <= 1}
              className="w-[30px] h-[30px] rounded-sm bg-white border border-line text-[13px] font-medium flex items-center justify-center disabled:opacity-40 disabled:cursor-not-allowed enabled:hover:bg-line-soft"
              aria-label="Previous page"
            >
              <ChevronLeft className="w-3.5 h-3.5" aria-hidden="true" />
            </button>
            {buildPageRange(currentPage, totalPages).map((p, i) =>
              p === "…" ? (
                <span
                  key={`ellipsis-${i}`}
                  className="w-[30px] h-[30px] flex items-center justify-center text-[13px] text-muted select-none"
                >
                  …
                </span>
              ) : (
                <button
                  key={p}
                  type="button"
                  onClick={() => setParams({ ...params, page: p })}
                  aria-current={p === currentPage ? "page" : undefined}
                  className={`w-[30px] h-[30px] rounded-sm text-[13px] font-medium flex items-center justify-center border ${
                    p === currentPage
                      ? "bg-black text-yellow border-black"
                      : "bg-white border-line hover:bg-line-soft"
                  }`}
                >
                  {p}
                </button>
              ),
            )}
            <button
              type="button"
              onClick={() =>
                setParams({ ...params, page: Math.min(totalPages, currentPage + 1) })
              }
              disabled={currentPage >= totalPages}
              className="w-[30px] h-[30px] rounded-sm bg-white border border-line text-[13px] font-medium flex items-center justify-center disabled:opacity-40 disabled:cursor-not-allowed enabled:hover:bg-line-soft"
              aria-label="Next page"
            >
              <ChevronRight className="w-3.5 h-3.5" aria-hidden="true" />
            </button>
          </div>
        </nav>
      </div>

      {openModalId !== null && (
        <ActionItemModal
          open={openModalId !== null}
          itemId={openModalId}
          shops={shops}
          teamMembers={teamMembers}
          onClose={() => setOpenModalId(null)}
          onChanged={() => void refetch()}
        />
      )}

      <AssignModal
        open={assignRow !== null}
        item={assignRow}
        teamMembers={teamMembers}
        onClose={() => setAssignRow(null)}
        onAssigned={() => void refetch()}
      />

    </div>
  );
}
