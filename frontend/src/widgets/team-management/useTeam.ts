import { useCallback, useState } from "react";
import { listTeam } from "./api";
import type { TeamFilterParams, TeamListResponse, TeamMemberRow, TeamStats } from "./types";

interface UseTeamInitial {
  rows: TeamMemberRow[];
  stats: TeamStats;
}

export function useTeam(initial: UseTeamInitial) {
  const [rows, setRows] = useState<TeamMemberRow[]>(initial.rows);
  const [count, setCount] = useState<number>(initial.rows.length);
  const [loading, setLoading] = useState(false);
  const [stats, setStats] = useState<TeamStats>(initial.stats);
  const [filters, setFilters] = useState<TeamFilterParams>({});

  const refresh = useCallback(
    async (override?: TeamFilterParams): Promise<void> => {
      setLoading(true);
      try {
        const params = override ?? filters;
        const data: TeamListResponse = await listTeam(params);
        setRows(data.results);
        setCount(data.count);
      } finally {
        setLoading(false);
      }
    },
    [filters],
  );

  const setSearch = (search: string) => {
    const next = { ...filters, search, page: 1 };
    setFilters(next);
    void refresh(next);
  };

  const setRegion = (region_id: number | undefined) => {
    // Reset shop filter when region changes
    const next = { ...filters, region_id, shop_id: undefined, page: 1 };
    setFilters(next);
    void refresh(next);
  };

  const setShop = (shop_id: number | undefined) => {
    const next = { ...filters, shop_id, page: 1 };
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

  const refetch = useCallback(() => {
    void refresh(filters);
  }, [refresh, filters]);

  return {
    rows,
    count,
    loading,
    stats,
    filters,
    setSearch,
    setRegion,
    setShop,
    setPage,
    setPageSize,
    refetch,
    setStats,
  };
}
