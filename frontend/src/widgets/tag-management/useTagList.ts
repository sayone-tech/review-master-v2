// Phase 25-03 — Hook for fetching and managing the canonical tag list.
// Phase 26-02 — Added search state + setSearch (TMGT-07).

import { useCallback, useEffect, useState } from "react";
import { fetchTags } from "./api";
import type { OrgCanonicalTagRow } from "./types";

export type TagOrdering =
  | "label"
  | "-label"
  | "review_count"
  | "-review_count"
  | "created_at"
  | "-created_at";

export function useTagList() {
  const [rows, setRows] = useState<OrgCanonicalTagRow[]>([]);
  const [count, setCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [ordering, setOrderingState] = useState<TagOrdering>("-review_count");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [search, setSearchState] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchTags({ ordering, page, page_size: pageSize, search });
      setRows(data.results);
      setCount(data.count);
    } catch {
      setError("Could not load tags");
    } finally {
      setLoading(false);
    }
  }, [ordering, page, pageSize, search]);

  const setSearch = (s: string) => {
    setSearchState(s);
    setPage(1);
  };

  useEffect(() => {
    void load();
  }, [load]);

  const setOrdering = (col: TagOrdering) => {
    // Toggle direction if re-clicking the active column
    if (col === ordering || `-${col}` === ordering || col === `-${ordering.replace(/^-/, "")}`) {
      // The column is already active — toggle direction
      setOrderingState(ordering.startsWith("-") ? (ordering.slice(1) as TagOrdering) : (`-${ordering}` as TagOrdering));
    } else {
      setOrderingState(col);
    }
    setPage(1);
  };

  const toggleOrdering = (baseCol: "label" | "review_count" | "created_at") => {
    const current = ordering;
    const isAsc = current === baseCol;
    const isDesc = current === `-${baseCol}`;
    if (isDesc) {
      // Was descending → switch to ascending
      setOrderingState(baseCol as TagOrdering);
    } else if (isAsc) {
      // Was ascending → switch to descending
      setOrderingState(`-${baseCol}` as TagOrdering);
    } else {
      // Not the active column — default to descending for review_count, ascending for others
      setOrderingState(baseCol === "review_count" ? `-${baseCol}` as TagOrdering : baseCol as TagOrdering);
    }
    setPage(1);
  };

  const totalPages = Math.max(1, Math.ceil(count / pageSize));
  const hasNext = page < totalPages;
  const hasPrev = page > 1;

  const goNext = () => { if (hasNext) setPage((p) => p + 1); };
  const goPrev = () => { if (hasPrev) setPage((p) => p - 1); };
  const changePageSize = (size: number) => { setPageSize(size); setPage(1); };

  return {
    rows,
    count,
    loading,
    error,
    ordering,
    page,
    pageSize,
    search,
    totalPages,
    hasNext,
    hasPrev,
    goNext,
    goPrev,
    setOrdering,
    toggleOrdering,
    changePageSize,
    setSearch,
    refetch: load,
  };
}
