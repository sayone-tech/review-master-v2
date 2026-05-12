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
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-[20px] font-semibold text-ink">
          Reports{" "}
          {data && !isLoading && (
            <span className="text-[14px] text-muted font-normal">({data.length} stores)</span>
          )}
        </h1>
      </div>

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
