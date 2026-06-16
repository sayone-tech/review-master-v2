// Phase 25-03 — Root widget for the Tags management page.
// Mirrors AuditLogWidget shell: space-y-4, h1, border card with pagination footer.
// Composes TagTable + MergeProgressBanner + TagMergeModal.

import { ChevronLeft, ChevronRight } from "lucide-react";
import { useState } from "react";
import { MergeProgressBanner } from "./MergeProgressBanner";
import { TagMergeModal } from "./TagMergeModal";
import { TagTable } from "./TagTable";
import { useMergeProgress } from "./useMergeProgress";
import { useTagList } from "./useTagList";
import type { OrgCanonicalTagRow } from "./types";

const pageBtnCls =
  "w-8 h-8 rounded-sm bg-white border border-line flex items-center justify-center disabled:opacity-40 disabled:cursor-not-allowed enabled:hover:bg-line-soft";

export function TagManagementWidget() {
  const {
    rows,
    loading,
    error,
    ordering,
    page,
    pageSize,
    totalPages,
    hasNext,
    hasPrev,
    goNext,
    goPrev,
    toggleOrdering,
    changePageSize,
    refetch,
  } = useTagList();

  // Local override for optimistic rename update (clears on next refetch)
  const [localRows, setLocalRows] = useState<OrgCanonicalTagRow[] | null>(null);
  const displayRows = localRows ?? rows;

  const handleRowRenamed = (updated: OrgCanonicalTagRow) => {
    setLocalRows((prev) =>
      (prev ?? rows).map((r: OrgCanonicalTagRow) => (r.id === updated.id ? updated : r)),
    );
  };

  const handleRefetch = async () => {
    setLocalRows(null);
    await refetch();
  };

  const [mergeSource, setMergeSource] = useState<OrgCanonicalTagRow | null>(null);
  const { job, visible: bannerVisible, dismiss, kickoff } = useMergeProgress();

  const handleJobStarted = (_jobId: number) => {
    kickoff(); // start polling immediately
  };

  const handleMergeComplete = () => {
    void handleRefetch(); // refetch table after SUCCESS
  };

  return (
    <div className="space-y-4">
      <h1 className="text-[20px] font-semibold text-ink">Tags</h1>

      {bannerVisible && job && (
        <MergeProgressBanner
          job={job}
          onDismiss={dismiss}
          onComplete={handleMergeComplete}
        />
      )}

      <div className="border border-line rounded-card overflow-hidden">
        <TagTable
          rows={displayRows}
          loading={loading}
          error={error}
          ordering={ordering}
          onToggleOrdering={toggleOrdering}
          onRetry={() => void handleRefetch()}
          onRowRenamed={handleRowRenamed}
          onMergeSource={(row) => setMergeSource(row)}
        />

        <nav
          aria-label="Pagination"
          className="flex items-center justify-between px-4 py-3 border-t border-line bg-[#FBFBFB] text-[12px] text-muted"
        >
          <div className="flex items-center gap-2">
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
          </div>

          <div className="flex items-center gap-2">
            <span>
              Page {page} of {totalPages}
            </span>
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

      <TagMergeModal
        open={mergeSource !== null}
        source={mergeSource}
        onClose={() => setMergeSource(null)}
        onJobStarted={handleJobStarted}
      />
    </div>
  );
}
