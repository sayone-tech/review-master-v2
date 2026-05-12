import { useQuery } from "@tanstack/react-query";

import { fetchStoreReport } from "./api";
import type { ReportFilters, StoreReportRow } from "./types";

export function useReportData(filters: ReportFilters) {
  return useQuery<StoreReportRow[]>({
    queryKey: ["reports", "stores", filters],
    queryFn: () => fetchStoreReport(filters),
    staleTime: 60 * 1000,
    retry: 1,
  });
}
