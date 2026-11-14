import { screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { fetchTagPolarity } from "./api";
import { TagPolarityChart } from "./TagPolarityChart";
import { renderWithClient } from "./testUtils";
import type { TagPolarityResponse } from "./types";

vi.mock("./api", () => ({ fetchTagPolarity: vi.fn() }));

const DATA: TagPolarityResponse = {
  tags: [
    { label: "Friendly staff", polarity_type: "mixed", positive_count: 42, negative_count: 4, total_count: 46 },
    { label: "Wait time", polarity_type: "always_negative", positive_count: 0, negative_count: 18, total_count: 18 },
  ],
  has_more: true,
};

describe("Top tags tug-of-war", () => {
  afterEach(() => vi.mocked(fetchTagPolarity).mockReset());

  it("should print complaints on the left and praise on the right of each tag", async () => {
    vi.mocked(fetchTagPolarity).mockResolvedValue(DATA);
    renderWithClient(<TagPolarityChart />);

    const row = await screen.findByRole("group", { name: "Friendly staff: 4 complaints, 42 praise" });
    expect(within(row).getByText("Friendly staff")).toBeInTheDocument();
    expect(within(row).getByTestId("complaints-count")).toHaveTextContent("4");
    expect(within(row).getByTestId("praise-count")).toHaveTextContent("42");
    expect(screen.getByText("All stores, all time")).toBeInTheDocument();
  });

  it("should size every bar against the largest count on either side", async () => {
    vi.mocked(fetchTagPolarity).mockResolvedValue(DATA);
    renderWithClient(<TagPolarityChart />);

    const friendly = await screen.findByRole("group", { name: /^Friendly staff/ });
    const wait = screen.getByRole("group", { name: /^Wait time/ });
    expect(within(friendly).getByTestId("praise-bar")).toHaveStyle({ width: "100%" });
    expect(within(friendly).getByTestId("complaints-bar")).toHaveStyle({ width: "9.5%" });
    expect(within(wait).getByTestId("complaints-bar")).toHaveStyle({ width: "42.9%" });
    expect(within(wait).getByTestId("praise-bar")).toHaveStyle({ width: "0%" });
    expect(within(wait).getByTestId("praise-count")).toHaveTextContent("0");
  });

  it("should link to all tags when there are more", async () => {
    vi.mocked(fetchTagPolarity).mockResolvedValue(DATA);
    renderWithClient(<TagPolarityChart />);
    expect(await screen.findByRole("link", { name: "See all tags" })).toHaveAttribute(
      "href",
      "/admin/org/tags/",
    );
  });

  it("should show the empty note when there are no tags", async () => {
    vi.mocked(fetchTagPolarity).mockResolvedValue({ tags: [], has_more: false });
    renderWithClient(<TagPolarityChart />);
    expect(await screen.findByText(/No canonical tags yet/)).toBeInTheDocument();
  });

  it("should show loading and error states", async () => {
    vi.mocked(fetchTagPolarity).mockReturnValue(new Promise(() => {}));
    const { unmount } = renderWithClient(<TagPolarityChart />);
    expect(screen.getByLabelText("Loading top tags")).toBeInTheDocument();
    unmount();

    vi.mocked(fetchTagPolarity).mockRejectedValue(new Error("boom"));
    renderWithClient(<TagPolarityChart />);
    expect(await screen.findByText("Could not load tag distribution.")).toBeInTheDocument();
  });
});
