import { render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, fetchInsights } from "../insights/api";
import type { InsightItem, InsightsBookData } from "../insights/types";

import { DashboardWidget } from "./DashboardWidget";
import { Spotlight } from "./Spotlight";
import { renderWithClient } from "./testUtils";

vi.mock("../insights/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../insights/api")>();
  return { ...actual, fetchInsights: vi.fn() };
});

// The rest of the dashboard: every report stays loading, so it renders
// without needing data.
vi.mock("./api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./api")>();
  const pending = () => new Promise(() => {});
  return {
    ...actual,
    fetchKpis: vi.fn(pending),
    fetchSentiment: vi.fn(pending),
    fetchTopPerforming: vi.fn(pending),
    fetchHighlights: vi.fn(pending),
    fetchYourStore: vi.fn(pending),
    fetchTagPolarity: vi.fn(pending),
  };
});

function item(over: Partial<InsightItem>): InsightItem {
  return {
    type: 1,
    chapter: "attention",
    headline: "6",
    title: "negative reviews have no reply",
    body: "",
    visual: { kind: "before_now", before: 1, now: 6 },
    link: { sentiment: "negative", replied: "false" },
    store: null,
    cta: "Reply now",
    caption: "",
    ...over,
  };
}

function book(items: InsightItem[]): InsightsBookData {
  return {
    cover: items.length
      ? { organisation: "Sayone", reviews: 412, stores: 4, attention: 2, good: 1 }
      : null,
    window: items.length ? { from: "2026-10-15", to: "2026-11-13" } : null,
    items,
  };
}

const ATTN_1 = item({ title: "negative reviews have no reply", headline: "6", cta: "Reply now" });
const ATTN_2 = item({
  type: 2,
  title: "Wait time complaints doubled at Kochi",
  headline: "9",
  link: { tag: 7, store: 3 },
  cta: "See reviews",
});
const GOOD_1 = item({
  type: 5,
  chapter: "good",
  title: "Trivandrum 5-star share up 10 points",
  headline: "+10",
  link: { rating: 5, store: 2 },
  cta: "",
});
const GOOD_2 = item({ type: 6, chapter: "good", title: "Replies are faster", headline: "2h" });
const GOOD_3 = item({ type: 7, chapter: "good", title: "Ratings up at Kochi", headline: "4.6" });

const mocked = () => vi.mocked(fetchInsights);

afterEach(() => mocked().mockReset());

