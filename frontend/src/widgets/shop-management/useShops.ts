import { useCallback, useEffect, useState } from "react";
import { listShops } from "./api";
import { setShopCredits } from "../credits/creditsStore";
import type { AllocationStatus, ShopFilterParams, ShopRow } from "./types";

interface UseShopsInitial {
  rows: ShopRow[];
  allocation: AllocationStatus;
  hasRegions: boolean;
}

/**
 * Mirror every row that carries credit fields into the shop-keyed store so the
 * badge keeps its last known value when a later row arrives without them.
 */
function seedCredits(rows: ShopRow[]): void {
  for (const row of rows) {
    if (typeof row.credits_remaining === "number" && typeof row.credits_total === "number") {
      setShopCredits(row.id, {
        remaining: row.credits_remaining,
        total: row.credits_total,
        isEnabled: row.credits_total > 0,
      });
    }
  }
}

export function useShops(initial: UseShopsInitial) {
  const [rows, setRows] = useState<ShopRow[]>(initial.rows);
  const [count, setCount] = useState<number>(initial.rows.length);
  const [allocation, setAllocation] = useState<AllocationStatus>(initial.allocation);
  const [hasRegions, setHasRegions] = useState<boolean>(initial.hasRegions);
  const [loading, setLoading] = useState(false);
  const [filters, setFilters] = useState<ShopFilterParams>(() => {
    // Phase 7 locked decision: pre-populate region filter from ?region=<pk>
    if (typeof window === "undefined") return {};
    const region = new URLSearchParams(window.location.search).get("region");
    return region ? { region: Number(region) } : {};
  });

  const refresh = useCallback(
    async (override?: ShopFilterParams) => {
      setLoading(true);
      try {
        const params = override ?? filters;
        const data = await listShops(params);
        seedCredits(data.results);
        setRows(data.results);
        setCount(data.count);
        setAllocation(data.allocation_status);
        setHasRegions(data.has_regions);
      } finally {
        setLoading(false);
      }
    },
    [filters],
  );

  // Seed the store from the bootstrap rows once, before the first paint settles.
  useEffect(() => {
    seedCredits(initial.rows);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Run once on mount IF the URL had a region param (so the initial seeded data is replaced)
  useEffect(() => {
    if (filters.region !== undefined) {
      void refresh(filters);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const handler = () => void refresh();
    window.addEventListener("shop:refresh", handler);
    return () => window.removeEventListener("shop:refresh", handler);
  }, [refresh]);

  const setSearch = (search: string) => {
    const next = { ...filters, search, page: 1 };
    setFilters(next);
    void refresh(next);
  };

  const setStatus = (status: ShopFilterParams["status"]) => {
    const next = { ...filters, status, page: 1 };
    setFilters(next);
    void refresh(next);
  };

  const setRegion = (region: ShopFilterParams["region"]) => {
    const next = { ...filters, region, page: 1 };
    setFilters(next);
    void refresh(next);
  };

  const setPage = (page: number) => {
    const next = { ...filters, page };
    setFilters(next);
    void refresh(next);
  };

  const setPageSize = (page_size: number) => {
    const next = { ...filters, page_size, page: 1 };
    setFilters(next);
    void refresh(next);
  };

  return {
    rows,
    count,
    loading,
    allocation,
    hasRegions,
    filters,
    refresh,
    setSearch,
    setStatus,
    setRegion,
    setPage,
    setPageSize,
  };
}
