import { Loader2 } from "lucide-react";
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";

import type { DashboardFilters } from "./types";
import { useSentiment } from "./useSentiment";

const COLORS = {
  positive: "#22C55E",
  neutral: "#F59E0B",
  negative: "#EF4444",
} as const;

type SentimentKey = keyof typeof COLORS;

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
    <div className="bg-white rounded-md shadow border border-line p-2 text-[14px]">
      <div className="capitalize font-semibold">{name}</div>
      <div>
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
    <div className="bg-white border border-line rounded-card p-4">
      <h2 className="text-[20px] font-bold text-ink mb-4">Sentiment Distribution</h2>

      {isLoading && (
        <div
          className="bg-line-soft rounded-full animate-[sk-pulse_1.6s_ease-in-out_infinite] mx-auto"
          style={{ width: 160, height: 160 }}
          aria-label="Loading sentiment data"
        />
      )}

      {isError && (
        <div className="flex flex-col gap-2">
          <p className="text-[14px] text-muted">Could not load.</p>
          <button
            onClick={() => void refetch()}
            className="text-[14px] font-semibold text-ink underline"
            aria-label="Retry loading Sentiment Distribution"
          >
            Retry
          </button>
        </div>
      )}

      {!isLoading && !isError && data && (
        <>
          {/* Empty: no reviews at all */}
          {data.total_count === 0 && (
            <p className="text-[14px] text-muted text-center py-8">
              No reviews to analyze in this period.
            </p>
          )}

          {/* Empty: reviews exist but none enriched yet */}
          {data.total_count > 0 && data.enriched_count === 0 && (
            <div className="text-center py-8">
              <Loader2
                className="size-6 animate-spin text-faint mx-auto mb-2"
                aria-hidden="true"
              />
              <p className="text-[14px] text-muted">
                Sentiment analysis is in progress. Check back shortly.
              </p>
            </div>
          )}

          {/* Populated */}
          {data.enriched_count > 0 && (
            <>
              <ResponsiveContainer width="100%" height={200}>
                <PieChart role="img" aria-label="Sentiment distribution donut chart">
                  <Pie
                    data={[
                      { name: "positive", value: data.positive },
                      { name: "neutral", value: data.neutral },
                      { name: "negative", value: data.negative },
                    ]}
                    dataKey="value"
                    innerRadius="55%"
                    outerRadius="80%"
                    paddingAngle={2}
                    startAngle={90}
                    endAngle={-270}
                  >
                    {(Object.keys(COLORS) as SentimentKey[]).map((k) => (
                      <Cell key={k} fill={COLORS[k]} />
                    ))}
                  </Pie>
                  <Tooltip
                    content={<CustomDonutTooltip total={data.enriched_count} />}
                  />
                </PieChart>
              </ResponsiveContainer>

              {/* Summary list */}
              <div className="flex flex-col gap-2 mt-2">
                {(Object.keys(COLORS) as SentimentKey[]).map((k) => {
                  const count = data[k];
                  const pct =
                    data.enriched_count > 0
                      ? Math.round((count / data.enriched_count) * 100)
                      : 0;
                  return (
                    <div key={k} className="flex items-center gap-2">
                      <span
                        className="w-3 h-3 rounded-sm shrink-0"
                        style={{ backgroundColor: COLORS[k] }}
                        aria-hidden="true"
                      />
                      <span className="text-[14px] text-text capitalize">{k}</span>
                      <div className="flex-1 bg-line-soft h-2 rounded-full overflow-hidden ml-2">
                        <div
                          className="h-2 rounded-full"
                          style={{ width: `${pct}%`, backgroundColor: COLORS[k] }}
                        />
                      </div>
                      <span className="text-[14px] font-semibold text-ink tabular-nums">
                        {count}
                      </span>
                      <span className="text-[14px] text-muted">{pct}%</span>
                    </div>
                  );
                })}
              </div>

              {/* Coverage footer */}
              {data.coverage_pct < 100 && (
                <div className="text-[11px] text-subtle mt-3 pt-3 border-t border-line">
                  Based on {data.enriched_count} enriched reviews ({data.coverage_pct}% of total)
                  {data.coverage_pct < 50 && (
                    <span className="ml-2 inline-flex items-center gap-1">
                      <Loader2 className="size-3 animate-spin" aria-hidden="true" />{" "}
                      Analysis is still in progress.
                    </span>
                  )}
                </div>
              )}
            </>
          )}
        </>
      )}
    </div>
  );
}