describe("Spotlight", () => {
  it("should show the top attention item's headline, title and action in the yellow block when one exists", async () => {
    mocked().mockResolvedValue(book([ATTN_1, ATTN_2, GOOD_1]));
    renderWithClient(<Spotlight enabled />);

    const block = await screen.findByRole("region", { name: "Top insight" });
    expect(within(block).getByText("Needs attention")).toBeInTheDocument();
    expect(within(block).getByText("6")).toBeInTheDocument();
    expect(within(block).getByText("negative reviews have no reply")).toBeInTheDocument();
    const cta = within(block).getByRole("link", { name: "Reply now" });
    expect(cta).toHaveAttribute(
      "href",
      "/admin/org/reviews/?sentiment=negative&replied=false",
    );
  });

  it("should fall back to the top good item when nothing needs attention", async () => {
    mocked().mockResolvedValue(book([GOOD_1, GOOD_2]));
    renderWithClient(<Spotlight enabled />);

    const block = await screen.findByRole("region", { name: "Top insight" });
    expect(within(block).getByText("Good news")).toBeInTheDocument();
    expect(within(block).getByText("★")).toBeInTheDocument();
    expect(within(block).getByText("+10")).toBeInTheDocument();
    expect(within(block).getByText("Trivandrum 5-star share up 10 points")).toBeInTheDocument();
    // Empty cta falls back to "See reviews".
    expect(within(block).getByRole("link", { name: "See reviews" })).toHaveAttribute(
      "href",
      "/admin/org/reviews/?rating=5&store=2",
    );
  });

  it("should list the next two items as rows with a stated chapter and a link when there are more items", async () => {
    mocked().mockResolvedValue(book([ATTN_1, ATTN_2, GOOD_1, GOOD_2]));
    renderWithClient(<Spotlight enabled />);

    const list = await screen.findByRole("list", { name: "More insights" });
    const rows = within(list).getAllByRole("listitem");
    expect(rows).toHaveLength(2);

    // Chapter is visible by shape, not just colour (the label is sr-only).
    expect(within(rows[0]).getByText("●")).toBeVisible();
    expect(within(rows[0]).queryByText("★")).not.toBeInTheDocument();
    expect(rows[0]).toHaveTextContent("Needs attention");
    expect(rows[0]).toHaveTextContent("Wait time complaints doubled at Kochi");
    expect(within(rows[0]).getByRole("link")).toHaveAttribute(
      "href",
      "/admin/org/reviews/?tag=7&store=3",
    );
    expect(within(rows[1]).getByText("★")).toBeVisible();
    expect(within(rows[1]).queryByText("●")).not.toBeInTheDocument();
    expect(rows[1]).toHaveTextContent("Good news");
    expect(rows[1]).toHaveTextContent("Trivandrum 5-star share up 10 points");
    expect(within(rows[1]).getByRole("link")).toHaveAttribute(
      "href",
      "/admin/org/reviews/?rating=5&store=2",
    );
  });

  it("should not repeat the yellow item in the rows when it is not first", async () => {
    // Defensive: if a good item ever ranks above an attention one.
    mocked().mockResolvedValue(book([GOOD_1, ATTN_1, GOOD_2]));
    renderWithClient(<Spotlight enabled />);

    const block = await screen.findByRole("region", { name: "Top insight" });
    expect(within(block).getByText("negative reviews have no reply")).toBeInTheDocument();
    const rows = within(screen.getByRole("list", { name: "More insights" })).getAllByRole(
      "listitem",
    );
    expect(rows.map((r) => r.textContent)).toEqual([
      expect.stringContaining("Trivandrum 5-star share up 10 points"),
      expect.stringContaining("Replies are faster"),
    ]);
  });

  it("should link the rest to the Insights page as 'N more' when there are more than three", async () => {
    mocked().mockResolvedValue(book([ATTN_1, ATTN_2, GOOD_1, GOOD_2, GOOD_3]));
    renderWithClient(<Spotlight enabled />);

    const more = await screen.findByRole("link", { name: "2 more on the Insights page" });
    expect(more).toHaveAttribute("href", "/admin/org/insights/");
    expect(screen.queryByRole("link", { name: "Open Insights" })).not.toBeInTheDocument();
  });

  it("should offer a quiet 'Open Insights' link when there is nothing more", async () => {
    mocked().mockResolvedValue(book([ATTN_1, GOOD_1, GOOD_2]));
    renderWithClient(<Spotlight enabled />);

    const open = await screen.findByRole("link", { name: "Open Insights" });
    expect(open).toHaveAttribute("href", "/admin/org/insights/");
    expect(screen.queryByText(/more on the Insights page/)).not.toBeInTheDocument();
  });

  it("should show no rows when there is a single item", async () => {
    mocked().mockResolvedValue(book([ATTN_1]));
    renderWithClient(<Spotlight enabled />);

    await screen.findByRole("region", { name: "Top insight" });
    expect(screen.queryByRole("list", { name: "More insights" })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open Insights" })).toBeInTheDocument();
  });

  it("should render nothing when there are no insights", async () => {
    mocked().mockResolvedValue(book([]));
    const { container } = renderWithClient(<Spotlight enabled />);

    await waitFor(() => expect(mocked()).toHaveBeenCalledTimes(1));
    await new Promise((r) => setTimeout(r, 0)); // let the empty response settle
    expect(container).toBeEmptyDOMElement();
  });

  it("should render nothing when still loading", () => {
    mocked().mockReturnValue(new Promise(() => {}));
    const { container } = renderWithClient(<Spotlight enabled />);
    expect(container).toBeEmptyDOMElement();
  });

  it("should render nothing when the API errors", async () => {
    mocked().mockRejectedValue(new ApiError(500));
    const { container } = renderWithClient(<Spotlight enabled />);

    await waitFor(() => expect(mocked()).toHaveBeenCalled());
    await new Promise((r) => setTimeout(r, 0)); // let the rejection settle
    expect(container).toBeEmptyDOMElement();
  });

  it("should not fetch or render when disabled", () => {
    const { container } = renderWithClient(<Spotlight enabled={false} />);
    expect(mocked()).not.toHaveBeenCalled();
    expect(container).toBeEmptyDOMElement();
  });
});

describe("DashboardWidget spotlight", () => {
  function mountRoot(isOrgAdmin: boolean) {
    document.body.innerHTML = `
      <script id="dashboard-regions" type="application/json">[]</script>
      <script id="dashboard-shops" type="application/json">[{"id":1,"name":"Kochi"},{"id":2,"name":"Trivandrum"}]</script>
      <div id="dashboard-root" data-is-org-admin="${isOrgAdmin}" data-is-single-shop="false"></div>`;
  }

  beforeEach(() => window.history.replaceState({}, "", "/dashboard/"));
  afterEach(() => {
    document.body.innerHTML = "";
  });

  it("should never fetch or render the spotlight when the user is Staff", async () => {
    mountRoot(false);
    mocked().mockResolvedValue(book([ATTN_1, ATTN_2, GOOD_1]));
    render(<DashboardWidget />);

    expect(await screen.findByLabelText("Filter by store")).toBeInTheDocument();
    expect(mocked()).not.toHaveBeenCalled();
    expect(screen.queryByRole("region", { name: "Top insight" })).not.toBeInTheDocument();
  });

  it("should hide the spotlight and keep the rest of the dashboard when the API returns 500", async () => {
    mountRoot(true);
    mocked().mockRejectedValue(new ApiError(500));
    render(<DashboardWidget />);

    await waitFor(() => expect(mocked()).toHaveBeenCalled());
    await new Promise((r) => setTimeout(r, 0)); // let the rejection settle
    expect(screen.getByLabelText("Filter by store")).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Top insight" })).not.toBeInTheDocument();
    expect(screen.queryByRole("list", { name: "More insights" })).not.toBeInTheDocument();
  });
});
