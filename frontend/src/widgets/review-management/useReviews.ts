import { useCallback, useEffect, useRef, useState } from "react";
import { listReviews } from "./api";
import type { ReviewFilterParams, ReviewListResponse, ReviewRow, SortKey } from "./types";

interface UseReviewsState {
  rows: ReviewRow[];
  count: number;
  next: string | null;
  previous: string | null;
  loading: boolean;
}

const DEFAULT_PARAMS: ReviewFilterParams = {
  ordering: "-review_create_time",
  page_size: 10,
};

export function useReviews(initial?: Partial<UseReviewsState>) {
  const [rows, setRows] = useState<ReviewRow[]>(initial?.rows ?? []);
  const [count, setCount] = useState<number>(initial?.count ?? 0);
  const [next, setNext] = useState<string | null>(initial?.next ?? null);
  const [previous, setPrevious] = useState<string | null>(initial?.previous ?? null);
  const [loading, setLoading] = useState<boolean>(true);
  const [filters, setFilters] = useState<ReviewFilterParams>(DEFAULT_PARAMS);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const refresh = useCallback(
    async (override?: ReviewFilterParams) => {
      setLoading(true);
      try {
        const params = override ?? filters;
        const data: ReviewListResponse = await listReviews(params);
        setRows(data.results);
        setCount(data.total_count);
        setNext(data.next ?? null);
        setPrevious(data.previous ?? null);
      } catch (e) {
        // Surface errors silently to keep state consistent; UI shows empty + count=0.
        setRows([]);
        setCount(0);
        setNext(null);
        setPrevious(null);
      } finally {
        setLoading(false);
      }
    },
    [filters],
  );

  // Initial load
  useEffect(() => {
    void refresh(DEFAULT_PARAMS);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const updateFilter = (next: ReviewFilterParams) => {
    setFilters(next);
    void refresh(next);
  };

  const setSearch = (search: string) => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      const next = { ...filters, search, cursor: undefined };
      updateFilter(next);
    }, 300);
  };

  const setShop = (shop?: number) => updateFilter({ ...filters, shop, cursor: undefined });
  const setRating = (rating?: 1 | 2 | 3 | 4 | 5) =>
    updateFilter({ ...filters, rating, cursor: undefined });
  const setSentiment = (sentiment?: "positive" | "neutral" | "negative") =>
    updateFilter({ ...filters, sentiment, cursor: undefined });
  const setIsReplied = (is_replied?: boolean) =>
    updateFilter({ ...filters, is_replied, cursor: undefined });
  const setFromDate = (from_date?: string) =>
    updateFilter({ ...filters, from_date, cursor: undefined });
  const setToDate = (to_date?: string) =>
    updateFilter({ ...filters, to_date, cursor: undefined });
  const setOrdering = (ordering: SortKey) =>
    updateFilter({ ...filters, ordering, cursor: undefined });
  const setPageSize = (page_size: 10 | 25 | 50 | 100) =>
    updateFilter({ ...filters, page_size, cursor: undefined });
  const goNext = () => {
    if (next) updateFilter({ ...filters, cursor: extractCursor(next) });
  };
  const goPrev = () => {
    if (previous) updateFilter({ ...filters, cursor: extractCursor(previous) });
  };

  const clearFilters = () => {
    const reset = { ...DEFAULT_PARAMS };
    setFilters(reset);
    void refresh(reset);
  };

  const replaceRow = (row: ReviewRow) => {
    setRows((prev) => prev.map((r) => (r.id === row.id ? row : r)));
  };

  return {
    rows,
    count,
    next,
    previous,
    loading,
    filters,
    refresh,
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
  };
}

function extractCursor(url: string | null): string | undefined {
  if (!url) return undefined;
  try {
    return new URL(url, window.location.origin).searchParams.get("cursor") ?? undefined;
  } catch {
    return undefined;
  }
}
