import { useQuery } from "@tanstack/react-query";

import { fetchHighlights } from "./api";
import type { DashboardFilters, HighlightsResponse } from "./types";

export function useHighlights(
  filters: Pick<DashboardFilters, "range" | "date_from" | "date_to">,
) {
  return useQuery<HighlightsResponse>({
    queryKey: ["dashboard", "highlights", filters],
    queryFn: () => fetchHighlights(filters),
    staleTime: 5 * 60 * 1000,
    retry: 1,
  });
}
