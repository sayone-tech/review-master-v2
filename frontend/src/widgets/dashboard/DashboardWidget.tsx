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

function readBootstrap(): DashboardBootstrap & { isOrgAdmin: boolean } {
  const regionsEl = document.getElementById("dashboard-regions");
  const shopsEl = document.getElementById("dashboard-shops");
  const rootEl = document.getElementById("dashboard-root");
  const regions: Region[] = regionsEl ? JSON.parse(regionsEl.textContent ?? "[]") : [];
  const shops: Shop[] = shopsEl ? JSON.parse(shopsEl.textContent ?? "[]") : [];
  const isSingleShop = rootEl?.dataset.isSingleShop === "true";
  const isOrgAdmin = rootEl?.dataset.isOrgAdmin === "true";
  return { regions, shops, isSingleShop, isOrgAdmin };
}

function NoStoresEmptyState({ isOrgAdmin }: { isOrgAdmin: boolean }) {
  return (
    <div className="flex flex-col items-center justify-center py-24 px-6 text-center">
      <div className="w-16 h-16 rounded-full bg-yellow/15 flex items-center justify-center mb-5">
        <svg className="w-8 h-8 text-yellow" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 21v-7.5a.75.75 0 0 1 .75-.75h3a.75.75 0 0 1 .75.75V21m-4.5 0H2.36m11.14 0H18m0 0h3.64m-1.39 0V9.349M3.75 21V9.349m0 0a3.001 3.001 0 0 0 3.75-.615A2.993 2.993 0 0 0 9.75 9.75c.896 0 1.7-.393 2.25-1.016a2.993 2.993 0 0 0 2.25 1.016c.896 0 1.7-.393 2.25-1.015a3.001 3.001 0 0 0 3.75.614m-16.5 0a3.004 3.004 0 0 1-.621-4.72l1.189-1.19A1.5 1.5 0 0 1 5.378 3h13.243a1.5 1.5 0 0 1 1.06.44l1.19 1.189a3 3 0 0 1-.621 4.72M6.75 18h3.75a.75.75 0 0 0 .75-.75V13.5a.75.75 0 0 0-.75-.75H6.75a.75.75 0 0 0-.75.75v3.75c0 .414.336.75.75.75Z" />
        </svg>
      </div>
      <h2 className="text-[18px] font-semibold text-ink mb-2">No stores connected yet</h2>
      {isOrgAdmin ? (
        <>
          <p className="text-[14px] text-subtle max-w-[360px] mb-6">
            Add your first store and connect it to Google Business Profile to start tracking reviews, sentiment, and performance across your locations.
          </p>
          <div className="flex flex-col sm:flex-row gap-3">
            <a
              href="/admin/org/shops/"
              className="inline-flex items-center justify-center gap-2 px-5 py-2.5 bg-yellow text-black text-[13.5px] font-semibold rounded-md hover:bg-yellow/90 transition-colors"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
              </svg>
              Add a store
            </a>
          </div>
          <p className="text-[12px] text-faint mt-5">
            Once a store is connected to Google Business Profile, reviews will sync automatically.
          </p>
        </>
      ) : (
        <>
          <p className="text-[14px] text-subtle max-w-[360px] mb-2">
            Your dashboard will appear here once your organisation admin adds and connects stores to Google Business Profile.
          </p>
          <p className="text-[12px] text-faint mt-2">
            Contact your organisation admin to get started.
          </p>
        </>
      )}
    </div>
  );
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

  if (bootstrap.shops.length === 0) {
    return <NoStoresEmptyState isOrgAdmin={bootstrap.isOrgAdmin} />;
  }

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
