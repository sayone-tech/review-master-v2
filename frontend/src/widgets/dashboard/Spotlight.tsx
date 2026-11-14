import { reviewsHref } from "../insights/api";
import type { Chapter, InsightItem } from "../insights/types";

import { useSpotlight } from "./useSpotlight";

const INSIGHTS_URL = "/admin/org/insights/";
const ROWS = 2;

const CHAPTER: Record<Chapter, { label: string; dot: string }> = {
  attention: { label: "Needs attention", dot: "#F87171" },
  good: { label: "Good news", dot: "#FACC15" },
};

const LINK =
  "underline underline-offset-2 decoration-1 font-semibold rounded-sm focus-visible:outline-2 focus-visible:outline-offset-2";

interface Props {
  /** Org Admin only; false means no fetch and no render. */
  enabled: boolean;
}

/**
 * Brand-wide strip of the latest insights: the top one in a yellow block,
 * the next two beside it on black, and a way into the Insights book.
 * Renders nothing while loading, on error, or when there are no insights.
 */
export function Spotlight({ enabled }: Props) {
  const { data } = useSpotlight(enabled);
  const items = data?.items ?? [];
  if (!enabled || items.length === 0) return null;

  const lead = items.find((i) => i.chapter === "attention") ?? items[0];
  const rows = items.filter((i) => i !== lead).slice(0, ROWS);
  const more = items.length - 1 - ROWS;

  return (
    <section
      aria-label="Insights spotlight"
      className="grid grid-cols-1 sm:grid-cols-[minmax(0,1fr)_minmax(0,1.6fr)] rounded-[14px] overflow-hidden bg-[#0A0A0A] text-white mb-[18px]"
    >
      <Lead item={lead} />

      <div className="flex flex-col justify-center gap-2.5 px-4 py-4 sm:px-[18px] min-w-0">
        {rows.length > 0 && (
          <ul aria-label="More insights" className="flex flex-col gap-2.5">
            {rows.map((item, i) => (
              <Row key={`${item.type}-${i}`} item={item} />
            ))}
          </ul>
        )}
        {/* Always a way into the book, even with nothing more to count. */}
        <a
          href={INSIGHTS_URL}
          className={`self-start text-[12.5px] text-[#A1A1AA] hover:text-white focus-visible:outline-white ${LINK}`}
        >
          {more > 0 ? `${more} more on the Insights page` : "Open Insights"}
        </a>
      </div>
    </section>
  );
}

function Lead({ item }: { item: InsightItem }) {
  return (
    <div
      role="region"
      aria-label="Top insight"
      className="bg-[#FACC15] text-[#0A0A0A] px-4 py-4 sm:px-[18px] flex flex-col gap-3 justify-between min-w-0"
    >
      <span className="text-[12px] font-semibold">{CHAPTER[item.chapter].label}</span>
      <div className="min-w-0">
        <div className="text-[34px] font-extrabold leading-none tracking-[-0.03em] tabular-nums break-words">
          {item.headline}
        </div>
        <p className="text-[13.5px] font-semibold leading-snug mt-1.5 break-words">{item.title}</p>
      </div>
      <a
        href={reviewsHref(item.link)}
        className={`self-start text-[12.5px] focus-visible:outline-[#0A0A0A] ${LINK}`}
      >
        {item.cta || "See reviews"}
      </a>
    </div>
  );
}

function Row({ item }: { item: InsightItem }) {
  const chapter = CHAPTER[item.chapter];
  return (
    <li className="flex items-baseline gap-2.5 text-[13px] leading-snug min-w-0">
      <span
        aria-hidden="true"
        className="w-[7px] h-[7px] rounded-full shrink-0 translate-y-[-1px]"
        style={{ background: chapter.dot }}
      />
      <span className="min-w-0 break-words">
        <span className="sr-only">{chapter.label}: </span>
        <span className="font-semibold">{item.title}</span>{" "}
        <a
          href={reviewsHref(item.link)}
          className={`text-[#FACC15] whitespace-nowrap focus-visible:outline-[#FACC15] ${LINK}`}
        >
          {item.cta || "See reviews"}
        </a>
      </span>
    </li>
  );
}
