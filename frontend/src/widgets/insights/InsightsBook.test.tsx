import { fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { InsightsBook } from "./InsightsBook";
import { Visual } from "./Visual";
import type { InsightItem, InsightsBookData } from "./types";

const WINDOW = { from: "2026-10-15", to: "2026-11-13" };

function item(over: Partial<InsightItem>): InsightItem {
  return {
    type: 1,
    chapter: "attention",
    headline: "1",
    title: "Title",
    body: "Body.",
    visual: { kind: "before_now", before: 1, now: 2 },
    link: { ...WINDOW },
    store: null,
    cta: "See reviews",
    caption: "Caption",
    ...over,
  };
}

const ITEMS: InsightItem[] = [
  item({
    type: 1,
    headline: "2×",
    title: "Wait time complaints doubled at Kochi",
    body: "9 reviews mentioned wait time in the last 30 days, up from 4.",
    visual: { kind: "before_now", before: 4, now: 9 },
    link: { store: 3, tags: "Wait time", sentiment: "negative", ...WINDOW },
    store: "Kochi",
    caption: "Reviews mentioning wait time at Kochi",
  }),
  item({
    type: 2,
    headline: "6",
    title: "Six unhappy customers are still waiting for a reply",
    visual: { kind: "waiting_days", days: [2, 3, 4, 6, 7, 9] },
    link: { sentiment: "negative", replied: "false", ...WINDOW },
    cta: "Reply now",
    caption: "Days each review has been waiting",
  }),
  item({
    type: 3,
    headline: "−1.0★",
    title: "Calicut is a full star below your brand",
    visual: { kind: "rating_line", store: 3.3, brand: 4.3 },
    link: { store: 5, ...WINDOW },
    store: "Calicut",
  }),
  item({
    type: 4,
    chapter: "good",
    headline: "62%",
    title: "Trivandrum earned more five-star reviews",
    visual: { kind: "share_line", points: [40, 44, 47, 52, 58, 62] },
    link: { store: 7, rating: 5, ...WINDOW },
    store: "Trivandrum",
  }),
  item({
    type: 5,
    chapter: "good",
    headline: "92%",
    title: "You answered almost every review",
    visual: { kind: "progress", before: 70, now: 92 },
  }),
  item({
    type: 6,
    chapter: "good",
    headline: "4.5★",
    title: "Kochi had its best month yet",
    visual: { kind: "monthly_bars", points: [4.0, 4.1, 3.9, 4.2, 4.3, 4.5] },
    store: "Kochi",
  }),
  item({
    type: 7,
    chapter: "good",
    headline: "7",
    title: "Customers started praising the new menu",
    visual: {
      kind: "store_bars",
      items: [
        { store: "Kochi", count: 4 },
        { store: "Calicut", count: 3 },
      ],
    },
  }),
];

const BOOK: InsightsBookData = {
  cover: { organisation: "Sayone", reviews: 412, stores: 4, attention: 3, good: 4 },
  window: WINDOW,
  items: ITEMS,
};

function mockMedia({ reduce = false, narrow = false } = {}) {
  vi.stubGlobal(
    "matchMedia",
    vi.fn((query: string) => ({
      matches:
        (query.includes("prefers-reduced-motion") && reduce) ||
        (query.includes("max-width") && narrow),
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      onchange: null,
      dispatchEvent: vi.fn(),
    })),
  );
}

function mockFetch(data: InsightsBookData) {
  const fn = vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => data });
  vi.stubGlobal("fetch", fn);
  return fn;
}

async function renderBook(data: InsightsBookData = BOOK) {
  const fetchFn = mockFetch(data);
  const utils = render(<InsightsBook />);
  return { ...utils, fetchFn };
}

const position = () => screen.getByTestId("book-position").textContent;
const book = () => screen.getByRole("region", { name: /insights book/i });

// jsdom has no PointerEvent; a MouseEvent subclass carries clientX like the real one.
if (typeof window.PointerEvent === "undefined") {
  class PointerEventShim extends window.MouseEvent {}
  Object.defineProperty(window, "PointerEvent", { value: PointerEventShim, configurable: true });
}

beforeEach(() => mockMedia());
afterEach(() => vi.unstubAllGlobals());

