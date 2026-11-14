import { PanelError, PULSE, RED, YELLOW } from "./Panel";
import { StarMeter } from "./StarMeter";
import type { DashboardFilters, HighlightShop } from "./types";
import { useHighlights } from "./useHighlights";

interface Props {
  dateOnlyFilters: Pick<DashboardFilters, "range" | "date_from" | "date_to">;
}

const CARD =
  "rounded-[12px] border border-[#262626] bg-[#1C1C1C] p-3.5 text-[#E4E4E7] flex flex-col min-w-0";

function Card({ badge, tone, shop }: { badge: string; tone: "good" | "bad"; shop: HighlightShop }) {
  const color = tone === "good" ? YELLOW : RED;
  return (
    <div role="group" aria-label={badge} className={CARD}>
      <span
        className="w-max rounded-[10px] px-2 py-0.5 text-[11px] font-semibold"
        style={{
          color,
          background: tone === "good" ? "rgba(250,204,21,.14)" : "rgba(248,113,113,.14)",
        }}
      >
        {badge}
      </span>
      <p className="mt-2 mb-1.5 truncate text-[15px] font-semibold text-white" title={shop.shop_name}>
        {shop.shop_name}
      </p>
      <span className="self-start">
        <StarMeter value={shop.avg_rating} size={14} />
      </span>
      <p className="mt-1.5 text-[12px] text-[#A1A1AA] tabular-nums">
        {shop.avg_rating.toFixed(1)}★ from {shop.review_count} reviews · {shop.positive_count} positive ·{" "}
        {shop.negative_count} negative
      </p>
    </div>
  );
}

export function PerformanceHighlights({ dateOnlyFilters }: Props) {
  const query = useHighlights(dateOnlyFilters);

  if (query.isLoading) {
    return (
      <div aria-label="Loading highlights" aria-busy="true" className="flex flex-col gap-2.5 lg:flex-1">
        <div className={`h-[112px] rounded-[12px] ${PULSE}`} />
        <div className={`h-[112px] rounded-[12px] ${PULSE}`} />
      </div>
    );
  }

  if (query.isError) {
    return (
      <div className="rounded-[12px] border border-[#262626] bg-[#141414] px-4 lg:flex-1">
        <PanelError
          message="Could not load highlights."
          onRetry={() => void query.refetch()}
          retryLabel="Retry loading performance highlights"
        />
      </div>
    );
  }

  const data = query.data;
  // Empty: the ladder's empty state covers this section.
  if (!data || data.top === null) return null;

  return (
    <div className="grid gap-2.5 sm:grid-cols-2 lg:flex-1 lg:grid-cols-1 lg:grid-rows-[1fr_1fr]">
      <Card badge="Top performer" tone="good" shop={data.top} />
      {data.bottom !== null && <Card badge="Needs attention" tone="bad" shop={data.bottom} />}
    </div>
  );
}
