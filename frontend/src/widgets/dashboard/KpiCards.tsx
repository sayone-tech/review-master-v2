import { Sparkline } from "./Sparkline";
import { StarMeter } from "./StarMeter";
import type { DashboardFilters, KpisResponse } from "./types";
import { useKpis } from "./useKpis";

interface Props {
  filters: DashboardFilters;
  shopNameIfSingle: string | null;
}

const YELLOW = "#FACC15";
const RED = "#F87171";
const MINUS = "−";
const EMPTY = "No reviews in this period";

const BAND =
  "grid grid-cols-2 lg:grid-cols-[1.2fr_1.4fr_1fr_1fr] gap-px bg-[#232323] rounded-[14px] overflow-hidden mb-[18px] text-white";
const CELL = "bg-[#0A0A0A] px-4 py-4 sm:px-[18px] flex flex-col min-w-0";
const NUM = "text-[30px] font-bold leading-none tracking-[-0.02em] tabular-nums";
const LABEL = "text-[12px] text-[#8A8A93] mt-1.5";

// ── Change lines ────────────────────────────────────────────────────────────
// Each returns null when there is nothing honest to compare against, so the
// line is hidden rather than showing NaN / Infinity.

type Change = { dir: "up" | "down" | "flat"; text: string } | null;

const SUFFIX = " vs previous period";

function signed(n: number, body: string): Change {
  if (n === 0) return { dir: "flat", text: `No change${SUFFIX}` };
  return { dir: n > 0 ? "up" : "down", text: `${n > 0 ? "+" : MINUS}${body}${SUFFIX}` };
}

function percentChange(cur: number, prev: number | null | undefined): Change {
  if (prev == null || prev === 0 || !Number.isFinite(cur)) return null;
  const pct = Math.round(((cur - prev) / prev) * 100);
  return signed(pct, `${Math.abs(pct)}%`);
}

function starChange(cur: number, prev: number | null | undefined): Change {
  if (prev == null || !Number.isFinite(cur)) return null;
  const d = Math.round((cur - prev) * 10) / 10;
  return signed(d, `${Math.abs(d).toFixed(1)}★`);
}

function pointChange(cur: number, prev: number | null | undefined): Change {
  if (prev == null || !Number.isFinite(cur)) return null;
  const d = Math.round(cur - prev);
  return signed(d, `${Math.abs(d)} ${Math.abs(d) === 1 ? "pt" : "pts"}`);
}

function ChangeLine({ change }: { change: Change }) {
  if (!change) return null;
  // Neutral ink: the sign and arrow carry direction, never colour alone.
  return (
    <p className="mt-2 text-[11.5px] font-medium text-[#A1A1AA] tabular-nums">
      {change.dir !== "flat" && (
        <span aria-hidden="true" className="mr-1 text-[9px]">
          {change.dir === "up" ? "▲" : "▼"}
        </span>
      )}
      {change.text}
    </p>
  );
}

// ── Parts ───────────────────────────────────────────────────────────────────

function Part({ name, children }: { name: string; children: React.ReactNode }) {
  return (
    <div role="group" aria-label={name} className={CELL}>
      {children}
    </div>
  );
}

function scopeLabel(data: KpisResponse, shopNameIfSingle: string | null): string {
  if (data.store_count > 1) return `reviews across ${data.store_count} stores`;
  return shopNameIfSingle ? `reviews at ${shopNameIfSingle}` : "reviews";
}

