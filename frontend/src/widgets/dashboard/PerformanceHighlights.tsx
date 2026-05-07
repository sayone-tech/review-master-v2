import { TrendingDown, TrendingUp } from "lucide-react";

import type { DashboardFilters } from "./types";
import { useHighlights } from "./useHighlights";

interface Props {
  dateOnlyFilters: Pick<DashboardFilters, "range" | "date_from" | "date_to">;
}

export function PerformanceHighlights({ dateOnlyFilters }: Props) {
  const query = useHighlights(dateOnlyFilters);

  if (query.isLoading) {
    return (
      <div className="flex flex-col gap-4">
        <div className="bg-line-soft rounded-card animate-[sk-pulse_1.6s_ease-in-out_infinite] h-[120px]" />
        <div className="bg-line-soft rounded-card animate-[sk-pulse_1.6s_ease-in-out_infinite] h-[120px]" />
      </div>
    );
  }

  if (query.isError) {
    return (
      <div className="text-[14px] text-muted">
        Could not load highlights.{" "}
        <button
          onClick={() => void query.refetch()}
          className="text-[14px] font-semibold text-ink underline"
          aria-label="Retry loading performance highlights"
        >
          Retry
        </button>
      </div>
    );
  }

  const data = query.data;

  // Empty — parent empty state covers the section
  if (!data || data.top === null) {
    return null;
  }

  return (
    <div className="flex flex-col gap-4">
      {/* Top sub-card */}
      <div className="bg-green-tint border border-green/30 rounded-card p-4">
        <div className="flex items-center gap-2 mb-2">
          <TrendingUp size={16} className="text-green" aria-hidden="true" />
          <span className="text-[14px] font-bold text-green">Top Performer</span>
        </div>
        <p className="text-[14px] font-semibold text-ink">{data.top.shop_name}</p>
        <p className="text-[24px] font-bold text-green tabular-nums">
          {data.top.avg_rating.toFixed(1)}
        </p>
        <p className="text-[14px] text-muted">
          {data.top.positive_count} positive reviews (AI-derived)
        </p>
      </div>

      {/* Bottom sub-card */}
      {data.bottom !== null && (
        <div className="bg-red-tint border border-red/30 rounded-card p-4">
          <div className="flex items-center gap-2 mb-2">
            <TrendingDown size={16} className="text-red" aria-hidden="true" />
            <span className="text-[14px] font-bold text-red">Needs Attention</span>
          </div>
          <p className="text-[14px] font-semibold text-ink">{data.bottom.shop_name}</p>
          <p className="text-[24px] font-bold text-red tabular-nums">
            {data.bottom.avg_rating.toFixed(1)}
          </p>
          <p className="text-[14px] text-muted">
            {data.bottom.negative_count} negative reviews (AI-derived)
          </p>
        </div>
      )}
    </div>
  );
}
