import { Star, StarHalf } from "lucide-react";

import type { DashboardFilters } from "./types";
import { useKpis } from "./useKpis";

interface Props {
  filters: DashboardFilters;
  shopNameIfSingle: string | null;
}

function StarRating({ avg }: { avg: number }) {
  return (
    <span className="inline-flex items-center gap-0.5">
      {Array.from({ length: 5 }, (_, i) => {
        const pos = i + 1;
        const frac = avg - Math.floor(avg);
        if (Math.floor(avg) >= pos) {
          return <Star key={pos} size={14} fill="#FACC15" className="text-yellow" aria-hidden="true" />;
        } else if (pos - 1 < avg && avg < pos && frac >= 0.25 && frac <= 0.74) {
          return <StarHalf key={pos} size={14} fill="#FACC15" className="text-yellow" aria-hidden="true" />;
        }
        return <Star key={pos} size={14} className="text-line" aria-hidden="true" />;
      })}
    </span>
  );
}

interface TileProps {
  label: string;
  value: string | number;
  sub: React.ReactNode;
  accent?: "rating" | "negative" | "amber";
  trend?: { dir: "up" | "down"; text: string };
  skeleton?: boolean;
}

function KpiTile({ label, value, sub, accent, trend, skeleton }: TileProps) {
  const accentColor =
    accent === "rating" ? "#FACC15" :
    accent === "negative" ? "#DC2626" :
    accent === "amber" ? "#D97706" :
    "#E4E4E7";

  if (skeleton) {
    return (
      <div className="bg-white border border-line rounded-xl p-4 flex flex-col gap-1 min-h-[112px] relative overflow-hidden">
        <div className="absolute left-0 top-0 bottom-0 w-[3px] rounded-l-xl" style={{ background: "#E4E4E7" }} />
        <div className="h-2.5 w-24 bg-line-soft rounded animate-[sk-pulse_1.6s_ease-in-out_infinite] mb-1" />
        <div className="h-8 w-14 bg-line-soft rounded animate-[sk-pulse_1.6s_ease-in-out_infinite]" />
        <div className="h-2.5 w-28 bg-line-soft rounded animate-[sk-pulse_1.6s_ease-in-out_infinite] mt-auto" />
      </div>
    );
  }

  return (
    <div className="bg-white border border-line rounded-xl p-4 flex flex-col gap-1 min-h-[112px] relative overflow-hidden">
      {/* Accent left border */}
      <div
        className="absolute left-0 top-0 bottom-0 w-[3px] rounded-l-xl"
        style={{ background: accentColor }}
        aria-hidden="true"
      />

      {/* Label row */}
      <div className="flex items-center justify-between">
        <span className="text-[11.5px] font-medium text-subtle uppercase tracking-[0.06em]">
          {label}
        </span>
      </div>

      {/* Value */}
      <div className="text-[30px] font-semibold text-ink tabular-nums leading-[1.1] tracking-[-0.025em] mt-0.5">
        {value}
      </div>

      {/* Footer */}
      <div className="mt-auto pt-1.5 flex items-center justify-between gap-2 text-[12px] text-subtle">
        <span className="inline-flex items-center gap-1.5">{sub}</span>
        {trend && (
          <span
            className={`tabular-nums font-medium ${trend.dir === "up" ? "text-[#166534]" : "text-[#991B1B]"}`}
          >
            {trend.dir === "up" ? "▲" : "▼"} {trend.text}
          </span>
        )}
      </div>
    </div>
  );
}

export function KpiCards({ filters, shopNameIfSingle }: Props) {
  const { data, isLoading, isError, refetch } = useKpis(filters);

  if (isLoading) {
    return (
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, minmax(0, 1fr))", gap: 12, marginBottom: 18 }}>
        <KpiTile label="" value="" sub="" skeleton />
        <KpiTile label="" value="" sub="" skeleton />
        <KpiTile label="" value="" sub="" skeleton />
        <KpiTile label="" value="" sub="" skeleton />
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, minmax(0, 1fr))", gap: 12, marginBottom: 18 }}>
        {["Total Reviews", "Average Rating", "Negative Reviews", "Awaiting Reply"].map((title) => (
          <div key={title} className="bg-white border border-line rounded-xl p-4 flex flex-col gap-2 min-h-[112px]">
            <p className="text-[13px] text-muted">Could not load.</p>
            <button
              onClick={() => void refetch()}
              className="text-[13px] font-semibold text-ink underline text-left"
              aria-label={`Retry loading ${title}`}
            >
              Retry
            </button>
          </div>
        ))}
      </div>
    );
  }

  const isEmpty = data.total_reviews === 0;
  const storeLabel =
    isEmpty ? "No reviews in this period" :
    data.store_count > 1 ? `across ${data.store_count} stores` :
    (shopNameIfSingle ?? "");

  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(4, minmax(0, 1fr))", gap: 12, marginBottom: 18 }}>
      {/* Total reviews */}
      <KpiTile
        label="Total reviews"
        value={isEmpty ? "—" : data.total_reviews.toLocaleString()}
        sub={storeLabel}
      />

      {/* Average rating */}
      <KpiTile
        label="Average rating"
        value={isEmpty ? "—" : data.avg_rating.toFixed(1)}
        sub={isEmpty ? "No reviews in this period" : <StarRating avg={data.avg_rating} />}
        accent="rating"
      />

      {/* Negative reviews */}
      <KpiTile
        label="Negative reviews"
        value={isEmpty ? "—" : data.negative_reviews.toLocaleString()}
        sub={isEmpty ? "No reviews in this period" : `${data.negative_pct}% of enriched`}
        accent="negative"
      />

      {/* Awaiting reply */}
      <KpiTile
        label="Awaiting reply"
        value={isEmpty ? "—" : data.awaiting_reply.toLocaleString()}
        sub={isEmpty ? "No reviews in this period" : "reviews without a reply"}
        accent="amber"
      />
    </div>
  );
}
