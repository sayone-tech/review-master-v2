import type { ReviewStats } from "./types";

interface Props {
  stats: ReviewStats | null;
  loading?: boolean;
}

function Sep() {
  return <span aria-hidden="true" className="w-px h-[18px] bg-line" />;
}

export function ReviewStatsCards({ stats, loading }: Props) {
  const dash = loading || !stats;
  const items = [
    { value: dash ? "—" : stats.total_count.toLocaleString(), label: "reviews", cls: "text-ink" },
    { value: dash ? "—" : `${stats.avg_rating.toFixed(1)} ★`, label: "avg rating", cls: "text-ink" },
    { value: dash ? "—" : stats.awaiting_reply_count.toLocaleString(), label: "awaiting reply", cls: "text-amber" },
    { value: dash ? "—" : `${stats.positive_sentiment_pct}%`, label: "positive", cls: "text-green" },
  ];

  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 bg-white border border-line rounded-[10px] px-[14px] py-[9px] text-[13px]">
      {items.map((it, i) => (
        <div key={it.label} className="flex items-center gap-4">
          {i > 0 && <Sep />}
          <span className={`flex items-baseline gap-[6px] ${loading ? "opacity-40" : ""}`}>
            <span className={`text-[15px] font-semibold tabular-nums ${it.cls}`}>{it.value}</span>
            <span className="text-muted">{it.label}</span>
          </span>
        </div>
      ))}
    </div>
  );
}
