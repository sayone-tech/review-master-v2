import { useMemo, useState } from "react";
import { ReviewEmptyStates } from "./ReviewEmptyStates";
import { ReviewFilters } from "./ReviewFilters";
import { ReviewTable } from "./ReviewTable";
import { useReviews } from "./useReviews";
import type { ReviewRow, ShopOption } from "./types";

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
    setSearch,
    setShop,
    setRating,
    setSentiment,
    setIsReplied,
    setFromDate,
    setToDate,
    setOrdering,
    setPageSize,
    goNext,
    goPrev,
    clearFilters,
    replaceRow,
  } = useReviews();

  const [openComposerId, setOpenComposerId] = useState<number | null>(null);
  // REVW-06 — track per-review "Show more" toggle for comments > 1000 chars.
  // Map<review.id, boolean> where true = show full text. Defaults to truncated.
  const [showFullComment, setShowFullComment] = useState<Map<number, boolean>>(
    () => new Map(),
  );
  const toggleShowFullComment = (reviewId: number) => {
    setShowFullComment((prev) => {
      const next = new Map(prev);
      next.set(reviewId, !prev.get(reviewId));
      return next;
    });
  };

  const isOrgAdmin = userRole === "ORG_ADMIN";
  const pageSize = filters.page_size ?? 10;
  const pageStart = rows.length === 0 ? 0 : 1;
  const pageEnd = rows.length;

  const hasAnyFilter = Boolean(
    filters.search ||
      filters.shop !== undefined ||
      filters.rating !== undefined ||
      filters.sentiment ||
      filters.is_replied !== undefined ||
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
    // Plan 10: dispatch event for Plan 11's ReplyComposer to listen to.
    // Plan 11 sets openComposerId via window event.
    window.dispatchEvent(new CustomEvent("review:open-composer", { detail: row }));
    setOpenComposerId(row.id);
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-[20px] font-semibold text-ink">
          Reviews{" "}
          <span className="text-[14px] text-muted font-normal">({count})</span>
        </h1>
      </div>
      <ReviewFilters
        shops={shops}
        filters={filters}
        totalCount={count}
        pageStart={pageStart}
        pageEnd={pageEnd}
        onSearch={setSearch}
        onShop={setShop}
        onRating={setRating}
        onSentiment={setSentiment}
        onIsReplied={setIsReplied}
        onFromDate={setFromDate}
        onToDate={setToDate}
        onOrdering={setOrdering}
        onClearAll={clearFilters}
      />
      <ReviewTable
        rows={rows}
        loading={loading}
        emptyState={emptyState}
        onReply={handleReplyCtaClick}
        expandedRowId={openComposerId}
        showFullComment={showFullComment}
        onToggleShowFullComment={toggleShowFullComment}
        onComposerSuccess={(updated) => {
          // Replace row in state so badge + reply text update immediately.
          // Keep composer open showing the success view; user closes manually.
          replaceRow(updated);
        }}
        onComposerClose={() => setOpenComposerId(null)}
      />
      <div className="flex items-center justify-between mt-4">
        <select
          className="px-3 py-2 text-[14px] bg-white border border-line rounded-md"
          value={pageSize}
          onChange={(e) => setPageSize(Number(e.target.value) as 10 | 25 | 50 | 100)}
          aria-label="Rows per page"
        >
          <option value={10}>10 / page</option>
          <option value={25}>25 / page</option>
          <option value={50}>50 / page</option>
          <option value={100}>100 / page</option>
        </select>
        <div className="flex items-center gap-2">
          <button
            type="button"
            className="px-3 py-2 text-[14px] border border-line rounded-md disabled:opacity-40"
            onClick={goPrev}
            disabled={!previous}
          >
            Previous
          </button>
          <button
            type="button"
            className="px-3 py-2 text-[14px] border border-line rounded-md disabled:opacity-40"
            onClick={goNext}
            disabled={!next}
          >
            Next
          </button>
        </div>
      </div>
    </div>
  );
};
