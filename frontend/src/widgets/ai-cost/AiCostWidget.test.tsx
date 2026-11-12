import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { AiCostWidget } from "./AiCostWidget";
import * as costApi from "./api";
import * as pricingApi from "../ai-pricing/api";

vi.mock("./api", async (orig) => ({
  ...(await orig<typeof import("./api")>()),
  fetchSummary: vi.fn(),
  fetchOrganisations: vi.fn(),
  fetchOrgSummary: vi.fn(),
  fetchOrgShops: vi.fn(),
  fetchOrgModels: vi.fn(),
}));
vi.mock("../ai-pricing/api", async (orig) => ({
  ...(await orig<typeof import("../ai-pricing/api")>()),
  fetchMissing: vi.fn(),
}));

describe("AiCostWidget missing-pricing alert", () => {
  beforeEach(() => {
    vi.mocked(costApi.fetchSummary).mockReturnValue(new Promise(() => {}));
    vi.mocked(costApi.fetchOrganisations).mockReturnValue(new Promise(() => {}));
    vi.mocked(costApi.fetchOrgSummary).mockReturnValue(new Promise(() => {}));
    vi.mocked(costApi.fetchOrgShops).mockReturnValue(new Promise(() => {}));
    vi.mocked(costApi.fetchOrgModels).mockReturnValue(new Promise(() => {}));
    vi.mocked(pricingApi.fetchMissing).mockReset();
    vi.mocked(pricingApi.fetchMissing).mockResolvedValue({
      models: [{ model: "gpt-x", last_used_at: null, configured: false }],
      generated_at: "x",
    });
  });

  it("shows the link-only alert on the platform view", async () => {
    render(<AiCostWidget orgId={null} />);
    expect(await screen.findByText("1 model is logged without pricing.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Go to AI Pricing →" })).toHaveAttribute(
      "href",
      "/admin/ai-pricing/",
    );
    expect(screen.queryByRole("button", { name: /Add pricing for/ })).not.toBeInTheDocument();
  });

  it("does not show it on the organisation drill-down", async () => {
    render(<AiCostWidget orgId={5} />);
    await new Promise((r) => setTimeout(r, 20));
    expect(pricingApi.fetchMissing).not.toHaveBeenCalled();
    expect(screen.queryByText(/logged without pricing/)).not.toBeInTheDocument();
  });
});
