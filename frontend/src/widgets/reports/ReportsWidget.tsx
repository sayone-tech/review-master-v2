import { useEffect, useState } from "react";
import { setHeaderCount } from "../../shell/header";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { FilterBar } from "./FilterBar";
import { ReportsTable } from "./ReportsTable";
import { useReportData } from "./useReportData";
import type { ReportFilters } from "./types";

const qc = new QueryClient();

const DEFAULT_FILTERS: ReportFilters = {
  range: "30d",
  date_from: null,
  date_to: null,
  reply_status: "all",
  sentiment: "all",
};

function Inner() {
  const [filters, setFilters] = useState<ReportFilters>(DEFAULT_FILTERS);
  const { data, isLoading, error } = useReportData(filters);

  // Store count shown next to the page title in the header.
  const storeCount = data && !isLoading ? data.length : null;
  useEffect(() => {
    setHeaderCount(storeCount);
    return () => setHeaderCount(null);
  }, [storeCount]);

  return (
    <div className="space-y-4">
      <FilterBar filters={filters} onApply={setFilters} />

      {error && (
        <div className="text-[13.5px] text-red-600 py-4">
          Failed to load report. Please try again.
        </div>
      )}

      <ReportsTable rows={data ?? []} loading={isLoading} />
    </div>
  );
}

export function ReportsWidget() {
  return (
    <QueryClientProvider client={qc}>
      <Inner />
    </QueryClientProvider>
  );
}
