import { useQuery } from "@tanstack/react-query";

import { fetchYourStore } from "./api";
import type { DashboardFilters, YourStoreResponse } from "./types";

export function useYourStore(
  filters: Pick<DashboardFilters, "range" | "date_from" | "date_to">,
  enabled: boolean,
) {
  return useQuery<YourStoreResponse>({
    queryKey: ["dashboard", "your-store", filters],
    queryFn: () => fetchYourStore(filters),
    staleTime: 5 * 60 * 1000,
    retry: 1,
    enabled,
  });
}
