import { BarChart2 } from "lucide-react";
import { useLayoutEffect, useRef, useState } from "react";

import { FOCUS, GREY, Panel, PanelError, PULSE, RED, TIP, YELLOW } from "./Panel";
import { assignLanes, ellipsize, ladderX } from "./panelMath";
import type { DashboardFilters, TopPerformingResponse, TopPerformingShop } from "./types";
import { useTopPerforming } from "./useTopPerforming";

interface Props {
  dateOnlyFilters: Pick<DashboardFilters, "range" | "date_from" | "date_to">;
  onSelect90d: () => void;
  /** Brand (all-store) average for the same date range, from /kpis/. */
  brandAvg: number | null;
}

type Side = "above" | "below" | null;

const LANE = 16; // px per label lane
const LINE_PAD = 14; // px between the line and the nearest lane
const BRAND_ID = -1;
const FALLBACK_WIDTH = 560;

function buildReviewsUrl(shopId: number, from: string | null, to: string | null): string {
  const p = new URLSearchParams();
  p.set("store", String(shopId));
  if (from) p.set("from", from);
  if (to) p.set("to", to);
  return `/admin/org/reviews/?${p.toString()}`;
}

/** Top 5 above, bottom 5 below, from the backend's `shops` split; overlap goes above. */
function ladderSides(response: TopPerformingResponse): Map<number, Side> {
  const top = response.shops.slice(0, 5);
  const bottom = response.split ? response.shops.slice(5) : response.shops.slice(-5);
  const sides = new Map<number, Side>();
  for (const s of bottom) sides.set(s.shop_id, "below");
  for (const s of top) sides.set(s.shop_id, "above");
  return sides;
}

function useWidth<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  const [width, setWidth] = useState(FALLBACK_WIDTH);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const measure = () => {
      if (el.clientWidth > 0) setWidth(el.clientWidth);
    };
    measure();
    if (typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return [ref, width] as const;
}

function labelText(s: TopPerformingShop): string {
  return `${ellipsize(s.shop_name)} ${s.avg_rating.toFixed(1)}`;
}

/** Centre a label on its dot, but keep it inside the ladder. */
function labelLeft(x: number, text: string, width: number): string {
  const half = (text.length * 6.4 + 4) / 2;
  const centre = Math.min(Math.max((x / 100) * width, half), width - half);
  return `${(centre / width) * 100}%`;
}

function tipAnchor(x: number): string {
  if (x < 20) return "left-0";
  if (x > 80) return "right-0";
  return "left-1/2 -translate-x-1/2";
}

