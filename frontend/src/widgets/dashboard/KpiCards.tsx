import { FileText, Star, StarHalf, TrendingDown } from "lucide-react";

import type { DashboardFilters } from "./types";
import { useKpis } from "./useKpis";

interface Props {
  filters: DashboardFilters;
  shopNameIfSingle: string | null; // From bootstrap data when isSingleShop
}

function CardSkeleton() {
  return (
    <div className="bg-white border border-line rounded-card p-4 flex flex-col gap-2">
      <div className="h-3 w-24 bg-line-soft rounded animate-[sk-pulse_1.6s_ease-in-out_infinite] mb-2" />
      <div className="h-8 w-16 bg-line-soft rounded animate-[sk-pulse_1.6s_ease-in-out_infinite]" />
      <div className="h-3 w-32 bg-line-soft rounded animate-[sk-pulse_1.6s_ease-in-out_infinite] mt-2" />
    </div>
  );
}

function CardError({ title, refetch }: { title: string; refetch: () => void }) {
  return (
    <div className="bg-white border border-line rounded-card p-4 flex flex-col gap-2">
      <p className="text-[14px] text-muted">Could not load.</p>
      <button
        onClick={refetch}
        className="text-[14px] font-semibold text-ink underline"
        aria-label={`Retry loading ${title}`}
      >
        Retry
      </button>
    </div>
  );
}

function StarRating({ avg }: { avg: number }) {
  return (
    <div className="flex items-center gap-0.5 mt-1">
      {Array.from({ length: 5 }, (_, i) => {
        const pos = i + 1;
        const frac = avg - Math.floor(avg);
        if (Math.floor(avg) >= pos) {
          return (
            <Star
              key={pos}
              size={14}
              fill="#FACC15"
              className="text-yellow"
              aria-hidden="true"
            />
          );
        } else if (pos - 1 < avg && avg < pos && frac >= 0.25 && frac <= 0.74) {
          return (
            <StarHalf
              key={pos}
              size={14}
              fill="#FACC15"
              className="text-yellow"
              aria-hidden="true"
            />
          );
        } else {
          return (
            <Star
              key={pos}
              size={14}
              className="text-line"
              aria-hidden="true"
            />
          );
        }
      })}
    </div>
  );
}

export function KpiCards({ filters, shopNameIfSingle }: Props) {
  const { data, isLoading, isError, refetch } = useKpis(filters);

  if (isLoading) {
    return (
      <div className="grid grid-cols-3 gap-4">
        <CardSkeleton />
        <CardSkeleton />
        <CardSkeleton />
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="grid grid-cols-3 gap-4">
        <CardError title="Total Reviews" refetch={refetch} />
        <CardError title="Average Rating" refetch={refetch} />
        <CardError title="Negative Reviews" refetch={refetch} />
      </div>
    );
  }

  const isEmpty = data.total_reviews === 0;
  const emptyFooter = "No reviews in this period";

  return (
    <div className="grid grid-cols-3 gap-4">
      {/* Card 1: Total Reviews */}
      <div className="bg-white border border-line rounded-card p-4 flex flex-col gap-2">
        <div className="flex items-center justify-between">
          <span className="text-[11px] font-bold text-subtle uppercase tracking-[0.06em]">
            Total Reviews
          </span>
          <FileText size={16} className="text-faint" aria-hidden="true" />
        </div>
        <div className="text-[24px] font-bold leading-none tabular-nums">
          {isEmpty ? "—" : data.total_reviews}
        </div>
        <div className="text-[14px] text-muted">
          {isEmpty
            ? emptyFooter
            : data.store_count > 1
              ? `Across ${data.store_count} stores`
              : (shopNameIfSingle ?? "")}
        </div>
      </div>

      {/* Card 2: Average Rating */}
      <div className="bg-white border border-line rounded-card p-4 flex flex-col gap-2">
        <div className="flex items-center justify-between">
          <span className="text-[11px] font-bold text-subtle uppercase tracking-[0.06em]">
            Average Rating
          </span>
          <Star size={16} fill="#FACC15" className="text-yellow" aria-hidden="true" />
        </div>
        {isEmpty ? (
          <>
            <div className="text-[24px] font-bold leading-none tabular-nums">—</div>
            <div className="text-[14px] text-muted">{emptyFooter}</div>
          </>
        ) : (
          <>
            <div className="text-[24px] font-bold leading-none tabular-nums">
              {data.avg_rating.toFixed(1)}
            </div>
            <StarRating avg={data.avg_rating} />
            <div className="text-[14px] text-muted">out of 5 stars</div>
          </>
        )}
      </div>

      {/* Card 3: Negative Reviews */}
      <div className="bg-white border border-line rounded-card p-4 flex flex-col gap-2">
        <div className="flex items-center justify-between">
          <span className="text-[11px] font-bold text-subtle uppercase tracking-[0.06em]">
            Negative Reviews
          </span>
          <TrendingDown size={16} className="text-red" aria-hidden="true" />
        </div>
        {isEmpty ? (
          <>
            <div className="text-[24px] font-bold leading-none tabular-nums">—</div>
            <div className="text-[14px] text-muted">{emptyFooter}</div>
          </>
        ) : (
          <>
            <div className="text-[24px] font-bold leading-none tabular-nums text-red">
              {data.negative_reviews}
            </div>
            <div className="text-[14px] text-muted">
              {data.negative_pct}% of enriched reviews
            </div>
          </>
        )}
      </div>
    </div>
  );
}
