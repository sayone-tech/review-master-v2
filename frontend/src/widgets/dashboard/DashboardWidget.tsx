import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useMemo } from "react";

import { FilterBar } from "./FilterBar";
import { KpiCards } from "./KpiCards";
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

function StarIcon({ filled }: { filled: boolean }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill={filled ? "currentColor" : "none"}
      stroke="currentColor"
      strokeWidth={1.5}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={`w-[13px] h-[13px] ${filled ? "text-yellow" : "text-line"}`}
    >
      <path d="M11.48 3.499a.562.562 0 0 1 1.04 0l2.125 5.111a.563.563 0 0 0 .475.345l5.518.442c.499.04.701.663.321.988l-4.204 3.602a.563.563 0 0 0-.182.557l1.285 5.385a.562.562 0 0 1-.84.61l-4.725-2.885a.562.562 0 0 0-.586 0L6.982 20.54a.562.562 0 0 1-.84-.61l1.285-5.386a.562.562 0 0 0-.182-.557l-4.204-3.602a.562.562 0 0 1 .321-.988l5.518-.442a.563.563 0 0 0 .475-.345L11.48 3.5z" />
    </svg>
  );
}

function NoStoresEmptyState({ isOrgAdmin }: { isOrgAdmin: boolean }) {
  return (
    <div>
      {/* Page welcome header */}
      <div className="mb-5">
        <h1 className="text-[26px] font-semibold text-ink tracking-tight leading-tight mb-1">
          Welcome to Review Master
        </h1>
        <p className="text-[14px] text-muted">
          Connect your first store to start tracking reviews, sentiment, and performance across locations.
        </p>
      </div>

      {/* Main empty-state card */}
      <div
        className="bg-white border border-line text-center relative overflow-hidden"
        style={{ padding: "48px 40px 40px", borderRadius: "16px" }}
      >
        {/* Yellow radial glow at top */}
        <div
          aria-hidden="true"
          className="absolute inset-x-0 top-0 pointer-events-none"
          style={{
            height: 180,
            background:
              "radial-gradient(ellipse 60% 100% at 50% 0%, rgba(250,204,21,0.10), transparent 70%)",
          }}
        />

        {/* Store icon */}
        <div
          className="relative inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-yellow text-black mb-[18px]"
          style={{ boxShadow: "0 8px 24px rgba(250,204,21,0.35)" }}
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.7} className="w-7 h-7">
            <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 21v-7.5a.75.75 0 0 1 .75-.75h3a.75.75 0 0 1 .75.75V21m-4.5 0H2.36m11.14 0H18m0 0h3.64m-1.39 0V9.349M3.75 21V9.349m0 0a3.001 3.001 0 0 0 3.75-.615A2.993 2.993 0 0 0 9.75 9.75c.896 0 1.7-.393 2.25-1.016a2.993 2.993 0 0 0 2.25 1.016c.896 0 1.7-.393 2.25-1.015a3.001 3.001 0 0 0 3.75.614m-16.5 0a3.004 3.004 0 0 1-.621-4.72l1.189-1.19A1.5 1.5 0 0 1 5.378 3h13.243a1.5 1.5 0 0 1 1.06.44l1.19 1.189a3 3 0 0 1-.621 4.72M6.75 18h3.75a.75.75 0 0 0 .75-.75V13.5a.75.75 0 0 0-.75-.75H6.75a.75.75 0 0 0-.75.75v3.75c0 .414.336.75.75.75Z" />
          </svg>
        </div>

        <h2 className="relative text-[22px] font-semibold text-ink tracking-tight mb-2">
          {isOrgAdmin ? "Let's connect your first store" : "No stores connected yet"}
        </h2>

        <p className="relative text-[14px] text-muted max-w-[460px] mx-auto leading-[1.55] mb-6">
          {isOrgAdmin
            ? "Link a store to your Google Business Profile and we'll automatically sync reviews, surface sentiment, and help you reply faster — all from one place."
            : "Your dashboard will appear here once your organisation admin adds and connects stores to Google Business Profile."}
        </p>

        {isOrgAdmin ? (
          <div className="relative inline-flex flex-col items-center" style={{ gap: 10 }}>
            <a
              href="/admin/org/shops/"
              className="inline-flex items-center gap-1.5 px-3.5 py-2 bg-yellow text-black border border-yellow-hover rounded-md text-[13.5px] font-semibold hover:bg-yellow-hover"
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="w-4 h-4">
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
              </svg>
              Add a store
            </a>
            <span className="inline-flex items-center gap-1.5 text-[12.5px] text-subtle">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="w-3.5 h-3.5 text-green flex-shrink-0">
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75 11.25 15 15 9.75M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0z" />
              </svg>
              Reviews sync automatically once connected · usually under a minute
            </span>
          </div>
        ) : (
          <div className="relative inline-flex items-center gap-1.5 text-[13px] text-subtle px-4 py-2.5 bg-line-soft rounded-lg">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="w-4 h-4 text-muted flex-shrink-0">
              <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 6a3.75 3.75 0 1 1-7.5 0 3.75 3.75 0 0 1 7.5 0zM4.501 20.118a7.5 7.5 0 0 1 14.998 0A17.933 17.933 0 0 1 12 21.75c-2.676 0-5.216-.584-7.499-1.632z" />
            </svg>
            Contact your organisation admin to get started
          </div>
        )}

        {/* Preview strip — shown only for org admin */}
        {isOrgAdmin && (
          <div style={{ marginTop: 36, paddingTop: 28, borderTop: "1px dashed #E4E4E7" }} className="relative">
            <p className="text-[11.5px] font-medium text-subtle uppercase tracking-[0.08em]" style={{ marginBottom: 16 }}>
              What you'll see once connected
            </p>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12, textAlign: "left" }}>
              {/* Card 1 — Average rating */}
              <div className="bg-[#FBFBFA] border border-line rounded-card p-4">
                <div className="w-[30px] h-[30px] rounded-md bg-white border border-line inline-flex items-center justify-center mb-2.5">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} className="w-[15px] h-[15px] text-ink">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M11.48 3.499a.562.562 0 0 1 1.04 0l2.125 5.111a.563.563 0 0 0 .475.345l5.518.442c.499.04.701.663.321.988l-4.204 3.602a.563.563 0 0 0-.182.557l1.285 5.385a.562.562 0 0 1-.84.61l-4.725-2.885a.562.562 0 0 0-.586 0L6.982 20.54a.562.562 0 0 1-.84-.61l1.285-5.386a.562.562 0 0 0-.182-.557l-4.204-3.602a.562.562 0 0 1 .321-.988l5.518-.442a.563.563 0 0 0 .475-.345L11.48 3.5z" />
                  </svg>
                </div>
                <div className="text-[13px] font-semibold text-ink mb-1">Average rating & volume</div>
                <div className="text-[12px] text-subtle leading-[1.45] mb-2.5">At-a-glance KPIs across every connected store.</div>
                <div className="flex items-baseline gap-2.5">
                  <span className="text-[22px] font-semibold text-ink tracking-tight leading-none">4.6</span>
                  <span className="inline-flex gap-0.5">
                    {[1, 2, 3, 4, 5].map((i) => <StarIcon key={i} filled={i <= 5} />)}
                  </span>
                </div>
                <div className="text-[12px] text-subtle mt-1">+12 reviews this week</div>
              </div>

              {/* Card 2 — Sentiment trend */}
              <div className="bg-[#FBFBFA] border border-line rounded-card p-4">
                <div className="w-[30px] h-[30px] rounded-md bg-white border border-line inline-flex items-center justify-center mb-2.5">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} className="w-[15px] h-[15px] text-ink">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M7.5 8.25h9m-9 3H12m-9.75 1.51c0 1.6 1.123 2.994 2.707 3.227 1.129.166 2.27.293 3.423.379.35.026.67.21.865.501L12 21l2.755-4.133a1.14 1.14 0 0 1 .865-.501 48.172 48.172 0 0 0 3.423-.379c1.584-.233 2.707-1.626 2.707-3.228V6.741c0-1.602-1.123-2.995-2.707-3.228A48.394 48.394 0 0 0 12 3c-2.392 0-4.744.175-7.043.513C3.373 3.746 2.25 5.14 2.25 6.741v6.018z" />
                  </svg>
                </div>
                <div className="text-[13px] font-semibold text-ink mb-1">Sentiment trend</div>
                <div className="text-[12px] text-subtle leading-[1.45] mb-2.5">Track positive · neutral · negative over time.</div>
                {/* Mini sparkline */}
                <div
                  className="h-8 rounded mb-2.5 relative"
                  style={{
                    background: "linear-gradient(180deg, rgba(250,204,21,0.18), rgba(250,204,21,0) 80%)",
                  }}
                >
                  <div
                    className="absolute inset-x-0 bottom-0"
                    style={{
                      height: 1.5,
                      background: "#EAB308",
                      clipPath: "polygon(0 80%, 12% 60%, 24% 70%, 36% 40%, 48% 50%, 60% 30%, 72% 35%, 84% 18%, 100% 22%, 100% 100%, 0 100%)",
                    }}
                  />
                </div>
                {[
                  { label: "Positive", color: "text-[#166534]", fill: "bg-green", pct: "71%" },
                  { label: "Neutral", color: "text-subtle", fill: "bg-faint", pct: "21%" },
                  { label: "Negative", color: "text-[#991B1B]", fill: "bg-red", pct: "8%" },
                ].map(({ label, color, fill, pct }) => (
                  <div key={label} className="flex items-center gap-2 text-[11.5px] text-subtle mb-1 last:mb-0">
                    <span className={`w-[54px] shrink-0 ${color}`}>{label}</span>
                    <div className="flex-1 h-1.5 rounded-full bg-line-soft overflow-hidden">
                      <div className={`h-full rounded-full ${fill}`} style={{ width: pct }} />
                    </div>
                    <span>{pct}</span>
                  </div>
                ))}
              </div>

              {/* Card 3 — Reply faster */}
              <div className="bg-[#FBFBFA] border border-line rounded-card p-4">
                <div className="w-[30px] h-[30px] rounded-md bg-white border border-line inline-flex items-center justify-center mb-2.5">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} className="w-[15px] h-[15px] text-ink">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M8.625 12a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0zm0 0H8.25m4.125 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0zm0 0H12m4.125 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 0 1-2.555-.337A5.972 5.972 0 0 1 5.41 20.97a5.969 5.969 0 0 1-.474-.065 4.48 4.48 0 0 0 .978-2.025c.09-.457-.133-.901-.467-1.226C3.93 16.178 3 14.189 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25z" />
                  </svg>
                </div>
                <div className="text-[13px] font-semibold text-ink mb-1">Reply faster</div>
                <div className="text-[12px] text-subtle leading-[1.45] mb-2.5">See what's awaiting a response and reply inline.</div>
                <div className="flex flex-col gap-1.5 mb-1.5">
                  <div className="h-1.5 rounded-full bg-line w-3/4" />
                  <div className="h-1.5 rounded-full bg-line w-[55%]" />
                </div>
                <div className="flex items-center gap-1.5 text-[11.5px] text-subtle">
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-amber-tint text-[#92400E] text-[11px] font-medium">
                    <span className="w-1.5 h-1.5 rounded-full bg-amber inline-block" />
                    42 awaiting
                  </span>
                  <span className="text-faint">·</span>
                  <span>median 4h</span>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
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
    <div>
      <FilterBar
        filters={fs.filters}
        regions={bootstrap.regions}
        shops={bootstrap.shops}
        onApply={fs.applyAll}
        onClear={fs.clearFilters}
      />

      {/* KPI strip — 4 tiles across full width */}
      <KpiCards filters={fullFilters} shopNameIfSingle={shopNameIfSingle} />

      {/* Main two-column grid */}
      <div style={{ display: "grid", gridTemplateColumns: "minmax(0,1.7fr) minmax(0,1fr)", gap: 16, alignItems: "start" }}>
        {bootstrap.isSingleShop ? (
          <YourStore dateOnlyFilters={dateOnlyFilters} />
        ) : (
          <TopPerformingSection
            dateOnlyFilters={dateOnlyFilters}
            onSelect90d={() => fs.setDateRange("90d")}
          />
        )}
        <SentimentDonut filters={fullFilters} />
      </div>
    </div>
  );
}
