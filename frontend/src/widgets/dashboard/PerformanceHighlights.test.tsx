import { screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { fetchHighlights } from "./api";
import { PerformanceHighlights } from "./PerformanceHighlights";
import { exactText, renderWithClient } from "./testUtils";
import type { HighlightsResponse } from "./types";

vi.mock("./api", () => ({ fetchHighlights: vi.fn() }));

const DATES = { range: "30d" as const, date_from: "2026-10-15", date_to: "2026-11-13" };

const DATA: HighlightsResponse = {
  top: { shop_id: 1, shop_name: "Trivandrum", avg_rating: 4.8, positive_count: 44, negative_count: 2, review_count: 52 },
  bottom: { shop_id: 2, shop_name: "Calicut", avg_rating: 3.3, positive_count: 15, negative_count: 13, review_count: 38 },
};

describe("Highlight cards", () => {
  afterEach(() => vi.mocked(fetchHighlights).mockReset());

  it("should show badge, name, rating and counts for both cards", async () => {
    vi.mocked(fetchHighlights).mockResolvedValue(DATA);
    renderWithClient(<PerformanceHighlights dateOnlyFilters={DATES} />);

    const top = await screen.findByRole("group", { name: "Top performer" });
    expect(within(top).getByText("Top performer")).toBeInTheDocument();
    expect(within(top).getByText("Trivandrum")).toBeInTheDocument();
    expect(within(top).getByRole("img", { name: "Average rating 4.8 out of 5" })).toBeInTheDocument();
    expect(
      within(top).getByText(exactText("4.8★ from 52 reviews · 44 positive · 2 negative")),
    ).toBeInTheDocument();

    const bottom = screen.getByRole("group", { name: "Needs attention" });
    expect(within(bottom).getByText("Calicut")).toBeInTheDocument();
    expect(
      within(bottom).getByText(exactText("3.3★ from 38 reviews · 15 positive · 13 negative")),
    ).toBeInTheDocument();
  });

  it("should render nothing when there is no top store", async () => {
    vi.mocked(fetchHighlights).mockResolvedValue({ top: null, bottom: null });
    const { container } = renderWithClient(<PerformanceHighlights dateOnlyFilters={DATES} />);
    await vi.waitFor(() => expect(fetchHighlights).toHaveBeenCalled());
    await vi.waitFor(() => expect(container).toBeEmptyDOMElement());
  });

  it("should show loading and error states", async () => {
    vi.mocked(fetchHighlights).mockReturnValue(new Promise(() => {}));
    const { unmount } = renderWithClient(<PerformanceHighlights dateOnlyFilters={DATES} />);
    expect(screen.getByLabelText("Loading highlights")).toBeInTheDocument();
    unmount();

    vi.mocked(fetchHighlights).mockRejectedValue(new Error("boom"));
    renderWithClient(<PerformanceHighlights dateOnlyFilters={DATES} />);
    expect(
      await screen.findByRole("button", { name: "Retry loading performance highlights" }),
    ).toBeInTheDocument();
  });
});
