// Standard pagination footer (mirrors review-management / audit-log): "Showing X–Y of N",
// rows-per-page select, previous/next chevrons and numbered page buttons.

import { ChevronDown, ChevronLeft, ChevronRight } from "lucide-react";
import { PAGE_SIZES } from "./types";

export function buildPageRange(current: number, total: number): (number | "…")[] {
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1);
  if (current <= 4) return [1, 2, 3, 4, 5, "…", total];
  if (current >= total - 3) return [1, "…", total - 4, total - 3, total - 2, total - 1, total];
  return [1, "…", current - 1, current, current + 1, "…", total];
}

const navBtnCls =
  "w-[30px] h-[30px] rounded-sm bg-white border border-line text-[13px] font-medium flex items-center justify-center disabled:opacity-40 disabled:cursor-not-allowed enabled:hover:bg-line-soft";

interface Props {
  page: number;
  pageSize: number;
  count: number;
  onPage: (page: number) => void;
  onPageSize: (pageSize: number) => void;
}

export function Pagination({ page, pageSize, count, onPage, onPageSize }: Props) {
  const totalPages = Math.max(1, Math.ceil(count / pageSize));
  const showingFrom = count === 0 ? 0 : (page - 1) * pageSize + 1;
  const showingTo = count === 0 ? 0 : Math.min(page * pageSize, count);

  return (
    <nav
      className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 border-t border-line bg-[#FBFBFB] text-[13px] text-muted"
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
          <label htmlFor="ai-cost-rows-per-page" className="text-[12px] text-muted">
            Rows:
          </label>
          <div className="inline-flex items-center bg-white border border-line rounded-sm focus-within:border-ink">
            <select
              id="ai-cost-rows-per-page"
              className="appearance-none pl-2 pr-1 py-1 text-[12.5px] bg-transparent focus:outline-none cursor-pointer"
              value={pageSize}
              onChange={(e) => onPageSize(Number(e.target.value))}
              aria-label="Rows per page"
            >
              {PAGE_SIZES.map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
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
          onClick={() => onPage(page - 1)}
          disabled={page <= 1}
          className={navBtnCls}
          aria-label="Previous page"
        >
          <ChevronLeft className="w-3.5 h-3.5" aria-hidden="true" />
        </button>
        {buildPageRange(page, totalPages).map((p, i) =>
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
              onClick={() => onPage(p)}
              aria-current={p === page ? "page" : undefined}
              className={`w-[30px] h-[30px] rounded-sm text-[13px] font-medium flex items-center justify-center border ${
                p === page
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
          onClick={() => onPage(page + 1)}
          disabled={page >= totalPages}
          className={navBtnCls}
          aria-label="Next page"
        >
          <ChevronRight className="w-3.5 h-3.5" aria-hidden="true" />
        </button>
      </div>
    </nav>
  );
}
