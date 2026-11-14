import { GREY, Panel, PanelError, PULSE, RED, TIP, YELLOW } from "./Panel";
import { toHundred } from "./panelMath";
import { StarMeter } from "./StarMeter";
import type { DashboardFilters, YourStoreResponse } from "./types";
import { useYourStore } from "./useYourStore";

interface Props {
  dateOnlyFilters: Pick<DashboardFilters, "range" | "date_from" | "date_to">;
}

type StarKey = 1 | 2 | 3 | 4 | 5;
const STARS: StarKey[] = [5, 4, 3, 2, 1];
const BAR_MAX = 96; // px
// Edge bars open inward so the tooltip stays inside the panel.
const BAR_TIP = ["left-0", "left-0", "left-1/2 -translate-x-1/2", "right-0", "right-0"];
const STAR_COLOR: Record<StarKey, { bg: string; opacity: number }> = {
  5: { bg: YELLOW, opacity: 1 },
  4: { bg: YELLOW, opacity: 0.7 },
  3: { bg: GREY, opacity: 1 },
  2: { bg: RED, opacity: 1 },
  1: { bg: RED, opacity: 1 },
};

function TrendLine({
  direction,
  delta,
}: {
  direction: YourStoreResponse["trend_direction"];
  delta: number | null;
}) {
  if (direction === "none") return null;
  const text =
    direction === "flat"
      ? "No change vs previous period"
      : `${direction === "up" ? "+" : "−"}${Math.abs(delta ?? 0).toFixed(2)}★ vs previous period`;
  return (
    <p className="mt-1.5 text-[11.5px] font-medium text-[#A1A1AA] tabular-nums">
      {direction !== "flat" && (
        <span aria-hidden="true" className="mr-1 text-[9px]">
          {direction === "up" ? "▲" : "▼"}
        </span>
      )}
      {text}
    </p>
  );
}

function StarBars({ distribution }: { distribution: YourStoreResponse["distribution"] }) {
  const counts = STARS.map((k) => distribution[k]);
  const pcts = toHundred(counts);
  const max = Math.max(0, ...counts);
  return (
    <div className="grid grid-cols-5 items-end gap-2.5 sm:gap-4" style={{ height: BAR_MAX + 26 }}>
      {STARS.map((star, i) => {
        const count = counts[i];
        const h = max > 0 ? Math.max(count > 0 ? 3 : 2, (count / max) * BAR_MAX) : 2;
        const { bg, opacity } = STAR_COLOR[star];
        return (
          <div
            key={star}
            className="group relative flex flex-col items-stretch"
            aria-label={`${star} stars: ${count} reviews, ${pcts[i]}%`}
            role="img"
          >
            <span className={`${TIP} bottom-full mb-1 ${BAR_TIP[i]}`} aria-hidden="true">
              <strong className="text-[13px] text-white tabular-nums">{count}</strong> reviews at {star}★
            </span>
            <div data-testid="star-bar" data-star={star} className="flex flex-col items-stretch">
              <div
                className="mx-auto w-full max-w-[56px] rounded-t-[6px] rounded-b-[2px]"
                style={{ height: h, background: count > 0 ? bg : "#2A2A2A", opacity: count > 0 ? opacity : 1 }}
              />
              <div className="mt-1.5 text-center text-[12px] text-[#A1A1AA] tabular-nums">
                {star}★ {pcts[i]}%
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

export function YourStore({ dateOnlyFilters }: Props) {
  const query = useYourStore(dateOnlyFilters, true);

  if (query.isLoading) {
    return (
      <Panel className="lg:flex-1" title="Your store" busy>
        <div aria-label="Loading your store" className="flex flex-col gap-3">
          <div className={`h-5 w-32 rounded ${PULSE}`} />
          <div className={`h-8 w-24 rounded ${PULSE}`} />
          <div className="grid grid-cols-5 items-end gap-4" style={{ height: BAR_MAX }}>
            {[80, 40, 20, 12, 16].map((h, i) => (
              <div key={i} className={`rounded-t-[6px] ${PULSE}`} style={{ height: h }} />
            ))}
          </div>
        </div>
      </Panel>
    );
  }

  if (query.isError) {
    return (
      <Panel className="lg:flex-1" title="Your store">
        <PanelError onRetry={() => void query.refetch()} retryLabel="Retry loading Your Store" />
      </Panel>
    );
  }

  const data = query.data;
  if (!data) return null;

  return (
    <Panel className="lg:flex-1" title="Your store" subtitle="Star breakdown for this period">
      <div className="grid gap-5 md:grid-cols-[minmax(0,1fr)_minmax(0,1.6fr)] md:items-end">
        <div className="min-w-0">
          <p className="truncate text-[18px] font-semibold text-white" title={data.shop_name}>
            {data.shop_name}
          </p>
          {data.region_name && (
            <span className="mt-1 inline-flex rounded-full bg-[#1C1C1C] px-2 py-0.5 text-[11px] font-medium text-[#A1A1AA]">
              {data.region_name}
            </span>
          )}
          <div className="mt-3 flex flex-wrap items-baseline gap-x-2.5">
            <span className="text-[30px] font-bold leading-none tracking-[-0.02em] text-white tabular-nums">
              {data.avg_rating.toFixed(1)}
            </span>
            <StarMeter value={data.avg_rating} size={16} />
          </div>
          <TrendLine direction={data.trend_direction} delta={data.trend_delta} />
          <p className="mt-2 text-[12.5px] text-[#A1A1AA] tabular-nums">{data.total_reviews} reviews</p>
          <p className="text-[12.5px] text-[#A1A1AA] tabular-nums">
            <strong className="font-semibold text-[#FACC15]">{data.positive_count}</strong> positive (
            {data.positive_pct}%) ·{" "}
            <strong className="font-semibold text-[#F87171]">{data.negative_count}</strong> negative (
            {data.negative_pct}%)
          </p>
        </div>
        <StarBars distribution={data.distribution} />
      </div>
    </Panel>
  );
}
