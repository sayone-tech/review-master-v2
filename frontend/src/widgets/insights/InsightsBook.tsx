import { ChevronLeft, ChevronRight } from "lucide-react";
import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from "react";

import { fetchInsights } from "./api";
import { BOOK_CSS } from "./bookStyles";
import { CoverPage, EndPage, StoryPage, VisualPage } from "./Spread";
import type { Chapter, InsightItem, InsightsBookData } from "./types";
import { useBook } from "./useBook";

const SWIPE_PX = 40;

function useMediaQuery(query: string): boolean {
  const get = () =>
    typeof window !== "undefined" && typeof window.matchMedia === "function"
      ? window.matchMedia(query).matches
      : false;
  const [matches, setMatches] = useState(get);
  useEffect(() => {
    if (typeof window.matchMedia !== "function") return;
    const mql = window.matchMedia(query);
    const onChange = () => setMatches(mql.matches);
    onChange();
    mql.addEventListener?.("change", onChange);
    return () => mql.removeEventListener?.("change", onChange);
  }, [query]);
  return matches;
}

type LoadState =
  | { status: "loading" }
  | { status: "error" }
  | { status: "ready"; data: InsightsBookData };

function Shell({ children, narrow = false }: { children: ReactNode; narrow?: boolean }) {
  return (
    <div className={`ib${narrow ? " ib-narrow" : ""}`}>
      <style>{BOOK_CSS}</style>
      <div className="ib-stage">{children}</div>
    </div>
  );
}

export function InsightsBook() {
  const [state, setState] = useState<LoadState>({ status: "loading" });

  useEffect(() => {
    const ctrl = new AbortController();
    fetchInsights(ctrl.signal)
      .then((data) => setState({ status: "ready", data }))
      .catch((err: unknown) => {
        if ((err as { name?: string })?.name !== "AbortError") setState({ status: "error" });
      });
    return () => ctrl.abort();
  }, []);

  if (state.status === "loading") {
    return (
      <Shell>
        <div className="ib-book" aria-busy="true" style={{ cursor: "default" }}>
          <div className="ib-skeleton" style={{ position: "absolute", inset: 0 }} />
          <span className="sr-only">Loading insights</span>
        </div>
      </Shell>
    );
  }
  if (state.status === "error") {
    return (
      <Shell>
        <div className="ib-empty" role="alert">
          <p className="ib-empty-title">Insights could not be loaded.</p>
          <p className="ib-body">Refresh the page to try again.</p>
        </div>
      </Shell>
    );
  }
  const { data } = state;
  if (!data.cover || data.items.length === 0) {
    return (
      <Shell>
        <div className="ib-empty">
          <h2 className="ib-empty-title">Not enough new reviews yet to spot changes.</h2>
          <p className="ib-body">
            Insights appear once your stores have more reviews in the last 30 days.
          </p>
        </div>
      </Shell>
    );
  }
  return <Book data={data} />;
}

/** A page's visibility: hidden pages are removed from the a11y tree and tab order. */
function faceProps(visible: boolean, testId: string) {
  return {
    "aria-hidden": !visible,
    inert: !visible,
    "data-testid": visible ? testId : undefined,
  };
}

/** Stacked paper on one side of the book: max 6 layers. */
function edges(layers: number, dir: 1 | -1): string {
  if (layers <= 0) return "none";
  return Array.from(
    { length: Math.min(6, layers) },
    (_, i) => `${dir * (i + 1) * 2}px ${i + 1}px 0 -1px ${i % 2 ? "#0d0d0d" : "#222"}`,
  ).join(",");
}

