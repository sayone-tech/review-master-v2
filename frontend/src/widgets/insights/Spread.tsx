import { reviewsHref } from "./api";
import type { InsightItem, InsightsBookData, InsightsCover } from "./types";
import { ACCENT, Visual } from "./Visual";

const plural = (n: number, one: string, many: string) =>
  `${n.toLocaleString("en-GB")} ${n === 1 ? one : many}`;

function formatDay(iso: string): string {
  const d = new Date(`${iso}T00:00:00Z`);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("en-GB", { day: "numeric", month: "short", timeZone: "UTC" });
}

export function CoverPage({
  cover,
  window: win,
  count,
}: {
  cover: InsightsCover;
  window: InsightsBookData["window"];
  count: number;
}) {
  const split = [
    cover.attention > 0 ? `${cover.attention} ${cover.attention === 1 ? "needs" : "need"} attention` : "",
    cover.good > 0 ? `${cover.good} good news` : "",
  ]
    .filter(Boolean)
    .join(", ");
  return (
    <>
      <p className="ib-cover-top">
        {win ? `Last 30 days, ${formatDay(win.from)} to ${formatDay(win.to)}` : "Last 30 days"}
      </p>
      <div>
        <h2 className="ib-cover-title">
          {cover.organisation},<br /> this month
        </h2>
        <p className="ib-cover-lede">
          {`${plural(count, "thing", "things")} worth knowing from ${plural(cover.reviews, "review", "reviews")} across ${plural(cover.stores, "store", "stores")}.`}
        </p>
      </div>
      <div className="ib-cover-foot">
        <span>{split}</span>
        <span aria-hidden="true">Turn the page ›</span>
      </div>
    </>
  );
}

export function ChapterLabel({ chapter }: { chapter: InsightItem["chapter"] }) {
  return (
    <span className="ib-chap" style={{ color: ACCENT[chapter] }}>
      <span aria-hidden="true">{chapter === "attention" ? "●" : "★"}</span>
      {chapter === "attention" ? "Needs attention" : "Good news"}
    </span>
  );
}

/** Right page: the story. */
export function StoryPage({ item, index, total }: { item: InsightItem; index: number; total: number }) {
  return (
    <>
      <ChapterLabel chapter={item.chapter} />
      <h3 className="ib-title">{item.title}</h3>
      <p className="ib-body">{item.body}</p>
      <div className="ib-cta-row">
        <a className="ib-cta" href={reviewsHref(item.link)}>
          {item.cta}
        </a>
      </div>
      <div className="ib-pgno">
        <span>{item.store || "All stores"}</span>
        <span>
          {index} / {total}
        </span>
      </div>
    </>
  );
}

/** Left page: headline number, visual, caption. */
export function VisualPage({ item }: { item: InsightItem }) {
  return (
    <div className="ib-bigvis">
      <p className="ib-headline" style={{ color: ACCENT[item.chapter] }}>
        {item.headline}
      </p>
      <Visual visual={item.visual} tone={item.chapter} storeName={item.store} />
      <p className="ib-caption">{item.caption}</p>
    </div>
  );
}

export function EndPage() {
  return (
    <div className="ib-end">
      <h3 className="ib-end-title">That&apos;s all for now</h3>
      <p className="ib-body">New insights arrive as new reviews come in.</p>
    </div>
  );
}
