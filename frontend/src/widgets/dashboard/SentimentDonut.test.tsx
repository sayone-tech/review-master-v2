import { screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { fetchSentiment } from "./api";
import { SentimentDonut } from "./SentimentDonut";
import { exactText, renderWithClient } from "./testUtils";
import type { DashboardFilters, SentimentResponse } from "./types";

vi.mock("./api", () => ({ fetchSentiment: vi.fn() }));

const FILTERS: DashboardFilters = {
  region_id: null,
  shop_id: null,
  range: "30d",
  date_from: "2026-10-15",
  date_to: "2026-11-13",
};

function sentiment(over: Partial<SentimentResponse> = {}): SentimentResponse {
  return {
    positive: 260,
    neutral: 82,
    negative: 46,
    enriched_count: 388,
    total_count: 413,
    coverage_pct: 94,
    ...over,
  };
}

describe("Sentiment grid", () => {
  afterEach(() => vi.mocked(fetchSentiment).mockReset());

  it("should render 100 squares split by largest-remainder rounding", async () => {
    vi.mocked(fetchSentiment).mockResolvedValue(sentiment());
    renderWithClient(<SentimentDonut filters={FILTERS} />);

    await screen.findByText(exactText("67 positive (260), 21 neutral (82), 12 negative (46)"));
    const squares = screen.getAllByTestId("sentiment-square");
    expect(squares).toHaveLength(100);
    const by = (k: string) => squares.filter((s) => s.dataset.sentiment === k).length;
    expect([by("positive"), by("neutral"), by("negative")]).toEqual([67, 21, 12]);
    // order: positive, then neutral, then negative
    expect(squares[0].dataset.sentiment).toBe("positive");
    expect(squares[67].dataset.sentiment).toBe("neutral");
    expect(squares[99].dataset.sentiment).toBe("negative");
  });

  it("should print counts with thousands separators in the legend", async () => {
    vi.mocked(fetchSentiment).mockResolvedValue(sentiment({ positive: 1204, neutral: 300, negative: 96 }));
    renderWithClient(<SentimentDonut filters={FILTERS} />);
    expect(await screen.findByText(/positive \(1,204\)/)).toBeInTheDocument();
  });

  it("should print how many reviews the grid is drawn from", async () => {
    vi.mocked(fetchSentiment).mockResolvedValue(sentiment());
    renderWithClient(<SentimentDonut filters={FILTERS} />);
    expect(await screen.findByText(/from 388 analysed \(94%\)/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /See negative reviews/ })).toBeInTheDocument();
  });

  it("should show the no-reviews note and no squares when nothing was reviewed", async () => {
    vi.mocked(fetchSentiment).mockResolvedValue(
      sentiment({ positive: 0, neutral: 0, negative: 0, enriched_count: 0, total_count: 0, coverage_pct: 0 }),
    );
    renderWithClient(<SentimentDonut filters={FILTERS} />);
    expect(await screen.findByText("No reviews to analyze in this period.")).toBeInTheDocument();
    expect(screen.queryAllByTestId("sentiment-square")).toHaveLength(0);
  });

  it("should show analysis in progress when reviews exist but none are analysed", async () => {
    vi.mocked(fetchSentiment).mockResolvedValue(
      sentiment({ positive: 0, neutral: 0, negative: 0, enriched_count: 0, coverage_pct: 0 }),
    );
    renderWithClient(<SentimentDonut filters={FILTERS} />);
    expect(await screen.findByText("Sentiment analysis in progress.")).toBeInTheDocument();
    expect(screen.queryAllByTestId("sentiment-square")).toHaveLength(0);
  });

  it("should show the loading placeholder while fetching", () => {
    vi.mocked(fetchSentiment).mockReturnValue(new Promise(() => {}));
    renderWithClient(<SentimentDonut filters={FILTERS} />);
    expect(screen.getByLabelText("Loading sentiment data")).toBeInTheDocument();
  });

  it("should offer a retry when loading fails", async () => {
    vi.mocked(fetchSentiment).mockRejectedValue(new Error("boom"));
    renderWithClient(<SentimentDonut filters={FILTERS} />);
    expect(
      await screen.findByRole("button", { name: "Retry loading Sentiment Distribution" }),
    ).toBeInTheDocument();
  });
});
