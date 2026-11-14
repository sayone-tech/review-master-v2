import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { fetchKpis } from "./api";

import { KpiCards } from "./KpiCards";
import { Sparkline } from "./Sparkline";
import { StarMeter } from "./StarMeter";
import type { DashboardFilters, KpisResponse } from "./types";

vi.mock("./api", () => ({ fetchKpis: vi.fn() }));

const FILTERS: DashboardFilters = {
  region_id: null,
  shop_id: null,
  range: "30d",
  date_from: "2026-10-15",
  date_to: "2026-11-13",
};

function kpis(over: Partial<KpisResponse> = {}): KpisResponse {
  return {
    total_reviews: 412,
    avg_rating: 4.3,
    negative_reviews: 49,
    negative_pct: 12,
    enriched_count: 388,
    store_count: 4,
    awaiting_reply: 17,
    previous: { total_reviews: 349, avg_rating: 4.1, negative_pct: 15, awaiting_reply: 20 },
    trend: {
      total_reviews: [50, 60, 62, 70, 80, 90],
      avg_rating: [4.0, 4.1, 4.2, 4.3, 4.3, 4.4],
      negative_pct: [15, 14, 13, 12, 12, 11],
    },
    oldest_awaiting_days: 9,
    ...over,
  };
}

function mockKpis(data: KpisResponse) {
  vi.mocked(fetchKpis).mockResolvedValue(data);
}

function renderBand(shopNameIfSingle: string | null = null) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <KpiCards filters={FILTERS} shopNameIfSingle={shopNameIfSingle} />
    </QueryClientProvider>,
  );
}

async function loaded() {
  await screen.findByRole("group", { name: "Total reviews" });
}

function part(name: string) {
  return screen.getByRole("group", { name });
}

