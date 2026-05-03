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
  page: 1,
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
      } catch {
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
      updateFilter({ ...filters, search, page: 1 });
    }, 300);
  };

  const setShop = (shop?: number) => updateFilter({ ...filters, shop, page: 1 });
  const setRating = (rating?: 1 | 2 | 3 | 4 | 5) =>
    updateFilter({ ...filters, rating, page: 1 });
  const setSentiment = (sentiment?: "positive" | "neutral" | "negative") =>
    updateFilter({ ...filters, sentiment, page: 1 });
  const setIsReplied = (is_replied?: boolean) =>
    updateFilter({ ...filters, is_replied, page: 1 });
  const setFromDate = (from_date?: string) =>
    updateFilter({ ...filters, from_date, page: 1 });
  const setToDate = (to_date?: string) =>
    updateFilter({ ...filters, to_date, page: 1 });
  const setOrdering = (ordering: SortKey) =>
    updateFilter({ ...filters, ordering, page: 1 });
  const setPageSize = (page_size: 10 | 25 | 50 | 100) =>
    updateFilter({ ...filters, page_size, page: 1 });
  const goToPage = (page: number) =>
    updateFilter({ ...filters, page });
  const goNext = () => {
    if (next) goToPage((filters.page ?? 1) + 1);
  };
  const goPrev = () => {
    const cur = filters.page ?? 1;
    if (cur > 1) goToPage(cur - 1);
  };

  const applyFilters = (draft: Partial<ReviewFilterParams>) => {
    updateFilter({ ...DEFAULT_PARAMS, ...draft, page: 1 });
  };

  const clearFilters = () => {
    const reset = { ...DEFAULT_PARAMS };
    setFilters(reset);
    void refresh(reset);
  };

  const replaceRow = (row: ReviewRow) => {
    setRows((prev) => prev.map((r) => (r.id === row.id ? row : r)));
  };

  const currentPage = filters.page ?? 1;
  const pageSize = filters.page_size ?? 10;
  const totalPages = count > 0 ? Math.ceil(count / pageSize) : 1;

  return {
    rows,
    count,
    next,
    previous,
    loading,
    filters,
    currentPage,
    totalPages,
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
    goToPage,
    goNext,
    goPrev,
    applyFilters,
    clearFilters,
    replaceRow,
  };
}
