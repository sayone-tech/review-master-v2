import { useQuery } from "@tanstack/react-query";

import { fetchTopPerforming } from "./api";
import type { DashboardFilters, TopPerformingResponse } from "./types";

export function useTopPerforming(
  filters: Pick<DashboardFilters, "range" | "date_from" | "date_to">,
) {
  return useQuery<TopPerformingResponse>({
    queryKey: ["dashboard", "top-performing", filters],
    queryFn: () => fetchTopPerforming(filters),
    staleTime: 5 * 60 * 1000,
    retry: 1,
  });
}
