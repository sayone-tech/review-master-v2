// Phase 25-04 — Dashboard tag polarity chart (TDASH-01).
// always_positive/always_negative tags render a single colored bar;
// mixed tags render a stacked positive/negative split (recharts stackId="a").
import { Tag } from "lucide-react";
import {
  Bar,
  BarChart,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useQuery } from "@tanstack/react-query";

import { fetchTagPolarity } from "./api";
import type { TagPolarityBar } from "./types";

// ---------------------------------------------------------------------------
// Tooltip
// ---------------------------------------------------------------------------

interface TagPolarityTooltipProps {
  active?: boolean;
  payload?: Array<{ payload: TagPolarityBar }>;
}

function TagPolarityTooltip({ active, payload }: TagPolarityTooltipProps) {
  if (!active || !payload || payload.length === 0) return null;
  const tag = payload[0].payload;
  const polarityLabel =
    tag.polarity_type === "always_positive"
      ? "Always positive"
      : tag.polarity_type === "always_negative"
        ? "Always negative"
        : "Mixed";
  return (
    <div className="bg-white rounded-lg shadow border border-line p-2 text-[14px]">
      <div className="font-semibold text-ink mb-1">{tag.label}</div>
      <div className="text-[12px] text-subtle capitalize mb-1">{polarityLabel}</div>
      {tag.polarity_type === "mixed" ? (
        <>
          <div className="text-[12px]">
            <span
              className="inline-block w-2 h-2 rounded-full bg-green mr-2"
              aria-hidden="true"
            />
            Positive: {tag.positive_count}
          </div>
          <div className="text-[12px]">
            <span
              className="inline-block w-2 h-2 rounded-full bg-red mr-2"
              aria-hidden="true"
            />
            Negative: {tag.negative_count}
          </div>
        </>
      ) : (
        <div className="text-[12px] text-muted">{tag.total_count} reviews</div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main chart component
// ---------------------------------------------------------------------------

export function TagPolarityChart() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["dashboard", "tag-polarity"],
    queryFn: fetchTagPolarity,
  });

  if (isLoading) {
    return (
      <section className="bg-white border border-line rounded-[14px] p-4">
        <div className="bg-line-soft rounded-xl animate-[sk-pulse_1.6s_ease-in-out_infinite] h-[240px]" />
      </section>
    );
  }

  if (isError) {
    return (
      <section className="bg-white border border-line rounded-[14px] p-4">
        <p className="text-[14px] text-muted text-center py-8">
          Could not load tag distribution.
        </p>
      </section>
    );
  }

  const tags = data?.tags ?? [];
  const hasMore = data?.has_more ?? false;

  return (
    <section className="bg-white border border-line rounded-[14px] p-4 flex flex-col">
      {/* Header */}
      <div className="mb-3">
        <h2 className="text-[18px] font-semibold text-ink tracking-[-0.01em] mb-1">
          Tag Distribution
        </h2>
        <p className="text-[12px] text-subtle">
          Top tags by review volume · canonical tags only
        </p>
      </div>

      {/* Empty state */}
      {tags.length === 0 ? (
        <p className="text-[14px] text-muted text-center py-8">
          No canonical tags yet. Tags will appear as reviews are enriched.
        </p>
      ) : (
        <>
          {/* Bar chart */}
          <div role="img" aria-label="Tag distribution by polarity bar chart">
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={tags} barCategoryGap="35%" margin={{ bottom: 48 }}>
                <XAxis
                  dataKey="label"
                  tick={{ fontSize: 12, fill: "#71717A" }}
                  tickFormatter={(name: string) =>
                    name.length > 14 ? name.slice(0, 13) + "…" : name
                  }
                  angle={-35}
                  textAnchor="end"
                  height={56}
                  axisLine={{ stroke: "#E4E4E7" }}
                  tickLine={false}
                  interval={0}
                />
                <YAxis
                  tick={{ fontSize: 12, fill: "#A1A1AA" }}
                  axisLine={false}
                  tickLine={false}
                  width={28}
                />
                <Tooltip
                  content={<TagPolarityTooltip />}
                  cursor={{ fill: "rgba(0,0,0,0.03)" }}
                />
                <Legend
                  verticalAlign="top"
                  height={28}
                  iconSize={8}
                  iconType="circle"
                  formatter={(value: string) => (
                    <span style={{ fontSize: 12, color: "#71717A" }}>{value}</span>
                  )}
                />
                {/* Positive on bottom (no radius), negative on top (rounded top corners).
                    always_* tags render naturally as single-color bars since the opposite
                    count is 0 — no Cell branching needed (TDASH-01). */}
                <Bar
                  dataKey="positive_count"
                  name="Positive"
                  stackId="a"
                  fill="#16A34A"
                  radius={[0, 0, 0, 0]}
                />
                <Bar
                  dataKey="negative_count"
                  name="Negative"
                  stackId="a"
                  fill="#DC2626"
                  radius={[4, 4, 0, 0]}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* "See all tags" footer */}
          {hasMore && (
            <div className="mt-3 pt-3 border-t border-line-soft">
              <a
                href="/admin/org/tags/"
                className="inline-flex items-center gap-1 text-[14px] text-ink hover:text-muted transition-colors"
              >
                <Tag size={14} aria-hidden="true" />
                See all tags
              </a>
            </div>
          )}
        </>
      )}
    </section>
  );
}
