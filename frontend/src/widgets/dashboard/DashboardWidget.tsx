import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useMemo } from "react";

import { FilterBar } from "./FilterBar";
import { KpiCards } from "./KpiCards";
import { PerformanceHighlights } from "./PerformanceHighlights";
import { SentimentDonut } from "./SentimentDonut";
import { TopPerformingSection } from "./TopPerformingSection";
import { YourStore } from "./YourStore";
import { useFilterState } from "./useFilterState";
import type { DashboardBootstrap, Region, Shop } from "./types";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 5 * 60 * 1000, retry: 1, refetchOnWindowFocus: false },
  },
});

function readBootstrap(): DashboardBootstrap {
  const regionsEl = document.getElementById("dashboard-regions");
  const shopsEl = document.getElementById("dashboard-shops");
  const rootEl = document.getElementById("dashboard-root");
  const regions: Region[] = regionsEl ? JSON.parse(regionsEl.textContent ?? "[]") : [];
  const shops: Shop[] = shopsEl ? JSON.parse(shopsEl.textContent ?? "[]") : [];
  const isSingleShop = rootEl?.dataset.isSingleShop === "true";
  return { regions, shops, isSingleShop };
}

export function DashboardWidget() {
  return (
    <QueryClientProvider client={queryClient}>
      <DashboardInner />
    </QueryClientProvider>
  );
}

function DashboardInner() {
  const bootstrap = useMemo(readBootstrap, []);
  const fs = useFilterState();
  const fullFilters = fs.filters;
  const dateOnlyFilters = useMemo(
    () => ({
      range: fs.filters.range,
      date_from: fs.filters.date_from,
      date_to: fs.filters.date_to,
    }),
    [fs.filters.range, fs.filters.date_from, fs.filters.date_to],
  );

  const shopNameIfSingle =
    bootstrap.isSingleShop && bootstrap.shops.length === 1
      ? bootstrap.shops[0].name
      : null;

  return (
    <div className="flex flex-col gap-6">
      <FilterBar
        filters={fs.filters}
        regions={bootstrap.regions}
        shops={bootstrap.shops}
        onRegionChange={fs.setRegion}
        onStoreChange={fs.setStore}
        onRangeChange={fs.setDateRange}
        onCustomRange={fs.setCustomRange}
        onClear={fs.clearFilters}
      />

      <div className="grid grid-cols-1 xl:grid-cols-[1fr_320px] gap-6">
        <div className="flex flex-col gap-6">
          {bootstrap.isSingleShop ? (
            <YourStore dateOnlyFilters={dateOnlyFilters} />
          ) : (
            <TopPerformingSection
              dateOnlyFilters={dateOnlyFilters}
              onSelect90d={() => fs.setDateRange("90d")}
            />
          )}
        </div>
        <div className="flex flex-col gap-6">
          <KpiCards filters={fullFilters} shopNameIfSingle={shopNameIfSingle} />
          <SentimentDonut filters={fullFilters} />
          {!bootstrap.isSingleShop && (
            <PerformanceHighlights dateOnlyFilters={dateOnlyFilters} />
          )}
        </div>
      </div>
    </div>
  );
}
