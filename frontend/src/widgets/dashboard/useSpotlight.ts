import { useQuery } from "@tanstack/react-query";

import { fetchInsights } from "../insights/api";
import type { InsightsBookData } from "../insights/types";

/**
 * The latest Insights snapshot for the Spotlight strip. Brand-wide, so it is
 * fetched once and never keyed on the dashboard filters. `enabled` is false
 * for Staff: the endpoint is Org Admin only, so it is never called.
 */
export function useSpotlight(enabled: boolean) {
  return useQuery<InsightsBookData>({
    queryKey: ["dashboard", "spotlight"],
    queryFn: ({ signal }) => fetchInsights(signal),
    enabled,
    staleTime: 5 * 60 * 1000,
    // A failed strip is simply hidden; retrying only delays that.
    retry: false,
  });
}
