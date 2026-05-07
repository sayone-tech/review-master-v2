import type { DashboardFilters, YourStoreResponse } from "./types";
import { useYourStore } from "./useYourStore";

interface Props {
  dateOnlyFilters: Pick<DashboardFilters, "range" | "date_from" | "date_to">;
}

type StarKey = 1 | 2 | 3 | 4 | 5;

function TrendIndicator({
  direction,
  delta,
}: {
  direction: YourStoreResponse["trend_direction"];
  delta: number | null;
}) {
  if (direction === "up") {
    return (
      <div className="flex flex-col items-end">
        <span className="text-[16px] font-bold text-green">↑</span>
        {delta !== null && (
          <span className="text-[14px] text-green">{delta.toFixed(2)}</span>
        )}
      </div>
    );
  }
  if (direction === "down") {
    return (
      <div className="flex flex-col items-end">
        <span className="text-[16px] font-bold text-red">↓</span>
        {delta !== null && (
          <span className="text-[14px] text-red">{delta.toFixed(2)}</span>
        )}
      </div>
    );
  }
  if (direction === "flat") {
    return (
      <div className="flex flex-col items-end">
        <span className="text-[16px] text-faint">→</span>
      </div>
    );
  }
  // "none" — no comparison period available, show nothing
  return null;
}

function DistributionBars({
  distribution,
}: {
  distribution: YourStoreResponse["distribution"];
}) {
  const keys: StarKey[] = [5, 4, 3, 2, 1];
  const maxCount = Math.max(...keys.map((k) => distribution[k]));

  return (
    <div className="flex flex-col gap-1 mt-4">
      {keys.map((star) => {
        const count = distribution[star];
        const widthPct = maxCount > 0 ? (count / maxCount) * 100 : 0;
        return (
          <div key={star} className="flex items-center gap-2">
            <span className="text-[11px] text-muted w-4">{star}</span>
            <div className="bg-line-soft h-2 rounded-full flex-1 relative overflow-hidden">
              <div
                className="bg-yellow h-2 rounded-full"
                style={{ width: `${widthPct}%` }}
              />
            </div>
            <span className="text-[11px] text-muted w-6 text-right">{count}</span>
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
      <div className="bg-white border border-line rounded-card p-6">
        <h2 className="text-[20px] font-bold text-ink mb-1">Your Store</h2>
        <div className="flex flex-col gap-3 mt-4">
          <div className="bg-line-soft rounded animate-[sk-pulse_1.6s_ease-in-out_infinite] h-5 w-32" />
          <div className="bg-line-soft rounded animate-[sk-pulse_1.6s_ease-in-out_infinite] h-9 w-16" />
          <div className="bg-line-soft rounded animate-[sk-pulse_1.6s_ease-in-out_infinite] h-3 w-24" />
          <div className="flex flex-col gap-1 mt-2">
            {[5, 4, 3, 2, 1].map((star) => (
              <div key={star} className="flex items-center gap-2">
                <div className="bg-line-soft rounded animate-[sk-pulse_1.6s_ease-in-out_infinite] h-2 w-4" />
                <div className="bg-line-soft rounded animate-[sk-pulse_1.6s_ease-in-out_infinite] h-2 flex-1" />
                <div className="bg-line-soft rounded animate-[sk-pulse_1.6s_ease-in-out_infinite] h-2 w-6" />
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (query.isError) {
    return (
      <div className="bg-white border border-line rounded-card p-6">
        <h2 className="text-[20px] font-bold text-ink mb-1">Your Store</h2>
        <p className="text-[14px] text-muted">
          Could not load.{" "}
          <button
            onClick={() => void query.refetch()}
            className="text-[14px] font-semibold text-ink underline"
            aria-label="Retry loading Your Store"
          >
            Retry
          </button>
        </p>
      </div>
    );
  }

  const data = query.data;
  if (!data) return null;

  return (
    <div className="bg-white border border-line rounded-card p-6">
      <h2 className="text-[20px] font-bold text-ink mb-1">Your Store</h2>

      <div style={{ display: "grid", gridTemplateColumns: "1fr auto", gap: 16, alignItems: "start", marginTop: 12 }}>
        {/* Left column */}
        <div>
          <p className="text-[20px] font-bold text-ink">{data.shop_name}</p>
          {data.region_name && (
            <span className="inline-flex items-center px-2 py-1 bg-line-soft text-[11px] font-semibold text-subtle rounded-full mt-1">
              {data.region_name}
            </span>
          )}
          <div className="flex items-baseline gap-1 mt-2">
            <span className="text-[36px] font-bold text-ink tabular-nums">
              {data.avg_rating.toFixed(1)}
            </span>
            <span className="text-[14px] text-muted ml-1">out of 5</span>
          </div>
          <p className="text-[14px] text-muted">{data.total_reviews} reviews</p>
          <p className="text-[14px] text-green font-semibold">
            {data.positive_count} positive ({data.positive_pct}%)
          </p>
          <p className="text-[14px] text-red font-semibold">
            {data.negative_count} negative ({data.negative_pct}%)
          </p>
        </div>

        {/* Right column — trend indicator */}
        <TrendIndicator
          direction={data.trend_direction}
          delta={data.trend_delta}
        />
      </div>

      {/* 5-star distribution */}
      <DistributionBars distribution={data.distribution} />
    </div>
  );
}