function Band({ data, shopNameIfSingle }: { data: KpisResponse; shopNameIfSingle: string | null }) {
  const isEmpty = data.total_reviews === 0;
  // No comparison for "all time", an empty previous window, or an empty current one.
  const prev = !isEmpty && data.previous && data.previous.total_reviews > 0 ? data.previous : null;
  // Nothing analysed yet: negative_pct is 0 only because it is unknown, not because it is good.
  const noAnalysis = !isEmpty && data.enriched_count === 0;

  return (
    <section aria-label="Headline numbers" className={BAND}>
      <Part name="Total reviews">
        <div className={NUM}>{data.total_reviews.toLocaleString()}</div>
        <p className={LABEL}>{isEmpty ? EMPTY : scopeLabel(data, shopNameIfSingle)}</p>
        {!isEmpty && (
          <div className="mt-2">
            <Sparkline points={data.trend?.total_reviews ?? []} label="Reviews per period" color={YELLOW} />
          </div>
        )}
        <ChangeLine change={prev && percentChange(data.total_reviews, prev.total_reviews)} />
      </Part>

      <Part name="Average rating">
        <div className="flex flex-wrap items-baseline gap-x-2.5">
          <div className={NUM}>{isEmpty ? "—" : data.avg_rating.toFixed(1)}</div>
          <p className="text-[12px] text-[#8A8A93]">average rating</p>
        </div>
        <div className="mt-2">
          <StarMeter value={isEmpty ? 0 : data.avg_rating} size={20} />
        </div>
        {isEmpty && <p className={LABEL}>{EMPTY}</p>}
        <ChangeLine change={prev && starChange(data.avg_rating, prev.avg_rating)} />
      </Part>

      <Part name="Negative reviews">
        <div className={NUM} style={{ color: isEmpty || noAnalysis ? undefined : RED }}>
          {isEmpty || noAnalysis ? "—" : `${data.negative_pct}%`}
        </div>
        <p className={LABEL}>
          {isEmpty ? EMPTY : `negative reviews (${data.negative_reviews.toLocaleString()})`}
        </p>
        {!isEmpty && (
          <div className="mt-2">
            <Sparkline points={data.trend?.negative_pct ?? []} label="Negative share per period, percent" color={RED} />
          </div>
        )}
        <ChangeLine change={noAnalysis || !prev ? null : pointChange(data.negative_pct, prev.negative_pct)} />
      </Part>

      <Part name="Awaiting reply">
        <div className={NUM} style={{ color: YELLOW }}>
          {data.awaiting_reply.toLocaleString()}
        </div>
        <p className={LABEL}>awaiting a reply</p>
        {data.oldest_awaiting_days != null && (
          <p className="mt-2 text-[12px] text-[#8A8A93] tabular-nums">
            oldest {data.oldest_awaiting_days} {data.oldest_awaiting_days === 1 ? "day" : "days"}
          </p>
        )}
      </Part>
    </section>
  );
}

export function KpiCards({ filters, shopNameIfSingle }: Props) {
  const { data, isLoading, isError, refetch } = useKpis(filters);

  if (isLoading) {
    return (
      <div aria-label="Loading headline numbers" aria-busy="true" className={BAND}>
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className={`${CELL} gap-2 min-h-[112px]`}>
            <div className="h-7 w-14 rounded bg-[#1C1C1C] motion-safe:animate-[sk-pulse_1.6s_ease-in-out_infinite]" />
            <div className="h-2.5 w-24 rounded bg-[#1C1C1C] motion-safe:animate-[sk-pulse_1.6s_ease-in-out_infinite]" />
            <div className="mt-auto h-2.5 w-28 rounded bg-[#1C1C1C] motion-safe:animate-[sk-pulse_1.6s_ease-in-out_infinite]" />
          </div>
        ))}
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="mb-[18px] flex flex-wrap items-center gap-3 rounded-[14px] bg-[#0A0A0A] px-[18px] py-4 text-[13px] text-[#A1A1AA]">
        <p>Could not load the headline numbers.</p>
        <button
          type="button"
          onClick={() => void refetch()}
          className="font-semibold text-[#FACC15] underline underline-offset-2 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#FACC15]"
          aria-label="Retry loading headline numbers"
        >
          Retry
        </button>
      </div>
    );
  }

  return <Band data={data} shopNameIfSingle={shopNameIfSingle} />;
}