describe("KpiCards headline band", () => {
  afterEach(() => {
    vi.mocked(fetchKpis).mockReset();
  });

  it("should show all four headline numbers when kpis load", async () => {
    mockKpis(kpis());
    renderBand();
    await loaded();

    expect(within(part("Total reviews")).getByText("412")).toBeInTheDocument();
    expect(within(part("Total reviews")).getByText(/across 4 stores/)).toBeInTheDocument();

    const avg = part("Average rating");
    expect(within(avg).getByText("4.3")).toBeInTheDocument();
    expect(within(avg).getByRole("img", { name: "Average rating 4.3 out of 5" })).toBeInTheDocument();

    const neg = part("Negative reviews");
    const pct = within(neg).getByText("12%");
    expect(pct).toHaveStyle({ color: "#F87171" });
    expect(within(neg).getByText(/negative reviews \(49\)/)).toBeInTheDocument();

    const wait = part("Awaiting reply");
    expect(within(wait).getByText("17")).toBeInTheDocument();
    expect(within(wait).getByText("oldest 9 days")).toBeInTheDocument();
  });

  it("should fill the star meter to the exact average when rating is 4.3", async () => {
    mockKpis(kpis());
    renderBand();
    await loaded();
    expect(screen.getByTestId("star-meter-fill")).toHaveStyle({ width: "86%" });
  });

  it("should show change lines when a previous period exists", async () => {
    mockKpis(kpis());
    renderBand();
    await loaded();
    // (412 - 349) / 349 = 18.05% -> +18%
    expect(within(part("Total reviews")).getByText("+18% vs previous period")).toBeInTheDocument();
    expect(within(part("Average rating")).getByText("+0.2★ vs previous period")).toBeInTheDocument();
    expect(within(part("Negative reviews")).getByText("−3 pts vs previous period")).toBeInTheDocument();
  });

  it("should say no change when values equal the previous period", async () => {
    mockKpis(kpis({ previous: { total_reviews: 412, avg_rating: 4.3, negative_pct: 12, awaiting_reply: 17 } }));
    renderBand();
    await loaded();
    expect(screen.getAllByText("No change vs previous period")).toHaveLength(3);
  });

  it("should hide change lines when previous is null", async () => {
    mockKpis(kpis({ previous: null }));
    renderBand();
    await loaded();
    expect(screen.queryByText(/vs previous period/)).not.toBeInTheDocument();
  });

  it("should hide a change line when its previous value is null or the previous total is 0", async () => {
    mockKpis(kpis({ previous: { total_reviews: 349, avg_rating: null, negative_pct: null, awaiting_reply: 3 } }));
    const { unmount } = renderBand();
    await loaded();
    expect(within(part("Total reviews")).getByText("+18% vs previous period")).toBeInTheDocument();
    expect(within(part("Average rating")).queryByText(/vs previous period/)).not.toBeInTheDocument();
    expect(within(part("Negative reviews")).queryByText(/vs previous period/)).not.toBeInTheDocument();
    unmount();

    mockKpis(kpis({ previous: { total_reviews: 0, avg_rating: null, negative_pct: null, awaiting_reply: 0 } }));
    renderBand();
    await loaded();
    expect(screen.queryByText(/vs previous period/)).not.toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/NaN|Infinity/);
  });

  it("should use singular day and hide the oldest wait when it is null", async () => {
    mockKpis(kpis({ oldest_awaiting_days: 1 }));
    const { unmount } = renderBand();
    await loaded();
    expect(screen.getByText("oldest 1 day")).toBeInTheDocument();
    unmount();

    mockKpis(kpis({ oldest_awaiting_days: null }));
    renderBand();
    await loaded();
    expect(screen.queryByText(/oldest/)).not.toBeInTheDocument();
  });

  it("should show an empty band without change lines or NaN when there are no reviews", async () => {
    mockKpis(
      kpis({
        total_reviews: 0,
        avg_rating: 0,
        negative_reviews: 0,
        negative_pct: 0,
        enriched_count: 0,
        awaiting_reply: 0,
        previous: { total_reviews: 10, avg_rating: 4.0, negative_pct: 10, awaiting_reply: 2 },
        trend: {
          total_reviews: [0, 0, 0, 0, 0, 0],
          avg_rating: [null, null, null, null, null, null],
          negative_pct: [null, null, null, null, null, null],
        },
        oldest_awaiting_days: null,
      }),
    );
    renderBand();
    await loaded();
    expect(within(part("Total reviews")).getByText("0")).toBeInTheDocument();
    expect(screen.getByTestId("star-meter-fill")).toHaveStyle({ width: "0%" });
    expect(screen.queryByText(/vs previous period/)).not.toBeInTheDocument();
    expect(screen.getAllByText("No reviews in this period").length).toBeGreaterThan(0);
    expect(document.body.innerHTML).not.toMatch(/NaN|Infinity/);
  });

  it("should name the shop when there is one store", async () => {
    mockKpis(kpis({ store_count: 1 }));
    renderBand("Kochi");
    await loaded();
    expect(within(part("Total reviews")).getByText(/Kochi/)).toBeInTheDocument();
  });

  it("should offer a retry when loading fails", async () => {
    vi.mocked(fetchKpis).mockRejectedValue(new Error("boom"));
    renderBand();
    expect(
      await screen.findByRole("button", { name: /retry loading headline numbers/i }, { timeout: 4000 }),
    ).toBeInTheDocument();
  });

  it("should show a skeleton when loading", async () => {
    vi.mocked(fetchKpis).mockReturnValue(new Promise(() => {}));
    renderBand();
    expect(screen.getByLabelText("Loading headline numbers")).toBeInTheDocument();
  });
});

describe("StarMeter", () => {
  it("should clamp and label the value when above 5", () => {
    render(<StarMeter value={7} />);
    expect(screen.getByRole("img", { name: "Average rating 5.0 out of 5" })).toBeInTheDocument();
    expect(screen.getByTestId("star-meter-fill")).toHaveStyle({ width: "100%" });
  });
});

describe("Sparkline", () => {
  it("should leave a gap when a point is null", () => {
    const { container } = render(<Sparkline points={[1, 2, null, 4, 5, 6]} label="Reviews trend" />);
    expect(container.querySelectorAll("polyline")).toHaveLength(2);
    expect(screen.getByRole("img", { name: /Reviews trend: 1, 2, no data, 4, 5, 6/ })).toBeInTheDocument();
    expect(container.innerHTML).not.toMatch(/NaN/);
  });

  it("should render nothing when fewer than 2 points exist", () => {
    const { container } = render(<Sparkline points={[null, 3, null, null, null, null]} />);
    expect(container.querySelector("svg")).toBeNull();
  });

  it("should draw without NaN when the series is flat", () => {
    const { container } = render(<Sparkline points={[0, 0, 0, 0, 0, 0]} />);
    expect(container.querySelector("svg")).not.toBeNull();
    expect(container.innerHTML).not.toMatch(/NaN/);
  });
});
