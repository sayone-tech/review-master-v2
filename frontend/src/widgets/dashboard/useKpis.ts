import { useQuery } from "@tanstack/react-query";

import { fetchKpis } from "./api";
import type { DashboardFilters, KpisResponse } from "./types";

export function useKpis(filters: DashboardFilters) {
  return useQuery<KpisResponse>({
    queryKey: ["dashboard", "kpis", filters],
    queryFn: () => fetchKpis(filters),
    staleTime: 5 * 60 * 1000,
    retry: 1,
  });
}
