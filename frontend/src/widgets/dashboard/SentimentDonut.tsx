import { Loader2, MessageCircle } from "lucide-react";
import { Fragment, useState } from "react";

import { FOCUS, GREY, Panel, PanelError, PULSE, RED, YELLOW } from "./Panel";
import { toHundred } from "./panelMath";
import type { DashboardFilters, SentimentResponse } from "./types";
import { useSentiment } from "./useSentiment";

// Kept as `SentimentDonut` so imports stay stable; it now draws a 100-square grid.

type Key = "positive" | "neutral" | "negative";
const KEYS: Key[] = ["positive", "neutral", "negative"];
const COLOR: Record<Key, string> = { positive: YELLOW, neutral: GREY, negative: RED };

interface Props {
  filters: DashboardFilters;
}

function negativeReviewsUrl(filters: DashboardFilters): string {
  const p = new URLSearchParams();
  p.set("sentiment", "negative");
  if (filters.shop_id) p.set("store", String(filters.shop_id));
  if (filters.date_from) p.set("from", filters.date_from);
  if (filters.date_to) p.set("to", filters.date_to);
  return `/admin/org/reviews/?${p.toString()}`;
}

function Grid({ data }: { data: SentimentResponse }) {
  const [hover, setHover] = useState<Key | null>(null);
  const pct = toHundred(KEYS.map((k) => data[k]));
  const share: Record<Key, number> = { positive: pct[0], neutral: pct[1], negative: pct[2] };
  const squares = KEYS.flatMap((k) => Array.from({ length: share[k] }, () => k));
  const summary = `${share.positive} positive, ${share.neutral} neutral, ${share.negative} negative`;

  return (
    <>
      <div className="relative w-full max-w-[520px]">
        <div
          role="img"
          aria-label={`Sentiment per 100 reviews: ${summary}`}
          className="grid grid-cols-[repeat(20,minmax(0,1fr))] gap-[3px]"
          onPointerLeave={() => setHover(null)}
        >
          {squares.map((k, i) => (
            <span
              key={i}
              data-testid="sentiment-square"
              data-sentiment={k}
              aria-hidden="true"
              onPointerEnter={() => setHover(k)}
              className="aspect-square rounded-[2px] motion-safe:transition-opacity"
              style={{ background: COLOR[k], opacity: hover && hover !== k ? 0.3 : 1 }}
            />
          ))}
        </div>
        {hover && (
          <div
            role="tooltip"
            className="pointer-events-none absolute left-1/2 top-1/2 z-20 -translate-x-1/2 -translate-y-1/2 rounded-lg border border-[#333] bg-[#1C1C1C] px-2.5 py-1.5 text-[12px] text-[#A1A1AA] shadow-lg whitespace-nowrap"
          >
            <strong className="text-[14px] font-semibold text-white tabular-nums">
              {data[hover].toLocaleString()}
            </strong>{" "}
            {hover} reviews ({share[hover]} in every 100)
          </div>
        )}
      </div>

      <p className="mt-3 text-[12px] leading-6 text-[#A1A1AA]">
        {KEYS.map((k, i) => (
          <Fragment key={k}>
            <span className="whitespace-nowrap">
              <span
                aria-hidden="true"
                className="mr-1.5 inline-block size-2.5 rounded-[2px] align-[-1px]"
                style={{ background: COLOR[k] }}
              />
              <strong className="text-[16px] font-semibold text-white tabular-nums">{share[k]}</strong>{" "}
              {k}
            </span>
            {i < KEYS.length - 1 && ", "}
          </Fragment>
        ))}
      </p>
    </>
  );
}

export function SentimentDonut({ filters }: Props) {
  const { data, isLoading, isError, refetch } = useSentiment(filters);
  const ready = !isLoading && !isError && data;

  const subtitle =
    ready && data.enriched_count > 0
      ? `Every 100 reviews, from ${data.enriched_count.toLocaleString()} analysed (${data.coverage_pct}%)`
      : "AI-derived sentiment of reviews in this period";

  return (
    <Panel title="Sentiment" subtitle={subtitle} busy={isLoading} className="lg:flex-1">
      {isLoading && (
        <div
          aria-label="Loading sentiment data"
          className="grid w-full max-w-[520px] grid-cols-[repeat(20,minmax(0,1fr))] gap-[3px]"
        >
          {Array.from({ length: 100 }, (_, i) => (
            <span key={i} className={`aspect-square rounded-[2px] ${PULSE}`} />
          ))}
        </div>
      )}

      {isError && (
        <PanelError
          onRetry={() => void refetch()}
          retryLabel="Retry loading Sentiment Distribution"
        />
      )}

      {ready && data.total_count === 0 && (
        <p className="py-10 text-center text-[13px] text-[#A1A1AA]">
          No reviews to analyze in this period.
        </p>
      )}

      {ready && data.total_count > 0 && data.enriched_count === 0 && (
        <div className="py-10 text-center">
          <Loader2
            className="mx-auto mb-2 size-6 text-[#71717A] motion-safe:animate-spin"
            aria-hidden="true"
          />
          <p className="text-[13px] text-[#A1A1AA]">Sentiment analysis in progress.</p>
        </div>
      )}

      {ready && data.enriched_count > 0 && (
        <>
          <Grid data={data} />

          {data.coverage_pct < 50 && (
            <p className="mt-2 inline-flex items-center gap-1 text-[11.5px] text-[#71717A]">
              <Loader2 className="size-3 motion-safe:animate-spin" aria-hidden="true" />
              Analysis in progress.
            </p>
          )}

          <div className="mt-auto pt-3.5">
            <a
              href={negativeReviewsUrl(filters)}
              className={`inline-flex items-center gap-1.5 text-[12.5px] font-semibold text-[#FACC15] underline underline-offset-2 ${FOCUS}`}
            >
              <MessageCircle size={14} aria-hidden="true" />
              See negative reviews
            </a>
          </div>
        </>
      )}
    </Panel>
  );
}
