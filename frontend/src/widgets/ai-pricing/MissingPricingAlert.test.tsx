import { describe, it, expect, vi, beforeEach } from "vitest";
import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MissingPricingAlert } from "./MissingPricingAlert";
import * as api from "./api";
import { ApiError } from "./api";

vi.mock("./api", async (orig) => ({
  ...(await orig<typeof import("./api")>()),
  fetchMissing: vi.fn(),
  refreshMissing: vi.fn(),
}));

const m = (model: string, configured = false) => ({ model, last_used_at: null, configured });
const resp = (models: ReturnType<typeof m>[]) => ({ models, generated_at: "2026-11-12T10:00:00Z" });

describe("MissingPricingAlert", () => {
  beforeEach(() => {
    vi.mocked(api.fetchMissing).mockReset();
    vi.mocked(api.refreshMissing).mockReset();
  });

  it("renders nothing when no models are missing", async () => {
    vi.mocked(api.fetchMissing).mockResolvedValue(resp([]));
    const { container } = render(<MissingPricingAlert variant="pricing" />);
    await act(async () => {
      await Promise.resolve();
    });
    expect(api.fetchMissing).toHaveBeenCalled();
    expect(container).toBeEmptyDOMElement();
  });

  it("uses the singular heading for one model", async () => {
    vi.mocked(api.fetchMissing).mockResolvedValue(resp([m("gpt-x")]));
    render(<MissingPricingAlert variant="pricing" />);
    expect(await screen.findByText("1 model is logged without pricing.")).toBeInTheDocument();
    expect(
      screen.getByText(/These calls show \$0 in cost totals until pricing is added\./),
    ).toBeInTheDocument();
  });

  it("uses the plural heading, lists models and marks the configured one", async () => {
    vi.mocked(api.fetchMissing).mockResolvedValue(resp([m("gpt-x", true), m("gpt-y")]));
    render(<MissingPricingAlert variant="pricing" onAddFor={vi.fn()} />);
    expect(await screen.findByText("2 models are logged without pricing.")).toBeInTheDocument();
    expect(screen.getByText("gpt-x")).toBeInTheDocument();
    expect(screen.getByText("gpt-y")).toBeInTheDocument();
    expect(screen.getByText("(configured model)")).toBeInTheDocument();
    expect(screen.getByText(/Missing:/)).toBeInTheDocument();
  });

  it("warns that enrichment fails only when the configured model is missing", async () => {
    vi.mocked(api.fetchMissing).mockResolvedValue(resp([m("gpt-x", true)]));
    const { unmount } = render(<MissingPricingAlert variant="pricing" onAddFor={vi.fn()} />);
    expect(await screen.findByText(/Enrichment fails until the configured model has a price\./)).toBeInTheDocument();
    unmount();
    vi.mocked(api.fetchMissing).mockResolvedValue(resp([m("gpt-y")]));
    render(<MissingPricingAlert variant="pricing" onAddFor={vi.fn()} />);
    await screen.findByText("1 model is logged without pricing.");
    expect(screen.queryByText(/Enrichment fails/)).not.toBeInTheDocument();
  });

  it("pricing variant: per-model buttons call onAddFor", async () => {
    vi.mocked(api.fetchMissing).mockResolvedValue(resp([m("gpt-x"), m("gpt-y")]));
    const onAddFor = vi.fn();
    render(<MissingPricingAlert variant="pricing" onAddFor={onAddFor} />);
    await userEvent.click(await screen.findByRole("button", { name: "Add pricing for gpt-y →" }));
    expect(onAddFor).toHaveBeenCalledWith("gpt-y");
    expect(screen.getByRole("button", { name: "Add pricing for gpt-x →" })).toBeInTheDocument();
  });

  it("cost-explorer variant: link to AI Pricing, no add or refresh buttons", async () => {
    vi.mocked(api.fetchMissing).mockResolvedValue(resp([m("gpt-x")]));
    render(<MissingPricingAlert variant="cost-explorer" />);
    const link = await screen.findByRole("link", { name: "Go to AI Pricing →" });
    expect(link).toHaveAttribute("href", "/admin/ai-pricing/");
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("refresh replaces the list; hides when the recheck finds nothing", async () => {
    vi.mocked(api.fetchMissing).mockResolvedValue(resp([m("gpt-x")]));
    vi.mocked(api.refreshMissing).mockResolvedValue(resp([]));
    const { container } = render(<MissingPricingAlert variant="pricing" onAddFor={vi.fn()} />);
    await userEvent.click(
      await screen.findByRole("button", { name: "Refresh missing-pricing check" }),
    );
    await vi.waitFor(() => expect(container).toBeEmptyDOMElement());
  });

  it("shows the wait message on a 429 refresh and keeps the alert", async () => {
    vi.mocked(api.fetchMissing).mockResolvedValue(resp([m("gpt-x")]));
    vi.mocked(api.refreshMissing).mockRejectedValue(new ApiError(429, "Request was throttled."));
    render(<MissingPricingAlert variant="pricing" onAddFor={vi.fn()} />);
    await userEvent.click(
      await screen.findByRole("button", { name: "Refresh missing-pricing check" }),
    );
    expect(
      await screen.findByText("Please wait a minute before refreshing again."),
    ).toBeInTheDocument();
    expect(screen.getByText("1 model is logged without pricing.")).toBeInTheDocument();
  });
});
