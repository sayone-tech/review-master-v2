import { AlertTriangle, BarChart2, CheckCircle } from "lucide-react";
import {
  Bar,
  BarChart,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { DashboardFilters, HighlightShop, TopPerformingShop } from "./types";
import { useHighlights } from "./useHighlights";
import { useTopPerforming } from "./useTopPerforming";

interface Props {
  dateOnlyFilters: Pick<DashboardFilters, "range" | "date_from" | "date_to">;
  onSelect90d: () => void;
}

function barColor(rating: number): string {
  if (rating >= 4.0) return "#16A34A";
  if (rating >= 3.0) return "#D97706";
  return "#DC2626";
}

function buildReviewsUrl(shopId: number, from: string | null, to: string | null): string {
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
    <div className="bg-white border border-line rounded-lg shadow-sm p-2.5 text-[13px]">
      <p className="font-semibold text-ink mb-0.5">{bar.shop_name}</p>
      <p className="text-text">Avg: {bar.avg_rating.toFixed(2)} ★</p>
      <p className="text-muted">{bar.review_count} reviews</p>
    </div>
  );
}

function CalloutCard({
  tone,
  icon,
  badgeLabel,
  shop,
}: {
  tone: "good" | "bad";
  icon: React.ReactNode;
  badgeLabel: string;
  shop: HighlightShop;
}) {
  const isGood = tone === "good";
  return (
    <div
      className={`rounded-[10px] p-3 border ${isGood ? "bg-green-tint border-[#BBF7D0]" : "bg-red-tint border-[#FECACA]"}`}
    >
      <div
        className={`inline-flex items-center gap-1.5 text-[11.5px] font-semibold uppercase tracking-[0.06em] ${isGood ? "text-[#166534]" : "text-[#991B1B]"}`}
      >
        {icon}
        <span>{badgeLabel}</span>
      </div>
      <div className="mt-1 text-[14px] text-ink">
        <strong className="font-semibold">{shop.shop_name}</strong>
      </div>
      <div className={`mt-1 text-[12px] tabular-nums ${isGood ? "text-[#166534]" : "text-[#991B1B]"}`}>
        {shop.avg_rating.toFixed(1)} ★ · {shop.review_count} reviews
      </div>
    </div>
  );
}

export function TopPerformingSection({ dateOnlyFilters, onSelect90d }: Props) {
  const topQuery = useTopPerforming(dateOnlyFilters);
  const highlightsQuery = useHighlights(dateOnlyFilters);

  if (topQuery.isLoading) {
    return (
      <section className="bg-white border border-line rounded-[14px] p-5">
        <div className="bg-line-soft rounded-xl animate-[sk-pulse_1.6s_ease-in-out_infinite] h-[280px]" />
      </section>
    );
  }

  if (topQuery.isError) {
    return (
      <section className="bg-white border border-line rounded-[14px] p-5">
        <p className="text-[14px] text-muted">
          Could not load.{" "}
          <button
            onClick={() => void topQuery.refetch()}
            className="text-[14px] font-semibold text-ink underline"
          >
            Retry
          </button>
        </p>
      </section>
    );
  }

  const response = topQuery.data;

  if (!response || response.shops.length === 0) {
    return (
      <section className="bg-white border border-line rounded-[14px] p-5">
        <div className="text-center py-12">
          <BarChart2 className="size-8 text-faint mx-auto mb-3" aria-hidden="true" />
          <h3 className="text-[18px] font-semibold text-ink tracking-tight">No qualifying stores in this period</h3>
          <p className="text-[13.5px] text-muted mt-2">Stores need at least 3 reviews in the selected period.</p>
          <button
            onClick={onSelect90d}
            className="mt-4 inline-flex items-center gap-2 px-4 py-2 bg-black text-yellow text-[13.5px] font-semibold rounded-lg"
          >
            View last 90 days
          </button>
        </div>
      </section>
    );
  }

  let chartData: ChartBar[];
  if (response.split && response.shops.length > 5) {
    const top5 = response.shops.slice(0, 5);
    const worst5 = response.shops.slice(5);
    const separator: SeparatorBar = { shop_id: -1, shop_name: "…", review_count: 0, avg_rating: 0, _separator: true };
    chartData = [...top5, separator, ...worst5];
  } else {
    chartData = response.shops;
  }

  const highlights = highlightsQuery.data;

  return (
    <section className="bg-white border border-line rounded-[14px] p-5">
      {/* Header */}
      <div className="flex items-start justify-between gap-3 mb-3.5">
        <div>
          <h2 className="text-[15px] font-semibold text-ink tracking-[-0.01em] mb-0.5">
            Best &amp; worst performing outlets
          </h2>
          <p className="text-[12.5px] text-subtle">
            Top 5 and bottom 5 by average rating · date range only · store filter not applied
          </p>
        </div>
        {response.split && (
          <div className="inline-flex items-center gap-2.5 text-[12px] text-subtle shrink-0">
            <span>
              <span
                className="inline-block w-2 h-2 rounded-full bg-green mr-1"
                aria-hidden="true"
              />
              Top 5
            </span>
            <span>
              <span
                className="inline-block w-2 h-2 rounded-full bg-red mr-1"
                aria-hidden="true"
              />
              Bottom 5
            </span>
          </div>
        )}
      </div>

      {/* Bar chart */}
      <div role="img" aria-label="Best and worst performing outlets bar chart">
        <ResponsiveContainer width="100%" height={280}>
          <BarChart data={chartData} barCategoryGap="30%" margin={{ bottom: 40 }}>
            <XAxis
              dataKey="shop_name"
              tick={{ fontSize: 10, fill: "#71717A" }}
              interval={0}
              tickFormatter={(name: string) => truncate(name, 12)}
              axisLine={{ stroke: "#E4E4E7" }}
              tickLine={false}
              angle={-35}
              textAnchor="end"
              height={60}
            />
            <YAxis
              domain={[0, 5]}
              ticks={[0, 1, 2, 3, 4, 5]}
              tick={{ fontSize: 11, fill: "#A1A1AA" }}
              axisLine={false}
              tickLine={false}
              width={24}
            />
            <Tooltip content={<CustomTooltip />} cursor={{ fill: "rgba(0,0,0,0.03)" }} />
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
                  return <Cell key="separator" fill="transparent" style={{ cursor: "default" }} />;
                }
                return <Cell key={bar.shop_id} fill={barColor(bar.avg_rating)} />;
              })}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Callouts footer */}
      {highlights && (highlights.top !== null || highlights.bottom !== null) && (
        <div
          className="grid gap-2.5 mt-4"
          style={{ gridTemplateColumns: highlights.top && highlights.bottom ? "1fr 1fr" : "1fr" }}
        >
          {highlights.top && (
            <CalloutCard
              tone="good"
              icon={<CheckCircle size={14} />}
              badgeLabel="Top performer"
              shop={highlights.top}
            />
          )}
          {highlights.bottom && (
            <CalloutCard
              tone="bad"
              icon={<AlertTriangle size={14} />}
              badgeLabel="Needs attention"
              shop={highlights.bottom}
            />
          )}
        </div>
      )}
    </section>
  );
}
