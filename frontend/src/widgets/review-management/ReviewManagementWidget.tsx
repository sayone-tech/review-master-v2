import { useEffect, useMemo, useState } from "react";
import { ChevronDown, ChevronLeft, ChevronRight } from "lucide-react";
import { ReviewEmptyStates } from "./ReviewEmptyStates";
import { ReviewFilters } from "./ReviewFilters";
import { ReviewStatsCards } from "./ReviewStatsCards";
import { ReviewTable } from "./ReviewTable";
import { fetchReviewStats } from "./api";
import { useReviews } from "./useReviews";
import type { ReviewRow, ReviewStats, ShopOption, SortKey } from "./types";

function buildPageRange(current: number, total: number): (number | "…")[] {
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1);
  if (current <= 4) return [1, 2, 3, 4, 5, "…", total];
  if (current >= total - 3) return [1, "…", total - 4, total - 3, total - 2, total - 1, total];
  return [1, "…", current - 1, current, current + 1, "…", total];
}

interface Props {
  userRole: string;
  openProgressShopId: number | null;
  initialShops?: ShopOption[];
  hasConnectedShops?: boolean;
}

function readJsonScript<T>(id: string, fallback: T): T {
  if (typeof document === "undefined") return fallback;
  const el = document.getElementById(id);
  if (!el) return fallback;
  try {
    return JSON.parse(el.textContent ?? "") as T;
  } catch {
    return fallback;
  }
}

export const ReviewManagementWidget = ({
  userRole,
  openProgressShopId: _openProgressShopId,
  initialShops,
  hasConnectedShops,
}: Props) => {
  const shops = useMemo<ShopOption[]>(
    () => initialShops ?? readJsonScript<ShopOption[]>("review-shops-data", []),
    [initialShops],
  );
  const connected =
    hasConnectedShops ?? readJsonScript<boolean>("review-has-connected-shops", false);

  const {
    rows,
    count,
    next,
    previous,
    loading,
    filters,
    currentPage,
    totalPages,
    applyFilters,
    clearFilters,
    setOrdering,
    setPageSize,
    goToPage,
    goNext,
    goPrev,
    replaceRow,
  } = useReviews();

  const [openComposerId, setOpenComposerId] = useState<number | null>(null);
  const [showFullComment, setShowFullComment] = useState<Map<number, boolean>>(() => new Map());
  const toggleShowFullComment = (reviewId: number) => {
    setShowFullComment((prev) => {
      const next = new Map(prev);
      next.set(reviewId, !prev.get(reviewId));
      return next;
    });
  };

  // Stats cards
  const [stats, setStats] = useState<ReviewStats | null>(null);
  const [statsLoading, setStatsLoading] = useState(true);
  useEffect(() => {
    setStatsLoading(true);
    fetchReviewStats()
      .then(setStats)
      .catch(() => {})
      .finally(() => setStatsLoading(false));
  }, []);

  const isOrgAdmin = userRole === "ORG_ADMIN";
  const pageSize = filters.page_size ?? 10;
  const showingFrom = count === 0 ? 0 : (currentPage - 1) * pageSize + 1;
  const showingTo = count === 0 ? 0 : Math.min(currentPage * pageSize, count);

  const hasAnyFilter = Boolean(
    filters.search ||
      filters.shop !== undefined ||
      filters.rating !== undefined ||
      filters.sentiment ||
      filters.is_replied !== undefined ||
      filters.has_comment !== undefined ||
      filters.from_date ||
      filters.to_date,
  );

  let emptyState: React.ReactNode = null;
  if (!loading && rows.length === 0) {
    if (!connected) {
      emptyState = <ReviewEmptyStates.EmptyStateA isOrgAdmin={isOrgAdmin} />;
    } else if (hasAnyFilter) {
      emptyState = <ReviewEmptyStates.EmptyStateC onClearFilters={clearFilters} />;
    } else {
      emptyState = <ReviewEmptyStates.EmptyStateB />;
    }
  }

  const handleReplyCtaClick = (row: ReviewRow) => {
    window.dispatchEvent(new CustomEvent("review:open-composer", { detail: row }));
    setOpenComposerId(row.id);
  };

  return (
    <div className="space-y-4">
      {/* Stats cards */}
      <ReviewStatsCards stats={stats} loading={statsLoading} />

      <div className="flex items-center justify-between">
        <h1 className="text-[20px] font-semibold text-ink">
          Reviews{" "}
          <span className="text-[14px] text-muted font-normal">({count})</span>
        </h1>
      </div>

      {/* Filter bar */}
      <ReviewFilters
        shops={shops}
        filters={filters}
        onApply={(draft) =>
          applyFilters({
            search: draft.search || undefined,
            shop: draft.shop,
            rating: draft.rating,
            sentiment: draft.sentiment,
            is_replied: draft.is_replied,
            has_comment: draft.has_comment,
            from_date: draft.from_date,
            to_date: draft.to_date,
          })
        }
        onReset={clearFilters}
      />

      <div className="border border-line rounded-card overflow-hidden">
        <ReviewTable
          rows={rows}
          loading={loading}
          emptyState={emptyState}
          onReply={handleReplyCtaClick}
          expandedRowId={openComposerId}
          showFullComment={showFullComment}
          onToggleShowFullComment={toggleShowFullComment}
          onComposerSuccess={(updated) => {
            replaceRow(updated);
          }}
          onComposerClose={() => setOpenComposerId(null)}
        />
        <nav
          className="flex items-center justify-between px-4 py-3 border-t border-line bg-[#FBFBFB] text-[13px] text-muted"
          aria-label="Pagination"
          data-testid="pagination"
        >
          <div className="flex items-center gap-3">
            {count > 0 ? (
              <span>
                Showing{" "}
                <strong className="text-ink font-semibold">
                  {showingFrom}–{showingTo}
                </strong>{" "}
                of <strong className="text-ink font-semibold">{count}</strong>
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
                  onChange={(e) => setPageSize(Number(e.target.value) as 10 | 25 | 50 | 100)}
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
            {/* Sort — lives in pagination footer */}
            <div className="flex items-center gap-1.5">
              <label className="text-[12px] text-muted">Sort:</label>
              <div className="inline-flex items-center bg-white border border-line rounded-sm focus-within:border-ink">
                <select
                  className="appearance-none pl-2 pr-1 py-1 text-[12.5px] bg-transparent focus:outline-none cursor-pointer"
                  value={filters.ordering ?? "-review_create_time"}
                  onChange={(e) => setOrdering(e.target.value as SortKey)}
                  aria-label="Sort order"
                >
                  <option value="-review_create_time">Newest first</option>
                  <option value="review_create_time">Oldest first</option>
                  <option value="-star_rating">Highest rating</option>
                  <option value="star_rating">Lowest rating</option>
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
              onClick={goPrev}
              disabled={!previous}
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
                  onClick={() => goToPage(p)}
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
              onClick={goNext}
              disabled={!next}
              className="w-[30px] h-[30px] rounded-sm bg-white border border-line text-[13px] font-medium flex items-center justify-center disabled:opacity-40 disabled:cursor-not-allowed enabled:hover:bg-line-soft"
              aria-label="Next page"
            >
              <ChevronRight className="w-3.5 h-3.5" aria-hidden="true" />
            </button>
          </div>
        </nav>
      </div>
    </div>
  );
};
