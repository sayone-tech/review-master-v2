import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
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
    expect(screen.getByRole("link", { name: "Go to AI Pricing" })).toHaveAttribute(
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

describe("AiCostWidget breadcrumb", () => {
  let crumb: HTMLElement;
  beforeEach(() => {
    vi.mocked(costApi.fetchSummary).mockReturnValue(new Promise(() => {}));
    vi.mocked(costApi.fetchOrganisations).mockReturnValue(new Promise(() => {}));
    vi.mocked(costApi.fetchOrgSummary).mockReturnValue(new Promise(() => {}));
    vi.mocked(costApi.fetchOrgShops).mockReturnValue(new Promise(() => {}));
    vi.mocked(costApi.fetchOrgModels).mockReturnValue(new Promise(() => {}));
    vi.mocked(pricingApi.fetchMissing).mockResolvedValue({ models: [], generated_at: "x" });
    crumb = document.createElement("strong");
    crumb.id = "topbar-breadcrumb";
    crumb.textContent = "AI Cost";
    document.body.appendChild(crumb);
    window.history.replaceState(null, "", "/admin/ai-cost/organisations/5/?range=7d");
  });
  afterEach(() => crumb.remove());

  it("shows AI Cost / name with a link back that keeps the filters", () => {
    render(<AiCostWidget orgId={5} orgName="Sayone" />);
    expect(crumb).toHaveTextContent("AI Cost/Sayone");
    const link = crumb.querySelector("a")!;
    expect(link).toHaveTextContent("AI Cost");
    expect(link.getAttribute("href")).toBe("/admin/ai-cost/?range=7d");
  });

  it("a plain click goes back client-side; a modified click is left to the browser", () => {
    render(<AiCostWidget orgId={5} orgName="Sayone" />);
    const link = crumb.querySelector("a")!;
    link.addEventListener("click", (e) => e.preventDefault()); // avoid jsdom navigation
    fireEvent.click(link, { ctrlKey: true });
    expect(window.location.pathname).toBe("/admin/ai-cost/organisations/5/");
    fireEvent.click(link);
    expect(window.location.pathname).toBe("/admin/ai-cost/");
    expect(crumb.textContent).toBe("AI Cost");
    expect(crumb.querySelector("a")).toBeNull();
    expect(screen.getByRole("heading", { level: 1, name: "AI Cost Explorer" })).toBeInTheDocument();
  });

  it("is just AI Cost when the organisation is unknown", () => {
    render(<AiCostWidget orgId={5} orgName={null} />);
    expect(crumb.textContent).toBe("AI Cost");
  });

  it("re-applies after a Turbo visit resets the top bar", () => {
    render(<AiCostWidget orgId={5} orgName="Sayone" />);
    crumb.textContent = "AI Cost";
    document.dispatchEvent(new Event("turbo:load"));
    expect(crumb).toHaveTextContent("AI Cost/Sayone");
  });
});