function Book({ data }: { data: InsightsBookData }) {
  const items = data.items;
  const cover = data.cover!;
  const N = items.length;
  const narrow = useMediaQuery("(max-width: 767px)");
  const reduce = useMediaQuery("(prefers-reduced-motion: reduce)");
  const { page, next, prev, jump } = useBook(narrow ? 2 * N : N);

  // Keep the reader on the same insight when the layout switches.
  const lastPage = useRef({ page, narrow });
  useEffect(() => {
    const was = lastPage.current;
    if (was.narrow !== narrow) {
      const p = was.page;
      if (narrow) jump(p === 0 ? 0 : p > N ? 2 * N + 1 : 2 * p - 1);
      else jump(p === 0 ? 0 : p > 2 * N ? N + 1 : Math.ceil(p / 2));
    }
  }, [narrow, N, jump]);
  useEffect(() => {
    lastPage.current = { page, narrow };
  });

  const last = narrow ? 2 * N + 1 : N + 1;
  const spread = narrow ? (page === 0 ? 0 : page === last ? N + 1 : Math.ceil(page / 2)) : page;
  const current: InsightItem | undefined = spread >= 1 && spread <= N ? items[spread - 1] : undefined;
  const label =
    spread === 0 ? "Cover" : spread > N ? "End" : `Insight ${spread} of ${N}`;
  const announcement =
    spread === 0
      ? `Cover: ${cover.organisation}, this month`
      : spread > N
        ? "End: That's all for now"
        : `${label}: ${current!.title}`;

  const firstOf = (c: Chapter) => items.findIndex((it) => it.chapter === c) + 1;
  const goChapter = (c: Chapter) => {
    const s = firstOf(c);
    jump(narrow ? 2 * s - 1 : s);
  };

  // Swipe / drag: pointerdown on the book, pointerup anywhere.
  const startX = useRef<number | null>(null);
  useEffect(() => {
    const up = (e: PointerEvent) => {
      if (startX.current === null) return;
      const dx = e.clientX - startX.current;
      startX.current = null;
      if (dx < -SWIPE_PX) next();
      else if (dx > SWIPE_PX) prev();
    };
    const cancel = () => {
      startX.current = null;
    };
    window.addEventListener("pointerup", up);
    window.addEventListener("pointercancel", cancel);
    return () => {
      window.removeEventListener("pointerup", up);
      window.removeEventListener("pointercancel", cancel);
    };
  }, [next, prev]);

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowRight") {
      e.preventDefault();
      next();
    } else if (e.key === "ArrowLeft") {
      e.preventDefault();
      prev();
    }
  };

  const leafClass = (turned: boolean) =>
    `ib-leaf${reduce ? "" : " ib-anim"}${turned ? " ib-turned" : ""}`;
  const leafStyle = (j: number, turned: boolean): CSSProperties => ({
    zIndex: turned ? 100 + j : 300 - j,
  });

  let leaves: ReactNode[];
  if (narrow) {
    // Pages: cover, (visual, story) per insight, end.
    const pages: { key: string; node: ReactNode; className: string }[] = [
      {
        key: "cover",
        className: "ib-face ib-cover",
        node: <CoverPage cover={cover} window={data.window} count={N} />,
      },
    ];
    items.forEach((it, i) => {
      pages.push({ key: `v${i}`, className: "ib-face ib-solo-visual", node: <VisualPage item={it} /> });
      pages.push({
        key: `s${i}`,
        className: "ib-face",
        node: <StoryPage item={it} index={i + 1} total={N} />,
      });
    });
    pages.push({
      key: "end",
      className: "ib-face ib-solo-visual",
      node: <EndPage />,
    });
    leaves = pages.map((p, q) => {
      const turned = q < page;
      return (
        <div key={p.key} className={leafClass(turned)} style={leafStyle(q, turned)}>
          <div className={p.className} {...faceProps(q === page, "visible-page")}>
            {p.node}
          </div>
        </div>
      );
    });
  } else {
    // Leaf 0: front = cover, back = visual of insight 1.
    // Leaf j: front = story of insight j, back = visual of insight j+1 (last back = end page).
    leaves = Array.from({ length: N + 1 }, (_, j) => {
      const turned = j < page;
      const nextItem = items[j];
      return (
        <div key={j} className={leafClass(turned)} style={leafStyle(j, turned)}>
          <div
            className={`ib-face ib-front${j === 0 ? " ib-cover" : ""}`}
            {...faceProps(j === page, "visible-right")}
          >
            {j === 0 ? (
              <CoverPage cover={cover} window={data.window} count={N} />
            ) : (
              <StoryPage item={items[j - 1]} index={j} total={N} />
            )}
          </div>
          <div className="ib-face ib-back" {...faceProps(j === page - 1, "visible-left")}>
            {nextItem ? <VisualPage item={nextItem} /> : <EndPage />}
          </div>
        </div>
      );
    });
  }

  const remaining = narrow ? last - page : N + 1 - page;
  const chapters: { id: Chapter; name: string }[] = [
    { id: "attention", name: "Needs attention" },
    { id: "good", name: "Good news" },
  ];

  return (
    <Shell narrow={narrow}>
      <div
        className="ib-book"
        role="region"
        aria-roledescription="book"
        aria-label="Insights book. Use the left and right arrow keys to turn pages."
        tabIndex={0}
        onKeyDown={onKeyDown}
        onPointerDown={(e) => {
          startX.current = e.clientX;
        }}
      >
        {narrow ? (
          <div className="ib-bed" style={{ boxShadow: edges(remaining, 1) }} />
        ) : (
          <>
            <div className="ib-bed ib-bed-left" style={{ boxShadow: edges(page, -1) }} />
            <div className="ib-bed ib-bed-right" style={{ boxShadow: edges(remaining, 1) }} />
            <div className="ib-spine" />
          </>
        )}
        <div className="ib-tabs">
          {chapters
            .filter((c) => firstOf(c.id) > 0)
            .map((c) => {
              const on = current?.chapter === c.id;
              return (
                <button
                  key={c.id}
                  type="button"
                  className={`ib-tab ib-tab-${c.id}${on ? " ib-on" : ""}`}
                  aria-current={on ? "true" : undefined}
                  onPointerDown={(e) => e.stopPropagation()}
                  onClick={() => goChapter(c.id)}
                >
                  {c.name}
                </button>
              );
            })}
        </div>
        {leaves}
      </div>
      <div className="ib-ctrl">
        <button
          type="button"
          className="ib-nb"
          aria-label="Previous page"
          disabled={page === 0}
          onClick={prev}
        >
          <ChevronLeft size={18} aria-hidden="true" />
        </button>
        <span className="ib-pos" data-testid="book-position" aria-hidden="true">
          {label}
        </span>
        <button
          type="button"
          className="ib-nb"
          aria-label="Next page"
          disabled={page === last}
          onClick={next}
        >
          <ChevronRight size={18} aria-hidden="true" />
        </button>
      </div>
      <p role="status" aria-live="polite" className="sr-only">
        {announcement}
      </p>
    </Shell>
  );
}