describe("InsightsBook", () => {
  it("fetches the insights API with same-origin credentials", async () => {
    const { fetchFn } = await renderBook();
    await screen.findByText("Cover");
    expect(fetchFn).toHaveBeenCalledWith(
      "/api/v1/insights/",
      expect.objectContaining({ credentials: "same-origin" }),
    );
  });

  it("shows the cover with the organisation copy and counts", async () => {
    await renderBook();
    expect(await screen.findByRole("heading", { name: /Sayone,\s*this month/ })).toBeInTheDocument();
    expect(
      screen.getByText("7 things worth knowing from 412 reviews across 4 stores."),
    ).toBeInTheDocument();
    expect(screen.getByText("3 need attention, 4 good news")).toBeInTheDocument();
    expect(position()).toBe("Cover");
  });

  it("next and previous buttons move between pages", async () => {
    await renderBook();
    await screen.findByText("Cover");
    fireEvent.click(screen.getByRole("button", { name: "Next page" }));
    expect(position()).toBe("Insight 1 of 7");
    expect(
      screen.getByRole("heading", { name: "Wait time complaints doubled at Kochi" }),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Previous page" }));
    expect(position()).toBe("Cover");
  });

  it("arrow keys turn pages when the book has focus", async () => {
    await renderBook();
    await screen.findByText("Cover");
    fireEvent.keyDown(book(), { key: "ArrowRight" });
    fireEvent.keyDown(book(), { key: "ArrowRight" });
    expect(position()).toBe("Insight 2 of 7");
    fireEvent.keyDown(book(), { key: "ArrowLeft" });
    expect(position()).toBe("Insight 1 of 7");
  });

  it("a swipe to the left turns to the next page", async () => {
    await renderBook();
    await screen.findByText("Cover");
    fireEvent.pointerDown(book(), { clientX: 300 });
    fireEvent.pointerUp(window, { clientX: 250 });
    expect(position()).toBe("Insight 1 of 7");
    fireEvent.pointerDown(book(), { clientX: 300 });
    fireEvent.pointerUp(window, { clientX: 280 });
    expect(position()).toBe("Insight 1 of 7");
    fireEvent.pointerDown(book(), { clientX: 200 });
    fireEvent.pointerUp(window, { clientX: 260 });
    expect(position()).toBe("Cover");
  });

  it("announces each spread's title politely", async () => {
    await renderBook();
    await screen.findByText("Cover");
    fireEvent.click(screen.getByRole("button", { name: "Next page" }));
    const live = screen.getByRole("status");
    expect(live).toHaveAttribute("aria-live", "polite");
    expect(live).toHaveTextContent("Insight 1 of 7: Wait time complaints doubled at Kochi");
  });

  it("chapter tab jumps to the first good item and is highlighted only in its chapter", async () => {
    await renderBook();
    await screen.findByText("Cover");
    const good = screen.getByRole("button", { name: "Good news" });
    const bad = screen.getByRole("button", { name: "Needs attention" });
    expect(good).not.toHaveAttribute("aria-current");
    expect(bad).not.toHaveAttribute("aria-current");

    fireEvent.click(good);
    expect(position()).toBe("Insight 4 of 7");
    expect(
      screen.getByRole("heading", { name: "Trivandrum earned more five-star reviews" }),
    ).toBeInTheDocument();
    expect(good).toHaveAttribute("aria-current", "true");
    expect(bad).not.toHaveAttribute("aria-current");

    fireEvent.click(bad);
    expect(position()).toBe("Insight 1 of 7");
    expect(bad).toHaveAttribute("aria-current", "true");
    expect(good).not.toHaveAttribute("aria-current");
  });

  it("a chapter with no items has no tab", async () => {
    await renderBook({ ...BOOK, items: ITEMS.slice(0, 3) });
    await screen.findByText("Cover");
    expect(screen.getByRole("button", { name: "Needs attention" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Good news" })).toBeNull();
  });

  it("ends on the end page", async () => {
    await renderBook();
    await screen.findByText("Cover");
    for (let i = 0; i < 10; i++) fireEvent.click(screen.getByRole("button", { name: "Next page" }));
    expect(position()).toBe("End");
    expect(screen.getByRole("heading", { name: "That's all for now" })).toBeInTheDocument();
    expect(screen.getByText("New insights arrive as new reviews come in.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Next page" })).toBeDisabled();
  });

  it("shows the empty state when there are no items", async () => {
    await renderBook({ cover: null, window: null, items: [] });
    expect(
      await screen.findByText("Not enough new reviews yet to spot changes."),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "Insights appear once your stores have more reviews in the last 30 days.",
      ),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Next page" })).toBeNull();
  });

  it("shows an error message when loading fails", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 500 }));
    render(<InsightsBook />);
    expect(await screen.findByText(/Insights could not be loaded/)).toBeInTheDocument();
  });

  it("action links open Reviews with the exact params", async () => {
    await renderBook();
    await screen.findByText("Cover");
    fireEvent.click(screen.getByRole("button", { name: "Next page" }));
    expect(screen.getByRole("link", { name: "See reviews" })).toHaveAttribute(
      "href",
      "/admin/org/reviews/?store=3&tags=Wait+time&sentiment=negative&from=2026-10-15&to=2026-11-13",
    );
    fireEvent.click(screen.getByRole("button", { name: "Next page" }));
    expect(screen.getByRole("link", { name: "Reply now" })).toHaveAttribute(
      "href",
      "/admin/org/reviews/?sentiment=negative&replied=false&from=2026-10-15&to=2026-11-13",
    );
  });

  it("shows the headline, visual and caption on the left page", async () => {
    await renderBook();
    await screen.findByText("Cover");
    fireEvent.click(screen.getByRole("button", { name: "Next page" }));
    const left = screen.getByTestId("visible-left");
    expect(within(left).getByText("2×")).toBeInTheDocument();
    expect(within(left).getByText("Reviews mentioning wait time at Kochi")).toBeInTheDocument();
    expect(within(left).getByText("9")).toBeInTheDocument();
  });

  it("turns animate by default and switch instantly with reduced motion", async () => {
    const { container, unmount } = await renderBook();
    await screen.findByText("Cover");
    const leaves = container.querySelectorAll(".ib-leaf");
    expect(leaves.length).toBe(8);
    leaves.forEach((l) => expect(l).toHaveClass("ib-anim"));
    unmount();

    mockMedia({ reduce: true });
    const second = await renderBook();
    await screen.findByText("Cover");
    second.container
      .querySelectorAll(".ib-leaf")
      .forEach((l) => expect(l).not.toHaveClass("ib-anim"));
  });

  it("shows one page per step on phones", async () => {
    mockMedia({ narrow: true });
    const { container } = await renderBook();
    await screen.findByText("Cover");
    expect(container.querySelectorAll(".ib-leaf").length).toBe(2 * 7 + 2);
    const next = screen.getByRole("button", { name: "Next page" });

    fireEvent.click(next);
    expect(position()).toBe("Insight 1 of 7");
    expect(screen.getByTestId("visible-page")).toHaveTextContent("2×");
    expect(
      screen.queryByRole("heading", { name: "Wait time complaints doubled at Kochi" }),
    ).toBeNull();

    fireEvent.click(next);
    expect(position()).toBe("Insight 1 of 7");
    expect(
      screen.getByRole("heading", { name: "Wait time complaints doubled at Kochi" }),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Good news" }));
    expect(position()).toBe("Insight 4 of 7");
    expect(screen.getByTestId("visible-page")).toHaveTextContent("62%");
  });
});

