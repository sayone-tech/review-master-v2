import { useQuery } from "@tanstack/react-query";

import { fetchSentiment } from "./api";
import type { DashboardFilters, SentimentResponse } from "./types";

export function useSentiment(filters: DashboardFilters) {
  return useQuery<SentimentResponse>({
    queryKey: ["dashboard", "sentiment", filters],
    queryFn: () => fetchSentiment(filters),
    staleTime: 5 * 60 * 1000,
    retry: 1,
  });
}
