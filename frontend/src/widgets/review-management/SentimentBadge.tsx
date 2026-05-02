import { AlertCircle, Loader2 } from "lucide-react";
import type { EnrichmentStatus, Sentiment } from "./types";

interface Props {
  sentiment: Sentiment;
  enrichmentStatus: EnrichmentStatus;
}

const POSITIVE = { backgroundColor: "#DCFCE7", color: "#16A34A" } as const;
const NEUTRAL = { backgroundColor: "#F4F4F5", color: "#52525B" } as const;
const NEGATIVE = { backgroundColor: "#FEE2E2", color: "#DC2626" } as const;
const ANALYZING = { backgroundColor: "#FEF3C7", color: "#D97706" } as const;

export function SentimentBadge({ sentiment, enrichmentStatus }: Props) {
  if (enrichmentStatus === "FAILED") {
    return (
      <span
        className="inline-flex items-center"
        title="AI analysis failed. Will retry automatically."
      >
        <AlertCircle size={14} className="text-red" aria-label="AI analysis failed" />
      </span>
    );
  }
  if (enrichmentStatus !== "SUCCESS") {
    return (
      <span
        className="inline-flex items-center gap-1 px-2 py-0.5 text-[12px] font-semibold rounded-full"
        style={ANALYZING}
      >
        <Loader2 size={12} className="animate-spin" aria-hidden="true" />
        Analyzing...
      </span>
    );
  }
  let label = "Neutral";
  let style: { backgroundColor: string; color: string } = NEUTRAL;
  if (sentiment === "positive") {
    label = "Positive";
    style = POSITIVE;
  } else if (sentiment === "negative") {
    label = "Negative";
    style = NEGATIVE;
  }
  return (
    <span
      className="inline-flex items-center px-2 py-0.5 text-[12px] font-semibold rounded-full"
      style={style}
    >
      {label}
    </span>
  );
}
