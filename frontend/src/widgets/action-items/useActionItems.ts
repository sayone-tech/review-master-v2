import { useCallback, useEffect, useRef, useState } from "react";
import { listActionItems } from "./api";
import type { ListParams, PaginatedActionItems } from "./types";

interface UseActionItemsInit {
  reviewParam?: string;
}

export function useActionItems(initial: UseActionItemsInit) {
  const DEFAULT_PARAMS: ListParams = {
    page: 1,
    page_size: 25,
    ordering: "-created_at",
    review: initial.reviewParam ? Number(initial.reviewParam) : undefined,
  };
  const [params, setParams] = useState<ListParams>(DEFAULT_PARAMS);
  const [data, setData] = useState<PaginatedActionItems | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [searchInput, setSearchInput] = useState<string>(params.search ?? "");
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const refetch = useCallback(async () => {
    setLoading(true);
    try {
      const result = await listActionItems(params);
      setData(result);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load action items");
    } finally {
      setLoading(false);
    }
  }, [params]);

  // Debounce the search input by 300ms; immediate for everything else.
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      setParams((p) => {
        const nextSearch = searchInput || undefined;
        if (p.search === nextSearch) return p;
        return { ...p, search: nextSearch, page: 1 };
      });
    }, 300);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchInput]);

  useEffect(() => {
    void refetch();
  }, [refetch]);

  return {
    data,
    loading,
    error,
    params,
    setParams,
    searchInput,
    setSearchInput,
    refetch,
  };
}
