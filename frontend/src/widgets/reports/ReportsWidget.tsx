import { useEffect, useState } from "react";
import { setHeaderCount } from "../../shell/header";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { FilterBar } from "./FilterBar";
import { ReportsTable } from "./ReportsTable";
import { useReportData } from "./useReportData";
import type { ReportFilters, SortDir, SortKey } from "./types";

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
  const [sortKey, setSortKey] = useState<SortKey>("total_reviews");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const { data, isLoading, error } = useReportData(filters);

  // Store count shown next to the page title in the header.
  const storeCount = data && !isLoading ? data.length : null;
  useEffect(() => {
    setHeaderCount(storeCount);
    return () => setHeaderCount(null);
  }, [storeCount]);

  function handleSort(key: SortKey) {
    if (key === sortKey) {
      setSortDir((d) => (d === "desc" ? "asc" : "desc"));
    } else {
      setSortKey(key);
      setSortDir("desc");
    }
  }

  return (
    <div className="space-y-4">
      <FilterBar
        filters={filters}
        onChange={setFilters}
        sortKey={sortKey}
        sortDir={sortDir}
        onSort={handleSort}
      />

      {error && (
        <div className="text-[13.5px] text-red-600 py-4">
          Failed to load report. Please try again.
        </div>
      )}

      <ReportsTable
        rows={data ?? []}
        loading={isLoading}
        sortKey={sortKey}
        sortDir={sortDir}
        onSort={handleSort}
      />
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
