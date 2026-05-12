import { useState } from "react";
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

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-[22px] font-semibold text-ink">Reports</h1>
          <p className="text-[13.5px] text-muted mt-0.5">Store review performance summary</p>
        </div>
      </div>

      <FilterBar filters={filters} onApply={setFilters} />

      {isLoading && (
        <div className="space-y-2">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-12 bg-line-soft rounded animate-pulse" />
          ))}
        </div>
      )}

      {error && (
        <div className="text-[13.5px] text-red-600 py-4">
          Failed to load report. Please try again.
        </div>
      )}

      {data && !isLoading && <ReportsTable rows={data} />}
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
