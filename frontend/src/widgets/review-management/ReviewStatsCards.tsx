import { FileText, MessageCircle, Star, TrendingUp } from "lucide-react";
import type { ReviewStats } from "./types";

interface Props {
  stats: ReviewStats | null;
  loading?: boolean;
}

export function ReviewStatsCards({ stats, loading }: Props) {
  const cards = [
    {
      label: "Total Reviews",
      value: loading || !stats ? "—" : stats.total_count.toLocaleString(),
      sub: "all time",
      icon: <FileText size={16} aria-hidden="true" />,
      iconColor: "#A1A1AA",
      valueColor: "#18181B",
    },
    {
      label: "Avg Rating",
      value: loading || !stats ? "—" : stats.avg_rating.toFixed(1),
      sub: "out of 5 stars",
      icon: <Star size={16} aria-hidden="true" fill="#FACC15" />,
      iconColor: "#FACC15",
      valueColor: "#18181B",
    },
    {
      label: "Awaiting Reply",
      value: loading || !stats ? "—" : stats.awaiting_reply_count.toLocaleString(),
      sub: "need attention",
      icon: <MessageCircle size={16} aria-hidden="true" />,
      iconColor: "#D97706",
      valueColor: "#D97706",
    },
    {
      label: "Positive Sentiment",
      value: loading || !stats ? "—" : `${stats.positive_sentiment_pct}%`,
      sub: "of enriched reviews",
      icon: <TrendingUp size={16} aria-hidden="true" />,
      iconColor: "#16A34A",
      valueColor: "#15803D",
    },
  ];

  return (
    <div
      className="grid gap-3"
      style={{ gridTemplateColumns: "repeat(4, minmax(0, 1fr))" }}
    >
      {cards.map((c) => (
        <div
          key={c.label}
          className="bg-white border border-line rounded-card p-4 flex flex-col gap-1.5"
        >
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-semibold text-subtle uppercase tracking-[0.06em]">
              {c.label}
            </span>
            <span style={{ color: c.iconColor }}>{c.icon}</span>
          </div>
          <div
            className={`text-[26px] font-bold leading-none tabular-nums ${loading ? "opacity-40" : ""}`}
            style={{ color: c.valueColor }}
          >
            {c.value}
          </div>
          <div className="text-[12px] text-muted">{c.sub}</div>
        </div>
      ))}
    </div>
  );
}