describe("Visual", () => {
  it("before_now labels both numbers", () => {
    render(<Visual visual={{ kind: "before_now", before: 4, now: 9 }} tone="attention" />);
    expect(screen.getByText("Before")).toBeInTheDocument();
    expect(screen.getByText("4")).toBeInTheDocument();
    expect(screen.getByText("9")).toBeInTheDocument();
  });

  it("waiting_days labels every review's days", () => {
    render(<Visual visual={{ kind: "waiting_days", days: [2, 5, 9] }} tone="attention" />);
    for (const d of ["2d", "5d", "9d"]) expect(screen.getByText(d)).toBeInTheDocument();
  });

  it("rating_line labels the store and the brand", () => {
    render(
      <Visual visual={{ kind: "rating_line", store: 3.3, brand: 4.3 }} tone="attention" storeName="Calicut" />,
    );
    expect(screen.getByText("Calicut 3.3")).toBeInTheDocument();
    expect(screen.getByText("Brand 4.3")).toBeInTheDocument();
  });

  it("share_line labels the first and latest share", () => {
    render(
      <Visual visual={{ kind: "share_line", points: [40, 44, 47, 52, 58, 62] }} tone="good" />,
    );
    expect(screen.getByText("40%")).toBeInTheDocument();
    expect(screen.getByText("62%")).toBeInTheDocument();
  });

  it("progress labels before and now", () => {
    render(<Visual visual={{ kind: "progress", before: 70, now: 92 }} tone="good" />);
    expect(screen.getByText("Before 70%")).toBeInTheDocument();
    expect(screen.getByText("92%")).toBeInTheDocument();
  });

  it("monthly_bars labels every month", () => {
    render(
      <Visual visual={{ kind: "monthly_bars", points: [4.0, 4.1, 3.9, 4.2, 4.3, 4.5] }} tone="good" />,
    );
    for (const v of ["4.0", "4.1", "3.9", "4.2", "4.3", "4.5"])
      expect(screen.getByText(v)).toBeInTheDocument();
  });

  it("store_bars labels every store and count", () => {
    render(
      <Visual
        visual={{ kind: "store_bars", items: [{ store: "Kochi", count: 4 }, { store: "Calicut", count: 3 }] }}
        tone="good"
      />,
    );
    expect(screen.getByText("Kochi")).toBeInTheDocument();
    expect(screen.getByText("Calicut")).toBeInTheDocument();
    expect(screen.getByText("4")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
  });

  it("every visual has an accessible description", () => {
    render(<Visual visual={{ kind: "before_now", before: 4, now: 9 }} tone="attention" />);
    expect(screen.getByRole("img", { name: "Before 4, now 9" })).toBeInTheDocument();
  });
});