function Ladder({
  response,
  brandAvg,
  dateOnlyFilters,
}: {
  response: TopPerformingResponse;
  brandAvg: number | null;
  dateOnlyFilters: Props["dateOnlyFilters"];
}) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const sides = ladderSides(response);

  // Every qualifying store; `shops` is merged in so a bottom-5 store past the
  // 200-dot cap still gets its dot.
  const byId = new Map<number, TopPerformingShop>();
  for (const s of response.all_stores ?? []) byId.set(s.shop_id, s);
  for (const s of response.shops) if (!byId.has(s.shop_id)) byId.set(s.shop_id, s);
  // Unlabelled first so labelled dots paint on top.
  const stores = [...byId.values()].sort(
    (a, b) => Number(sides.has(a.shop_id)) - Number(sides.has(b.shop_id)),
  );

  const brandText = brandAvg != null ? `brand ${brandAvg.toFixed(1)}` : null;
  const labelled = (side: Side) =>
    stores
      .filter((s) => sides.get(s.shop_id) === side)
      .map((s) => ({ id: s.shop_id, x: ladderX(s.avg_rating), text: labelText(s) }));
  const aboveInput = labelled("above");
  if (brandText && brandAvg != null) aboveInput.push({ id: BRAND_ID, x: ladderX(brandAvg), text: brandText });
  const above = assignLanes(aboveInput, width);
  const below = assignLanes(labelled("below"), width);

  const lanesAbove = Math.max(0, ...above.values()) + (above.size ? 1 : 0);
  const lanesBelow = Math.max(0, ...below.values()) + (below.size ? 1 : 0);
  const lineY = 8 + lanesAbove * LANE + LINE_PAD;
  const axisY = lineY + LINE_PAD + lanesBelow * LANE + 6;
  const height = axisY + 16;

  return (
    <div ref={ref} className="relative w-full" style={{ height }}>
      {/* the 3★–5★ line */}
      <div className="absolute inset-x-0 h-0.5 rounded bg-[#2F2F2F]" style={{ top: lineY - 1 }} />

      {/* axis ticks */}
      <div
        className="absolute inset-x-0 flex justify-between text-[10.5px] text-[#71717A] tabular-nums"
        style={{ top: axisY }}
        aria-hidden="true"
      >
        <span>3.0★</span>
        <span>4.0★</span>
        <span>5.0★</span>
      </div>

      {brandText && brandAvg != null && (
        <>
          <div
            aria-hidden="true"
            className="absolute w-0.5 -translate-x-1/2 bg-white"
            style={{ left: `${ladderX(brandAvg)}%`, top: lineY - 12, height: 24 }}
          />
          <span
            data-testid="ladder-brand"
            className="absolute -translate-x-1/2 whitespace-nowrap text-[10.5px] font-medium text-white tabular-nums"
            style={{
              left: labelLeft(ladderX(brandAvg), brandText, width),
              top: lineY - LINE_PAD - (above.get(BRAND_ID)! + 1) * LANE,
            }}
          >
            {brandText}
          </span>
        </>
      )}

      {stores.map((s) => {
        const side = sides.get(s.shop_id) ?? null;
        const x = ladderX(s.avg_rating);
        const color = side === "above" ? YELLOW : side === "below" ? RED : GREY;
        const size = side ? 14 : 10;
        const text = labelText(s);
        const lane = side === "above" ? above.get(s.shop_id)! : side === "below" ? below.get(s.shop_id)! : 0;
        return (
          <div key={s.shop_id}>
            <a
              data-testid="ladder-dot"
              href={buildReviewsUrl(s.shop_id, dateOnlyFilters.date_from, dateOnlyFilters.date_to)}
              aria-label={`${s.shop_name}, ${s.avg_rating.toFixed(1)} stars, ${s.review_count} reviews`}
              className={`group absolute z-10 flex size-6 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full hover:z-30 focus-visible:z-30 ${FOCUS}`}
              style={{ left: `${x}%`, top: lineY }}
            >
              <span
                aria-hidden="true"
                className="block rounded-full motion-safe:transition-transform group-hover:scale-125"
                style={{
                  width: size,
                  height: size,
                  background: color,
                  boxShadow: side ? "0 0 0 2px #141414" : undefined,
                }}
              />
              <span role="tooltip" className={`${TIP} bottom-full mb-1.5 ${tipAnchor(x)}`}>
                <span className="block font-semibold text-white">{s.shop_name}</span>
                <span className="tabular-nums">
                  <strong className="text-[13px] text-white">{s.avg_rating.toFixed(2)}★</strong> ·{" "}
                  {s.review_count} reviews
                  {s.avg_rating < 3 && " · below 3★, shown at the end"}
                </span>
              </span>
            </a>
            {side && (
              <span
                data-testid="ladder-label"
                data-side={side}
                data-lane={lane}
                aria-hidden="true"
                className="absolute -translate-x-1/2 whitespace-nowrap text-[11px] font-medium tabular-nums"
                style={{
                  color,
                  left: labelLeft(x, text, width),
                  top:
                    side === "above"
                      ? lineY - LINE_PAD - (lane + 1) * LANE
                      : lineY + LINE_PAD + lane * LANE - 2,
                }}
              >
                {text}
              </span>
            )}
          </div>
        );
      })}
    </div>
  );
}

export function TopPerformingSection({ dateOnlyFilters, onSelect90d, brandAvg }: Props) {
  const topQuery = useTopPerforming(dateOnlyFilters);
  const response = topQuery.data;

  return (
    <Panel
      title="Best and weakest stores"
      subtitle="Every store on one line by average rating. Top 5 named above, bottom 5 below. Stores need 3+ reviews; date range only, store filter not applied."
      busy={topQuery.isLoading}
      className="lg:flex-[1.6]"
    >
      {topQuery.isLoading && (
        <div aria-label="Loading store ladder" className={`h-[120px] rounded-xl ${PULSE}`} />
      )}

      {topQuery.isError && (
        <PanelError onRetry={() => void topQuery.refetch()} retryLabel="Retry loading store ladder" />
      )}

      {!topQuery.isLoading && !topQuery.isError && (!response || response.shops.length === 0) && (
        <div className="py-8 text-center">
          <BarChart2 className="mx-auto mb-3 size-8 text-[#52525B]" aria-hidden="true" />
          <h3 className="text-[15px] font-semibold text-white">No qualifying stores in this period</h3>
          <p className="mt-1.5 text-[13px] text-[#A1A1AA]">
            Stores need at least 3 reviews in the selected period.
          </p>
          <button
            type="button"
            onClick={onSelect90d}
            className={`mt-4 inline-flex items-center rounded-lg bg-[#FACC15] px-4 py-2 text-[13px] font-semibold text-black ${FOCUS}`}
          >
            View last 90 days
          </button>
        </div>
      )}

      {response && response.shops.length > 0 && !topQuery.isError && (
        <Ladder response={response} brandAvg={brandAvg} dateOnlyFilters={dateOnlyFilters} />
      )}
    </Panel>
  );
}
