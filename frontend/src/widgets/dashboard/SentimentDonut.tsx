import { Loader2, MessageCircle } from "lucide-react";
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";

import type { DashboardFilters } from "./types";
import { useSentiment } from "./useSentiment";

const COLORS = {
  positive: "#16A34A",
  neutral: "#D97706",
  negative: "#DC2626",
} as const;

type SentimentKey = keyof typeof COLORS;

const LABELS: Record<SentimentKey, string> = {
  positive: "Positive",
  neutral: "Neutral",
  negative: "Negative",
};

function CustomDonutTooltip({
  active,
  payload,
  total,
}: {
  active?: boolean;
  payload?: { name: string; value: number }[];
  total: number;
}) {
  if (!active || !payload?.length) return null;
  const { name, value } = payload[0];
  const pct = total > 0 ? Math.round((value / total) * 100) : 0;
  return (
    <div className="bg-white rounded-lg shadow border border-line p-2.5 text-[13px]">
      <div className="capitalize font-semibold text-ink">{name}</div>
      <div className="text-muted">
        {value} reviews ({pct}%)
      </div>
    </div>
  );
}

interface Props {
  filters: DashboardFilters;
}

export function SentimentDonut({ filters }: Props) {
  const { data, isLoading, isError, refetch } = useSentiment(filters);

  return (
    <section className="bg-white border border-line rounded-[14px] p-5 flex flex-col">
      {/* Header */}
      <div className="mb-3.5">
        <h2 className="text-[15px] font-semibold text-ink tracking-[-0.01em] mb-0.5">Sentiment</h2>
        {!isLoading && !isError && data && data.enriched_count > 0 && (
          <p className="text-[12.5px] text-subtle">
            AI-derived from {data.enriched_count.toLocaleString()} reviews
          </p>
        )}
      </div>

      {/* Loading state */}
      {isLoading && (
        <div
          className="bg-line-soft rounded-full animate-[sk-pulse_1.6s_ease-in-out_infinite] mx-auto my-4"
          style={{ width: 168, height: 168 }}
          aria-label="Loading sentiment data"
        />
      )}

      {/* Error state */}
      {isError && (
        <div className="flex flex-col gap-2 py-4">
          <p className="text-[13px] text-muted">Could not load.</p>
          <button
            onClick={() => void refetch()}
            className="text-[13px] font-semibold text-ink underline text-left"
            aria-label="Retry loading Sentiment Distribution"
          >
            Retry
          </button>
        </div>
      )}

      {!isLoading && !isError && data && (
        <>
          {/* Empty — no reviews */}
          {data.total_count === 0 && (
            <p className="text-[13.5px] text-muted text-center py-10">
              No reviews to analyze in this period.
            </p>
          )}

          {/* Reviews exist but none enriched */}
          {data.total_count > 0 && data.enriched_count === 0 && (
            <div className="text-center py-10">
              <Loader2 className="size-6 animate-spin text-faint mx-auto mb-2" aria-hidden="true" />
              <p className="text-[13.5px] text-muted">Sentiment analysis in progress.</p>
            </div>
          )}

          {/* Populated */}
          {data.enriched_count > 0 && (
            <>
              {/* Donut + center label */}
              <div className="flex flex-col items-center gap-[18px] py-2">
                <div className="relative flex items-center justify-center" style={{ width: 168, height: 168 }}>
                  {/* Center text overlay — sits behind the chart SVG so tooltip isn't blocked */}
                  <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none" style={{ zIndex: 0 }}>
                    <span className="text-[32px] font-semibold text-ink leading-none tabular-nums tracking-[-0.02em]">
                      {Math.round((data.positive / data.enriched_count) * 100)}%
                    </span>
                    <span className="text-[11px] text-subtle uppercase tracking-[0.08em] mt-1">
                      positive
                    </span>
                  </div>
                  <div style={{ position: "relative", zIndex: 1 }}>
                    <ResponsiveContainer width={168} height={168}>
                      <PieChart role="img" aria-label="Sentiment distribution donut chart">
                        <Pie
                          data={[
                            { name: "positive", value: data.positive },
                            { name: "neutral", value: data.neutral },
                            { name: "negative", value: data.negative },
                          ]}
                          dataKey="value"
                          innerRadius="67%"
                          outerRadius="84%"
                          paddingAngle={0}
                          startAngle={90}
                          endAngle={-270}
                          strokeWidth={0}
                        >
                          {(Object.keys(COLORS) as SentimentKey[]).map((k) => (
                            <Cell key={k} fill={COLORS[k]} />
                          ))}
                        </Pie>
                        <Tooltip content={<CustomDonutTooltip total={data.enriched_count} />} />
                      </PieChart>
                    </ResponsiveContainer>
                  </div>
                </div>

                {/* Legend rows */}
                <ul className="w-full space-y-2 list-none m-0 p-0">
                  {(Object.keys(COLORS) as SentimentKey[]).map((k) => {
                    const count = data[k];
                    const pct = Math.round((count / data.enriched_count) * 100);
                    return (
                      <li
                        key={k}
                        className="grid items-center gap-2.5 text-[12.5px] tabular-nums"
                        style={{ gridTemplateColumns: "8px 60px 1fr auto auto" }}
                      >
                        <span
                          className="w-2 h-2 rounded-full shrink-0"
                          style={{ background: COLORS[k] }}
                          aria-hidden="true"
                        />
                        <span className="text-ink font-medium">{LABELS[k]}</span>
                        <div className="h-1.5 bg-line-soft rounded-full overflow-hidden">
                          <div
                            className="h-full rounded-full"
                            style={{ width: `${pct}%`, background: COLORS[k] }}
                          />
                        </div>
                        <span className="font-semibold text-ink">{count}</span>
                        <span className="text-subtle w-8 text-right">{pct}%</span>
                      </li>
                    );
                  })}
                </ul>
              </div>

              {/* Coverage note */}
              {data.coverage_pct < 100 && (
                <p className="text-[11px] text-subtle mt-2">
                  Based on {data.enriched_count} enriched reviews ({data.coverage_pct}% of total)
                  {data.coverage_pct < 50 && (
                    <span className="inline-flex items-center gap-1 ml-1">
                      <Loader2 className="size-3 animate-spin" aria-hidden="true" />
                      Analysis in progress.
                    </span>
                  )}
                </p>
              )}

              {/* Footer link */}
              <div className="mt-3.5 pt-3.5 border-t border-line-soft">
                <a
                  href={(() => {
                    const p = new URLSearchParams();
                    p.set("sentiment", "negative");
                    if (filters.shop_id) p.set("store", String(filters.shop_id));
                    if (filters.date_from) p.set("from", filters.date_from);
                    if (filters.date_to) p.set("to", filters.date_to);
                    return `/admin/org/reviews/?${p.toString()}`;
                  })()}
                  className="inline-flex items-center gap-1.5 text-[13px] text-ink hover:text-muted transition-colors"
                >
                  <MessageCircle size={14} aria-hidden="true" />
                  See negative reviews
                </a>
              </div>
            </>
          )}
        </>
      )}
    </section>
  );
}
