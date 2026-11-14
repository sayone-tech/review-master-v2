import { screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { fetchYourStore } from "./api";
import { renderWithClient } from "./testUtils";
import type { YourStoreResponse } from "./types";
import { YourStore } from "./YourStore";

vi.mock("./api", () => ({ fetchYourStore: vi.fn() }));

const DATES = { range: "30d" as const, date_from: "2026-10-15", date_to: "2026-11-13" };

const DATA: YourStoreResponse = {
  shop_id: 1,
  shop_name: "Kochi",
  region_name: "Central",
  avg_rating: 4.2,
  total_reviews: 100,
  positive_count: 70,
  positive_pct: 70,
  negative_count: 12,
  negative_pct: 12,
  distribution: { 1: 7, 2: 5, 3: 8, 4: 18, 5: 62 },
  trend_direction: "up",
  trend_delta: 0.2,
};

describe("Your Store", () => {
  afterEach(() => vi.mocked(fetchYourStore).mockReset());

  it("should show five bars from 5 stars to 1 star with percentages", async () => {
    vi.mocked(fetchYourStore).mockResolvedValue(DATA);
    renderWithClient(<YourStore dateOnlyFilters={DATES} />);

    await screen.findByText("Kochi");
    const bars = screen.getAllByTestId("star-bar");
    expect(bars).toHaveLength(5);
    expect(bars.map((b) => b.dataset.star)).toEqual(["5", "4", "3", "2", "1"]);
    expect(bars.map((b) => b.textContent)).toEqual(["5★ 62%", "4★ 18%", "3★ 8%", "2★ 5%", "1★ 7%"]);
    expect(screen.getByRole("img", { name: "Average rating 4.2 out of 5" })).toBeInTheDocument();
    expect(screen.getByText("100 reviews")).toBeInTheDocument();
  });

  it("should show loading and error states", async () => {
    vi.mocked(fetchYourStore).mockReturnValue(new Promise(() => {}));
    const { unmount } = renderWithClient(<YourStore dateOnlyFilters={DATES} />);
    expect(screen.getByLabelText("Loading your store")).toBeInTheDocument();
    unmount();

    vi.mocked(fetchYourStore).mockRejectedValue(new Error("boom"));
    renderWithClient(<YourStore dateOnlyFilters={DATES} />);
    expect(await screen.findByRole("button", { name: "Retry loading Your Store" })).toBeInTheDocument();
  });
});
