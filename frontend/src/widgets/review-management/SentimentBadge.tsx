import { AlertCircle, Loader2 } from "lucide-react";
import type { EnrichmentStatus, ReviewTag, Sentiment, TagPolarity } from "./types";

interface Props {
  sentiment: Sentiment;
  enrichmentStatus: EnrichmentStatus;
  tags?: ReviewTag[];
}

const POSITIVE = { backgroundColor: "#DCFCE7", color: "#16A34A" } as const;
const NEUTRAL = { backgroundColor: "#F4F4F5", color: "#52525B" } as const;
const NEGATIVE = { backgroundColor: "#FEE2E2", color: "#DC2626" } as const;
const ANALYZING = { backgroundColor: "#FEF3C7", color: "#D97706" } as const;

const TAG_STYLES: Record<TagPolarity, { backgroundColor: string; color: string }> = {
  positive: POSITIVE,
  neutral: NEUTRAL,
  negative: NEGATIVE,
};

const MAX_TAGS = 5;

export function SentimentBadge({ sentiment, enrichmentStatus, tags = [] }: Props) {
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
  const visibleTags = tags.slice(0, MAX_TAGS);
  return (
    <span className="inline-flex flex-wrap items-center gap-1">
      <span
        className="inline-flex items-center px-2 py-0.5 text-[12px] font-semibold rounded-full"
        style={style}
      >
        {label}
      </span>
      {visibleTags.map((tag) => (
        <span
          key={`${tag.label}-${tag.polarity}`}
          className="inline-flex items-center px-2 py-0.5 text-[12px] font-medium rounded-full"
          style={TAG_STYLES[tag.polarity]}
          title={tag.label}
        >
          {tag.label}
        </span>
      ))}
    </span>
  );
}
