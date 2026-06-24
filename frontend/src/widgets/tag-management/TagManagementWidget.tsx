// Phase 25-03 — Root widget for the Tags management page.
// Mirrors AuditLogWidget shell: space-y-4, h1, border card with pagination footer.
// Composes TagTable + MergeProgressBanner + TagMergeModal.
// Phase 26-02 — Added debounced server-side search (TMGT-07), "Tags (N)" header count,
//               and "Showing X–Y of N · Rows: N" pagination footer (TMGT-08).

import { ChevronDown, ChevronLeft, ChevronRight } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { MergeProgressBanner } from "./MergeProgressBanner";
import { TagMergeModal } from "./TagMergeModal";
import { TagTable } from "./TagTable";
import { useMergeProgress } from "./useMergeProgress";
import { useTagList } from "./useTagList";
import type { OrgCanonicalTagRow } from "./types";

function buildPageRange(current: number, total: number): (number | "…")[] {
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1);
  if (current <= 4) return [1, 2, 3, 4, 5, "…", total];
  if (current >= total - 3) return [1, "…", total - 4, total - 3, total - 2, total - 1, total];
  return [1, "…", current - 1, current, current + 1, "…", total];
}

const inputCls =
  "px-3 py-2 text-[14px] bg-white border border-line rounded-md focus:outline-none focus:ring focus:ring-black/[0.06] focus:border-ink";

export function TagManagementWidget() {
  const {
    rows,
    count,
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
    setSearch,
    refetch,
  } = useTagList();

  // Debounced search — clones TeamTable.tsx pattern (lines 42–54)
  const [searchInput, setSearchInput] = useState("");
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => setSearch(searchInput), 300);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchInput]);

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

  // Pagination footer derivations — mirrors TeamTable.tsx lines 209–213
  const start = count === 0 ? 0 : (page - 1) * pageSize + 1;
  const end = Math.min(page * pageSize, count);
  const computedTotalPages = count > 0 ? Math.ceil(count / pageSize) : 1;

  return (
    <div className="space-y-4">
      {/* Header with "Tags (N)" count — mirrors team_list.html lines 7–9 */}
      <h1 className="text-[20px] font-semibold text-ink">
        Tags
        <span className="text-muted font-normal text-[14px] ml-1">({count})</span>
      </h1>

      {bannerVisible && job && (
        <MergeProgressBanner
          job={job}
          onDismiss={dismiss}
          onComplete={handleMergeComplete}
        />
      )}

      {/* Debounced server-side search input — mirrors TeamTable.tsx lines 220–227 */}
      <div className="flex items-center gap-2 flex-wrap">
        <input
          type="search"
          placeholder="Search tags…"
          value={searchInput}
          onChange={(e) => setSearchInput(e.target.value)}
          className={`${inputCls} flex-1 min-w-[200px]`}
          data-testid="tag-search"
        />
      </div>

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

        {/* "Showing X–Y of N · Rows: N" footer — mirrors TeamTable.tsx lines 271–337 */}
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
              <span className="text-muted">Showing 0–0 of 0</span>
            )}
            <div className="flex items-center gap-1.5">
              <label htmlFor="tag-page-size" className="text-[12px] text-muted">Rows:</label>
              <div className="inline-flex items-center bg-white border border-line rounded-sm focus-within:border-ink">
                <select
                  id="tag-page-size"
                  value={pageSize}
                  onChange={(e) => changePageSize(Number(e.target.value))}
                  className="appearance-none pl-2 pr-1 py-1 text-[12.5px] bg-transparent focus:outline-none cursor-pointer"
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
              onClick={goPrev}
              disabled={!hasPrev}
              className="w-[30px] h-[30px] rounded-sm bg-white border border-line text-[13px] font-medium flex items-center justify-center disabled:opacity-40 disabled:cursor-not-allowed enabled:hover:bg-line-soft"
              aria-label="Previous page"
            >
              <ChevronLeft className="w-3.5 h-3.5" aria-hidden="true" />
            </button>
            {buildPageRange(page, computedTotalPages).map((p, i) =>
              p === "…" ? (
                <span key={`ellipsis-${i}`} className="w-[30px] h-[30px] flex items-center justify-center text-[13px] text-muted select-none">…</span>
              ) : (
                <button
                  key={p}
                  type="button"
                  onClick={() => {
                    if (p !== page) {
                      // Navigate to page p by stepping from current page
                      const diff = (p as number) - page;
                      if (diff > 0) {
                        for (let step = 0; step < diff; step++) goNext();
                      } else {
                        for (let step = 0; step < -diff; step++) goPrev();
                      }
                    }
                  }}
                  aria-current={p === page ? "page" : undefined}
                  className={`w-[30px] h-[30px] rounded-sm text-[13px] font-medium flex items-center justify-center border ${p === page ? "bg-black text-yellow border-black" : "bg-white border-line hover:bg-line-soft"}`}
                >
                  {p}
                </button>
              )
            )}
            <button
              type="button"
              onClick={goNext}
              disabled={!hasNext}
              className="w-[30px] h-[30px] rounded-sm bg-white border border-line text-[13px] font-medium flex items-center justify-center disabled:opacity-40 disabled:cursor-not-allowed enabled:hover:bg-line-soft"
              aria-label="Next page"
            >
              <ChevronRight className="w-3.5 h-3.5" aria-hidden="true" />
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
