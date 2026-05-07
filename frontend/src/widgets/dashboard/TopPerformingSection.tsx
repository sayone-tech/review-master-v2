import { BarChart2 } from "lucide-react";
import {
  Bar,
  BarChart,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { PerformanceHighlights } from "./PerformanceHighlights";
import type { DashboardFilters, TopPerformingShop } from "./types";
import { useTopPerforming } from "./useTopPerforming";

interface Props {
  dateOnlyFilters: Pick<DashboardFilters, "range" | "date_from" | "date_to">;
  onSelect90d: () => void;
}

function barColor(rating: number): string {
  if (rating >= 4.0) return "#22C55E";
  if (rating >= 3.0) return "#F59E0B";
  return "#EF4444";
}

function buildReviewsUrl(
  shopId: number,
  from: string | null,
  to: string | null,
): string {
  const p = new URLSearchParams();
  p.set("store", String(shopId));
  if (from) p.set("from", from);
  if (to) p.set("to", to);
  return `/admin/org/reviews/?${p.toString()}`;
}

function truncate(name: string, maxLen: number): string {
  return name.length > maxLen ? name.slice(0, maxLen) + "…" : name;
}

interface SeparatorBar extends TopPerformingShop {
  _separator: true;
}

type ChartBar = TopPerformingShop | SeparatorBar;

function isSeparator(bar: ChartBar): bar is SeparatorBar {
  return "_separator" in bar && bar._separator === true;
}

interface CustomTooltipProps {
  active?: boolean;
  payload?: Array<{ payload: ChartBar }>;
}

function CustomTooltip({ active, payload }: CustomTooltipProps) {
  if (!active || !payload || payload.length === 0) return null;
  const bar = payload[0].payload;
  if (isSeparator(bar)) return null;
  return (
    <div className="bg-white border border-line rounded-md shadow p-2">
      <p className="text-[14px] font-bold text-ink">{bar.shop_name}</p>
      <p className="text-[14px] text-text">Avg: {bar.avg_rating.toFixed(2)}</p>
      <p className="text-[14px] text-muted">{bar.review_count} reviews</p>
    </div>
  );
}

export function TopPerformingSection({ dateOnlyFilters, onSelect90d }: Props) {
  const query = useTopPerforming(dateOnlyFilters);

  if (query.isLoading) {
    return (
      <section className="bg-white border border-line rounded-card p-4">
        <div className="bg-line-soft rounded-card animate-[sk-pulse_1.6s_ease-in-out_infinite] h-[280px]" />
      </section>
    );
  }

  if (query.isError) {
    return (
      <section className="bg-white border border-line rounded-card p-4">
        <div className="text-[14px] text-muted">
          Could not load.{" "}
          <button
            onClick={() => void query.refetch()}
            className="text-[14px] font-semibold text-ink underline"
            aria-label="Retry loading best performing outlets"
          >
            Retry
          </button>
        </div>
      </section>
    );
  }

  const response = query.data;

  // Empty state
  if (!response || response.shops.length === 0) {
    return (
      <section className="bg-white border border-line rounded-card p-4">
        <div className="text-center py-12">
          <BarChart2
            className="size-8 text-faint mx-auto mb-3"
            aria-hidden="true"
          />
          <h3 className="text-[20px] font-bold text-ink">
            No qualifying stores in this period
          </h3>
          <p className="text-[14px] text-muted mt-2">
            Stores need at least 3 reviews in the selected period to appear
            here.
          </p>
          <button
            onClick={onSelect90d}
            className="mt-4 inline-flex items-center gap-2 px-4 py-2 bg-black text-yellow text-[14px] font-bold rounded-md"
          >
            View last 90 days
          </button>
        </div>
      </section>
    );
  }

  // Build chart data with optional separator between top 5 and worst 5
  let chartData: ChartBar[];
  if (response.split && response.shops.length > 5) {
    const top5 = response.shops.slice(0, 5);
    const worst5 = response.shops.slice(5);
    const separator: SeparatorBar = {
      shop_id: -1,
      shop_name: "…",
      review_count: 0,
      avg_rating: 0,
      _separator: true,
    };
    chartData = [...top5, separator, ...worst5];
  } else {
    chartData = response.shops;
  }

  return (
    <>
      <section className="bg-white border border-line rounded-card p-4">
        <h2 className="text-[20px] font-bold text-ink mb-1">
          Best Performing Outlets
        </h2>
        <p className="text-[14px] text-subtle mb-4">(date range only)</p>

        <div role="img" aria-label="Best performing outlets bar chart">
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={chartData}>
              <XAxis
                dataKey="shop_name"
                tick={{ fontSize: 11 }}
                interval={0}
                tickFormatter={(name: string) => truncate(name, 16)}
              />
              <YAxis domain={[0, 5]} ticks={[1, 2, 3, 4, 5]} tick={{ fontSize: 11 }} />
              <Tooltip content={<CustomTooltip />} />
              <Bar
                dataKey="avg_rating"
                radius={[4, 4, 0, 0]}
                cursor="pointer"
                onClick={(data) => {
                  const bar = data as unknown as ChartBar;
                  if (!isSeparator(bar)) {
                    window.location.href = buildReviewsUrl(
                      bar.shop_id,
                      dateOnlyFilters.date_from,
                      dateOnlyFilters.date_to,
                    );
                  }
                }}
              >
                {chartData.map((bar) => {
                  if (isSeparator(bar)) {
                    return (
                      <Cell
                        key="separator"
                        fill="transparent"
                        style={{ cursor: "default" }}
                      />
                    );
                  }
                  return (
                    <Cell
                      key={bar.shop_id}
                      fill={barColor(bar.avg_rating)}
                    />
                  );
                })}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </section>

      <PerformanceHighlights dateOnlyFilters={dateOnlyFilters} />
    </>
  );
}
