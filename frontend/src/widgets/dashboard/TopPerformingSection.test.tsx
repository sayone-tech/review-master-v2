import { fireEvent, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { fetchTopPerforming } from "./api";
import { renderWithClient } from "./testUtils";
import { TopPerformingSection } from "./TopPerformingSection";
import type { TopPerformingResponse, TopPerformingShop } from "./types";

vi.mock("./api", () => ({ fetchTopPerforming: vi.fn() }));

const DATES = { range: "30d" as const, date_from: "2026-10-15", date_to: "2026-11-13" };

function store(id: number, name: string, avg: number, count = 10): TopPerformingShop {
  return { shop_id: id, shop_name: name, avg_rating: avg, review_count: count };
}

// 12 stores, avg desc; the backend splits into top 5 + bottom 5.
const ALL = [
  store(1, "Trivandrum", 4.8, 52),
  store(2, "Kochi", 4.6),
  store(3, "Thrissur", 4.5),
  store(4, "Alappuzha", 4.4),
  store(5, "Kollam", 4.3),
  store(6, "Palakkad", 4.1),
  store(7, "Kottayam", 4.0),
  store(8, "Malappuram", 3.8),
  store(9, "Kasaragod", 3.6),
  store(10, "Wayanad", 3.4),
  store(11, "Kannur", 3.2),
  store(12, "Calicut", 2.4),
];

const SPLIT: TopPerformingResponse = {
  shops: [...ALL.slice(0, 5), ...ALL.slice(-5)],
  split: true,
  all_stores: ALL,
};

function renderLadder(brandAvg: number | null = 4.3, onSelect90d = () => {}) {
  return renderWithClient(
    <TopPerformingSection dateOnlyFilters={DATES} onSelect90d={onSelect90d} brandAvg={brandAvg} />,
  );
}

const dots = () => screen.getAllByTestId("ladder-dot");
const labels = () => screen.queryAllByTestId("ladder-label");

describe("Store rating ladder", () => {
  afterEach(() => vi.mocked(fetchTopPerforming).mockReset());

  it("should draw one dot per qualifying store, placed by rating", async () => {
    vi.mocked(fetchTopPerforming).mockResolvedValue(SPLIT);
    renderLadder();
    await screen.findAllByTestId("ladder-dot");

    expect(dots()).toHaveLength(12);
    const kottayam = screen.getByRole("link", { name: "Kottayam, 4.0 stars, 10 reviews" });
    expect(kottayam).toHaveStyle({ left: "50%" });
    expect(screen.getByRole("link", { name: "Trivandrum, 4.8 stars, 52 reviews" })).toHaveStyle({
      left: "90%",
    });
  });

  it("should label only the top 5 above and the bottom 5 below", async () => {
    vi.mocked(fetchTopPerforming).mockResolvedValue(SPLIT);
    renderLadder();
    await screen.findAllByTestId("ladder-dot");

    const above = labels().filter((l) => l.dataset.side === "above").map((l) => l.textContent);
    const below = labels().filter((l) => l.dataset.side === "below").map((l) => l.textContent);
    expect(above).toHaveLength(5);
    expect(below).toHaveLength(5);
    expect(above).toContain("Trivandrum 4.8");
    expect(below).toContain("Kannur 3.2");
    expect(labels().map((l) => l.textContent)).not.toContain("Palakkad 4.1");
  });

  it("should pin stores below 3 stars to the left end with their real value", async () => {
    vi.mocked(fetchTopPerforming).mockResolvedValue(SPLIT);
    renderLadder();
    const calicut = await screen.findByRole("link", { name: "Calicut, 2.4 stars, 10 reviews" });
    expect(calicut).toHaveStyle({ left: "0%" });
    expect(labels().map((l) => l.textContent)).toContain("Calicut 2.4");
  });

  it("should show the brand-average notch from the KPI average", async () => {
    vi.mocked(fetchTopPerforming).mockResolvedValue(SPLIT);
    renderLadder(4.3);
    const notch = await screen.findByTestId("ladder-brand");
    expect(notch).toHaveTextContent("brand 4.3");
    expect(notch).toHaveStyle({ left: "65%" });
  });

  it("should omit the notch when there is no brand average", async () => {
    vi.mocked(fetchTopPerforming).mockResolvedValue(SPLIT);
    renderLadder(null);
    await screen.findAllByTestId("ladder-dot");
    expect(screen.queryByTestId("ladder-brand")).not.toBeInTheDocument();
  });

  it("should label two close stores once each, above, on separate lanes", async () => {
    const two = [store(1, "Review Focus A", 4.5), store(2, "Review Focus B", 4.52)];
    vi.mocked(fetchTopPerforming).mockResolvedValue({ shops: two, split: false, all_stores: two });
    renderLadder(4.51);
    await screen.findAllByTestId("ladder-dot");

    expect(dots()).toHaveLength(2);
    expect(labels()).toHaveLength(2);
    expect(labels().every((l) => l.dataset.side === "above")).toBe(true);
    expect(new Set(labels().map((l) => l.dataset.lane)).size).toBe(2);
  });

  it("should still draw the shops when an old cached payload lacks all_stores", async () => {
    const two = [store(1, "Review Focus A", 4.5), store(2, "Review Focus B", 4.52)];
    vi.mocked(fetchTopPerforming).mockResolvedValue({ shops: two, split: false } as never);
    renderLadder(4.51);
    await screen.findAllByTestId("ladder-dot");
    expect(dots().length).toBeGreaterThan(0);
  });

  it("should work with a single store", async () => {
    const one = [store(1, "Only Store", 4.1)];
    vi.mocked(fetchTopPerforming).mockResolvedValue({ shops: one, split: false, all_stores: one });
    renderLadder(4.1);
    await screen.findAllByTestId("ladder-dot");
    expect(labels().map((l) => l.textContent)).toEqual(["Only Store 4.1"]);
  });

  it("should shorten long names and keep the full name in the tooltip", async () => {
    const one = [store(1, "Thiruvananthapuram Central", 4.6)];
    vi.mocked(fetchTopPerforming).mockResolvedValue({ shops: one, split: false, all_stores: one });
    renderLadder();
    await screen.findAllByTestId("ladder-dot");
    expect(labels()[0]).toHaveTextContent("Thiruvananthap… 4.6");
    expect(screen.getByRole("tooltip")).toHaveTextContent("Thiruvananthapuram Central");
  });

  it("should show the empty state with a 90-day shortcut", async () => {
    vi.mocked(fetchTopPerforming).mockResolvedValue({ shops: [], split: false, all_stores: [] });
    const onSelect90d = vi.fn();
    renderLadder(null, onSelect90d);
    expect(await screen.findByText("No qualifying stores in this period")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "View last 90 days" }));
    expect(onSelect90d).toHaveBeenCalled();
  });

  it("should show loading and error states", async () => {
    vi.mocked(fetchTopPerforming).mockReturnValue(new Promise(() => {}));
    const { unmount } = renderLadder();
    expect(screen.getByLabelText("Loading store ladder")).toBeInTheDocument();
    unmount();

    vi.mocked(fetchTopPerforming).mockRejectedValue(new Error("boom"));
    renderLadder();
    expect(await screen.findByRole("button", { name: "Retry loading store ladder" })).toBeInTheDocument();
  });
});

describe("Ladder tooltips", () => {
  afterEach(() => vi.mocked(fetchTopPerforming).mockReset());

  it("should keep tooltips out of layout until hovered and open them inward", async () => {
    vi.mocked(fetchTopPerforming).mockResolvedValue(SPLIT);
    renderLadder();
    await screen.findAllByTestId("ladder-dot");
    const tips = screen.getAllByRole("tooltip", { hidden: true });
    for (const t of tips) {
      // display:none until hover/focus (visibility:hidden would still widen the page)
      expect(t).toHaveClass("hidden", "group-hover:block", "group-focus-visible:block");
      expect(t).not.toHaveClass("invisible");
    }
    const tipOf = (name: RegExp) =>
      within(screen.getByRole("link", { name })).getByRole("tooltip", { hidden: true });
    expect(tipOf(/^Trivandrum/)).toHaveClass("right-0");
    expect(tipOf(/^Calicut/)).toHaveClass("left-0");
  });
});
